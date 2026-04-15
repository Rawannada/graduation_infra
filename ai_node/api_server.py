import sys
import asyncio
import threading
import pickle
import hashlib
import logging
from pathlib import Path
from typing import Dict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor

# ─────────────────────────────────────────────────────────────────────────────
# 1. SETUP LOGGING
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("AI_SERVER")

# ─────────────────────────────────────────────────────────────────────────────
# 2. LIBRARY PATHS
# ─────────────────────────────────────────────────────────────────────────────
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

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = ThreadPoolExecutor(max_workers=4)

# ─────────────────────────────────────────────────────────────────────────────
# 3. PATHS & REGISTRY
# ─────────────────────────────────────────────────────────────────────────────
WSL_BASE_PATH = Path(r"\\wsl.localhost\Ubuntu\home\rawannada\graduation_infra\backend-node")

vector_stores: Dict[str, VectorStore] = {}
vs_building: set = set()

class SummarizeRequest(BaseModel):
    filePath: str
    fileId: str = None

class QuestionRequest(BaseModel):
    filePath: str
    question: str
    fileId: str = None

# ─────────────────────────────────────────────────────────────────────────────
# 4. PATH RESOLVER
# ─────────────────────────────────────────────────────────────────────────────
def _get_clean_path(raw_path: str) -> Path:
    p = Path(raw_path)
    parts = p.parts

    if "uploads" in parts:
        index = parts.index("uploads")
        relative_path = Path(*parts[index:])
    else:
        relative_path = Path("uploads") / p.name

    file_path = WSL_BASE_PATH.joinpath(relative_path).resolve()
    
    if not file_path.exists():
        logger.error(f"File system check failed: {file_path}")
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    return file_path

# ─────────────────────────────────────────────────────────────────────────────
# 5. VECTOR STORE LOGIC
# ─────────────────────────────────────────────────────────────────────────────
def _get_or_build_vector_store(file_path: Path, cache_key: str) -> None:
    if cache_key in vector_stores:
        return

    vs = VectorStore(max_workers=4)

    if vs.load(cache_key):
        vector_stores[cache_key] = vs
        logger.info(f"Successfully loaded store from disk for ID: {cache_key}")
        return

    try:
        logger.info(f"Building fresh Vector Store for: {file_path.name}")
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

        logger.info(f"Generated {len(chunked_data)} chunks for indexing.")
        vs.create_vector_store(chunked_data, cache_source=cache_key)
        vector_stores[cache_key] = vs
        logger.info(f"Vector Store creation complete: {cache_key}")

    except Exception as e:
        logger.error(f"Vector building failure: {str(e)}")
    finally:
        vs_building.discard(cache_key)

# ─────────────────────────────────────────────────────────────────────────────
# 6. LIFECYCLE EVENTS
# ─────────────────────────────────────────────────────────────────────────────
@app.on_event("startup")
def _preload_caches() -> None:
    def _load_all():
        index_files = list(CACHE_DIR.glob("*.index"))
        logger.info(f"Scanning cache directory: {CACHE_DIR}")
        for index_file in index_files:
            try:
                cache_id = index_file.stem
                vs = VectorStore(max_workers=4)
                if vs.load(cache_id):
                    vector_stores[cache_id] = vs
            except Exception as e:
                logger.warning(f"Failed to preload {index_file.name}: {e}")
        logger.info(f"Startup complete. Memory registry contains {len(vector_stores)} stores.")

    threading.Thread(target=_load_all, daemon=True).start()

# ─────────────────────────────────────────────────────────────────────────────
# 7. ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"status": "healthy", "nodes_loaded": len(vector_stores)}

@app.post("/api/summarize")
def summarize(request: SummarizeRequest):
    logger.info("--- SUMMARIZE REQUEST START ---")
    logger.debug(f"Payload: {request.model_dump()}")
    
    try:
        file_path = _get_clean_path(request.filePath)
        cache_key = request.fileId if request.fileId else _cache_key(str(file_path))
        
        logger.info(f"Processing File: {file_path.name} | Cache Key: {cache_key}")

        summarizer = PDFSummarizer()
        summary_result = summarizer.summarize(str(file_path))

        if cache_key not in vector_stores and cache_key not in vs_building:
            vs_building.add(cache_key)
            threading.Thread(
                target=_get_or_build_vector_store, 
                args=(file_path, cache_key), 
                daemon=True
            ).start()

        return {
            "status": "success",
            "summary": summary_result,
            "metadata": {"filename": file_path.name, "cache_key": cache_key},
        }
    except Exception as e:
        logger.error(f"Summarize API Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ask")
async def ask(request: QuestionRequest):
    logger.info("--- ASK REQUEST START ---")
    try:
        if not request.question.strip():
            raise HTTPException(status_code=400, detail="Empty question")
        
        file_path = _get_clean_path(request.filePath)
        cache_key = request.fileId if request.fileId else _cache_key(str(file_path))

        # Wait if building is in progress
        wait_count = 0
        while cache_key in vs_building and wait_count < 60:
            logger.info(f"Waiting for VectorStore {cache_key} to finish building... {wait_count}s")
            await asyncio.sleep(1)
            wait_count += 1

        if cache_key not in vector_stores:
            logger.info(f"Cache miss for {cache_key}. Triggering manual build.")
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(executor, _get_or_build_vector_store, file_path, cache_key)

        if cache_key not in vector_stores:
            raise HTTPException(status_code=500, detail="Vector Store initialization failed")

        logger.info(f"Querying RAG Pipeline for ID: {cache_key}")
        rag = RAGPipeline(vector_store=vector_stores[cache_key])
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(executor, rag.query, request.question)

        logger.info(f"Successfully generated answer. Sources found: {len(result.get('sources', []))}")
        
        return {
            "status": "success",
            "answer": result.get("answer", ""),
            "sources": result.get("sources", []),
        }
    except Exception as e:
        logger.error(f"Ask API Exception: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)