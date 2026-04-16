import sys
import asyncio
import threading
import logging
import numpy as np
import httpx
from pathlib import Path
from typing import Dict, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor
from pypdf import PdfReader

# الإعدادات ومسارات المكتبات
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
logger = logging.getLogger("AI_SERVER_MANAGER")

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
executor = ThreadPoolExecutor(max_workers=4)

# مسار الـ WSL من الويندوز
WSL_BASE_PATH = Path(r"\\wsl.localhost\Ubuntu\home\rawannada\graduation_infra\backend-node")
WORKER_URLS: List[str] = ["http://192.168.1.12:8001"]

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

# --- Helper: تنظيف المسارات للويندوز ---
def _get_clean_path(raw_path: str) -> Path:
    p = Path(raw_path)
    if "uploads" in p.parts:
        idx = p.parts.index("uploads")
        relative_path = Path(*p.parts[idx:])
    else:
        relative_path = Path("uploads") / p.name
    
    file_path = WSL_BASE_PATH / relative_path
    if not file_path.exists():
        if Path(raw_path).exists(): return Path(raw_path)
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

# --- التجميع الذكي (Merge) - الحل هنا ---
def _merge_result_into_store(vs: VectorStore, result: dict):
    if not result or "embeddings" not in result:
        return
    
    # تأمين وجود السمات المطلوبة في كائن vs
    if not hasattr(vs, 'documents'): vs.documents = []
    if not hasattr(vs, 'embeddings'): vs.embeddings = None

    # تحويل الـ Embeddings لـ Numpy Array
    new_embs = np.array(result["embeddings"], dtype=np.float32)
    
    if vs.embeddings is None:
        vs.embeddings = new_embs
    else:
        vs.embeddings = np.vstack([vs.embeddings, new_embs])
        
    # تجميع النصوص (سواء جاية باسم chunks أو documents)
    incoming_text = result.get("chunks", result.get("documents", []))
    vs.documents.extend(incoming_text)

# --- بناء الـ Vector Store بالتوزيع ---
async def _call_worker_vectorize(worker_url: str, file_path: Path, start: int, end: int) -> dict:
    async with httpx.AsyncClient(timeout=600) as client:
        try:
            with open(file_path, "rb") as f:
                files = {'file': (file_path.name, f, 'application/pdf')}
                data = {'startPage': str(start), 'endPage': str(end)}
                response = await client.post(f"{worker_url}/process", files=files, data=data)
            return response.json() if response.status_code == 200 else {}
        except Exception as e:
            logger.error(f"Worker {worker_url} failed: {e}")
            return {}

def _build_local_partial(file_path: Path, start: int, end: int):
    vs = VectorStore(max_workers=4)
    processor = PDFProcessor(str(file_path))
    pages_data = processor.process_pdf(start_page=start, end_page=end)
    
    chunked_data = []
    for section in pages_data:
        chunks = split_into_chunks(section["text"], max_words=100)
        for chunk in chunks:
            chunked_data.append({
                "text": chunk,
                "filename": section["filename"],
                "page_num": section["page_num"],
            })
    
    vs.create_vector_store(chunked_data)
    return {
        "embeddings": vs.embeddings.tolist() if vs.embeddings is not None else [],
        "chunks": chunked_data
    }

async def _distribute_and_build(file_path: Path, cache_key: str):
    try:
        reader = PdfReader(str(file_path))
        total_pages = len(reader.pages)
        num_total = len(WORKER_URLS) + 1
        page_ranges = _split_pages(total_pages, num_total)
        
        worker_tasks = [
            _call_worker_vectorize(url, file_path, r[0], r[1]) 
            for i, (url, r) in enumerate(zip(WORKER_URLS, page_ranges))
        ]
        
        loop = asyncio.get_event_loop()
        local_task = loop.run_in_executor(executor, _build_local_partial, file_path, page_ranges[-1][0], page_ranges[-1][1])
        
        results = await asyncio.gather(*worker_tasks)
        local_res = await local_task

        master_vs = VectorStore(max_workers=4)
        _merge_result_into_store(master_vs, local_res)
        for res in results:
            if isinstance(res, dict): _merge_result_into_store(master_vs, res)
        
        if master_vs.embeddings is not None:
            import faiss
            d = master_vs.embeddings.shape[1]
            master_vs.index = faiss.IndexFlatL2(d)
            master_vs.index.add(master_vs.embeddings)
            master_vs.save(cache_key)
            vector_stores[cache_key] = master_vs
            logger.info(f"Master Store Built & Saved: {cache_key}")
            
    except Exception as e:
        logger.error(f"Distribute Build Error: {e}")
    finally:
        with _vs_lock: vs_building.discard(cache_key)

# --- Routes ---
@app.post("/api/summarize")
async def summarize(request: SummarizeRequest):
    file_path = _get_clean_path(request.filePath)
    cache_key = request.fileId or _cache_key(str(file_path))
    
    summarizer = PDFSummarizer()
    summary_result = summarizer.summarize(str(file_path))

    with _vs_lock:
        if cache_key not in vector_stores and cache_key not in vs_building:
            vs_building.add(cache_key)
            asyncio.create_task(_distribute_and_build(file_path, cache_key))

    return {"status": "success", "summary": summary_result, "metadata": {"cache_key": cache_key}}

@app.post("/api/ask")
async def ask(request: QuestionRequest):
    file_path = _get_clean_path(request.filePath)
    cache_key = request.fileId or _cache_key(str(file_path))
    
    wait = 0
    while cache_key in vs_building and wait < 60:
        await asyncio.sleep(1); wait += 1

    if cache_key not in vector_stores:
        vs = VectorStore(max_workers=4)
        if not vs.load(cache_key):
             await _distribute_and_build(file_path, cache_key)
        vector_stores[cache_key] = vs

    rag = RAGPipeline(vector_store=vector_stores[cache_key])
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, rag.query, request.question)
    return {"status": "success", "answer": result.get("answer"), "sources": result.get("sources")}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)