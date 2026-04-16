import sys
import asyncio
import threading
import logging
import numpy as np
import httpx
import io
from pathlib import Path
from typing import Dict, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor
from pypdf import PdfReader

# الإعدادات
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent / "pdf_summarizer" / "src"))

from vector_store import VectorStore, CACHE_DIR, _cache_key
from rag_pipeline import RAGPipeline
from pdf_processor import PDFProcessor

try:
    from pdf_summarizer.src.summarizer import PDFSummarizer
except ImportError:
    from summarizer import PDFSummarizer

try:
    from pdf_summarizer.src.chunker import split_into_chunks
except ImportError:
    from src.chunker import split_into_chunks

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("AI_SERVER")

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
executor = ThreadPoolExecutor(max_workers=4)


WSL_BASE_PATH = Path(r"\\wsl.localhost\Ubuntu\home\rawannada\graduation_infra\backend-node")


WORKER_URLS: List[str] = [
    # "http://192.168.1.XX:8001", 
]

vector_stores: Dict[str, VectorStore] = {}
vs_building: set = set()
_vs_lock = threading.Lock()

class SummarizeRequest(BaseModel):
    filePath: str
    fileId: str = None

class QuestionRequest(BaseModel):
    filePath: str
    question: str
    fileId: str = None

def _get_clean_path(raw_path: str) -> Path:
    p = Path(raw_path)
    parts = p.parts
    idx = parts.index("uploads") if "uploads" in parts else -1
    relative_path = Path(*parts[idx:]) if idx != -1 else Path("uploads") / p.name
    file_path = WSL_BASE_PATH.joinpath(relative_path).resolve()
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    return file_path

def _split_pages(total_pages: int, num_workers: int) -> List[tuple]:
    chunk_size = total_pages // num_workers
    ranges = []
    start = 0
    for i in range(num_workers):
        end = start + chunk_size if i < num_workers - 1 else total_pages
        ranges.append((start, end))
        start = end
    return ranges

# ─────────────────────────────────────────────────────────────────────────────
# التعديل الجوهري: إرسال الملف كـ Stream
# ─────────────────────────────────────────────────────────────────────────────
async def _call_worker(worker_url: str, file_path: Path, start: int, end: int) -> dict:
    async with httpx.AsyncClient(timeout=600) as client:
        logger.info(f"إرسال Streaming للملف إلى {worker_url} (صفحة {start} → {end})")
        
        # نفتح الملف ونبعته في الطلب
        with open(file_path, "rb") as f:
            files = {'file': (file_path.name, f, 'application/pdf')}
            data = {'startPage': str(start), 'endPage': str(end)}
            
            response = await client.post(
                f"{worker_url}/process",
                files=files,
                data=data
            )
        
        if response.status_code != 200:
            logger.error(f"فشل الوركير {worker_url}: {response.text}")
            response.raise_for_status()
            
        return response.json()

def _build_local_partial(file_path: Path, start: int, end: int) -> dict:
    from embeddings import EmbeddingGenerator
    processor = PDFProcessor(str(file_path))
    pages_data = processor.process_pdf(use_ocr=False, use_sections=True, start_page=start, end_page=end)

    chunked_data = []
    for section in pages_data:
        chunks = split_into_chunks(section["text"], max_words=100)
        for chunk in chunks:
            chunked_data.append({
                "text": chunk,
                "filename": section["filename"],
                "page_num": section["page_num"],
                "source": section.get("source", section["filename"]),
                "section_title": section.get("section_title", ""),
            })

    if not chunked_data: return {"documents": [], "vectors": [], "raw_vectors": []}

    gen = EmbeddingGenerator(max_workers=4)
    texts = [c["text"] for c in chunked_data]
    embeddings = gen.embed_documents(texts)
    emb_np = np.array(embeddings).astype("float32")
    
    norms = np.linalg.norm(emb_np, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normalized = emb_np / norms

    return {"documents": chunked_data, "vectors": normalized.tolist(), "raw_vectors": emb_np.tolist()}

def _merge_result_into_store(vs: VectorStore, result: dict) -> None:
    import faiss
    documents = result.get("documents", [])
    raw_vectors = result.get("raw_vectors", [])
    vectors = result.get("vectors", [])

    if not documents or not raw_vectors: return

    raw_np = np.array(raw_vectors).astype("float32")
    norm_np = np.array(vectors).astype("float32")
    
    if vs.index is None:
        vs.index = faiss.IndexFlatL2(raw_np.shape[1])
        vs.documents = []
        vs.vectors = None

    vs.index.add(raw_np)
    vs.documents.extend(documents)
    vs.vectors = np.vstack([vs.vectors, norm_np]) if vs.vectors is not None else norm_np

async def _distribute_and_build(file_path: Path, cache_key: str, file_id: str) -> None:
    try:
        reader = PdfReader(str(file_path))
        total_pages = len(reader.pages)
        num_total = len(WORKER_URLS) + 1
        page_ranges = _split_pages(total_pages, num_total)
        
        local_range = page_ranges[-1]
        worker_ranges = page_ranges[:-1]

        # تشغيل الأصحاب
        worker_tasks = [
            _call_worker(WORKER_URLS[i], file_path, worker_ranges[i][0], worker_ranges[i][1])
            for i in range(len(WORKER_URLS))
        ]

        # تشغيل جهازك
        loop = asyncio.get_event_loop()
        local_future = loop.run_in_executor(executor, _build_local_partial, file_path, local_range[0], local_range[1])

        worker_results = await asyncio.gather(*worker_tasks, return_exceptions=True)
        local_result = await local_future

        vs = VectorStore(max_workers=4)
        _merge_result_into_store(vs, local_result)

        for i, result in enumerate(worker_results):
            if isinstance(result, Exception): continue
            _merge_result_into_store(vs, result)

        vs.save(cache_key)
        vector_stores[cache_key] = vs
    finally:
        vs_building.discard(cache_key)

def _build_solo(file_path: Path, cache_key: str) -> None:
    vs = VectorStore(max_workers=4)
    if vs.load(cache_key):
        vector_stores[cache_key] = vs
        return
    try:
        processor = PDFProcessor(str(file_path))
        pages_data = processor.process_pdf(use_ocr=False, use_sections=True)
        chunked_data = []
        for section in pages_data:
            chunks = split_into_chunks(section["text"], max_words=100)
            for chunk in chunks:
                chunked_data.append({
                    "text": chunk,
                    "filename": section["filename"],
                    "page_num": section["page_num"],
                    "source": section.get("source", section["filename"]),
                    "section_title": section.get("section_title", ""),
                })
        vs.create_vector_store(chunked_data, cache_source=cache_key)
        vector_stores[cache_key] = vs
    finally:
        vs_building.discard(cache_key)

@app.on_event("startup")
def _preload_caches():
    def _load():
        for f in CACHE_DIR.glob("*.index"):
            vs = VectorStore(max_workers=4)
            if vs.load(f.stem): vector_stores[f.stem] = vs
    threading.Thread(target=_load, daemon=True).start()

@app.post("/api/summarize")
async def summarize(request: SummarizeRequest):
    file_path = _get_clean_path(request.filePath)
    cache_key = request.fileId or _cache_key(str(file_path))
    
    summarizer = PDFSummarizer()
    summary = summarizer.summarize(str(file_path))

    with _vs_lock:
        if cache_key not in vector_stores and cache_key not in vs_building:
            vs_building.add(cache_key)
            if WORKER_URLS:
                asyncio.create_task(_distribute_and_build(file_path, cache_key, cache_key))
            else:
                threading.Thread(target=_build_solo, args=(file_path, cache_key), daemon=True).start()

    return {"status": "success", "summary": summary, "metadata": {"cache_key": cache_key}}

@app.post("/api/ask")
async def ask(request: QuestionRequest):
    file_path = _get_clean_path(request.filePath)
    cache_key = request.fileId or _cache_key(str(file_path))
    
    wait = 0
    while cache_key in vs_building and wait < 60:
        await asyncio.sleep(1)
        wait += 1

    if cache_key not in vector_stores:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(executor, _build_solo, file_path, cache_key)

    rag = RAGPipeline(vector_store=vector_stores[cache_key])
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, rag.query, request.question)
    return {"status": "success", **result}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)