import sys
import asyncio
import threading
import logging
import numpy as np
import httpx
from pathlib import Path
from typing import Dict, List, Tuple
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor
from pypdf import PdfReader

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

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("AI_SERVER_MANAGER")

# ─────────────────────────────────────────────────────────────────────────────
# APP & MIDDLEWARE
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
executor = ThreadPoolExecutor(max_workers=4)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
WSL_BASE_PATH = Path(r"\\wsl.localhost\Ubuntu\home\rawannada\graduation_infra\backend-node")

# Add each worker machine IP here when they run worker_server.py
WORKER_URLS: List[str] = ["http://192.168.1.150:8001"]

vector_stores: Dict[str, VectorStore] = {}
vs_building:   set                    = set()
_vs_lock                              = threading.Lock()

# ─────────────────────────────────────────────────────────────────────────────
# REQUEST MODELS
# �极───────────────────────────────────────────────────────────────────────────
class SummarizeRequest(BaseModel):
    filePath: str
    fileId:   str = None

class QuestionRequest(BaseModel):
    filePath: str
    question: str
    fileId:   str = None

# ─────────────────────────────────────────────────────────────────────────────
# PATH RESOLVER
# ─────────────────────────────────────────────────────────────────────────────
def _get_clean_path(raw_path: str) -> Path:
    p = Path(raw_path)
    if "uploads" in p.parts:
        idx           = p.parts.index("uploads")
        relative_path = Path(*p.parts[idx:])
    else:
        relative_path = Path("uploads") / p.name

    file_path = WSL_BASE_PATH / relative_path
    if not file_path.exists():
        if Path(raw_path).exists():
            return Path(raw_path)
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    return file_path

# ─────────────────────────────────────────────────────────────────────────────
# CHUNK SPLITTER
# ─────────────────────────────────────────────────────────────────────────────
def _split_chunks(total_chunks: int, num_workers: int) -> List[tuple]:
    chunk_size = total_chunks // num_workers
    ranges, start = [], 0
    for i in range(num_workers):
        end = start + chunk_size if i < num_workers - 1 else total_chunks
        ranges.append((start, end))
        start = end
    return ranges

# ─────────────────────────────────────────────────────────────────────────────
# LOCAL CHUNK PROCESSOR
# ─────────────────────────────────────────────────────────────────────────────
def _process_chunks_locally(chunks: List[dict]) -> dict:
    from embeddings import EmbeddingGenerator
    
    # Try to import PDFSummarizer if available
    try:
        from pdf_summarizer.src.summarizer import PDFSummarizer
        summarizer_available = True
    except ImportError:
        summarizer_available = False

    logger.info(f"[LOCAL] Processing {len(chunks)} chunks locally...")

    if not chunks:
        logger.warning(f"[LOCAL] WARNING: No chunks provided. Returning empty package.")
        return {"vectors": [], "chunks": []}

    logger.info(f"[LOCAL] STEP 1/3 — Generating embeddings via Ollama...")
    emb_gen    = EmbeddingGenerator(max_workers=4)
    texts      = [c["text"] for c in chunks]
    embeddings = emb_gen.embed_documents(texts)
    emb_np     = np.array(embeddings).astype("float32")
    logger.info(f"[LOCAL] Embeddings shape: {emb_np.shape} | dtype: {emb_np.dtype}")

    logger.info(f"[LOCAL] STEP 2/3 — Normalizing vectors...")
    norms             = np.linalg.norm(emb_np, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normalized        = emb_np / norms
    logger.info(f"[LOCAL] Normalization done. Shape: {normalized.shape}")

    # Generate summary if summarizer is available
    summary = ""
    if summarizer_available:
        logger.info(f"[LOCAL] STEP 3/3 — Generating summary...")
        try:
            summarizer = PDFSummarizer()
            summary_text, _ = summarizer.summarize_text_with_ollama(
                text_chunks=texts,
                model_name=summarizer.model_name,
                temperature=0.1,
                max_tokens=512
            )
            summary = summary_text or ""
            logger.info(f"[LOCAL] Summary generated. Length: {len(summary)} characters")
        except Exception as e:
            logger.error(f"[LOCAL] ERROR: Summary generation failed — {str(e)}")
    else:
        logger.info(f"[LOCAL] STEP 3/3 — Skipping summary (summarizer not available)")

    return {
        "vectors": normalized,
        "chunks": chunks,
        "summary": summary
    }

# ─────────────────────────────────────────────────────────────────────────────
# REMOTE WORKER CALLER
# ─────────────────────────────────────────────────────────────────────────────
async def _call_worker_process_chunks(
    worker_url: str,
    chunks: List[dict]
) -> dict:
    logger.info(f"[WORKER] Sending {len(chunks)} chunks to worker: {worker_url}")
    async with httpx.AsyncClient(timeout=1200) as client:
        try:
            response = await client.post(
                f"{worker_url}/process_chunks",
                json={"chunks": chunks}
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"[WORKER] Response received from {worker_url} with {result.get('vector_count', 0)} vectors and {len(result.get('summary', ''))} summary chars")
                
                # Validate vectors
                if result.get("vectors"):
                    vecs = np.array(result["vectors"], dtype=np.float32)
                    if vecs.ndim != 2:
                        logger.error(f"[WORKER] ERROR: Non-2D vectors from {worker_url}. Skipping.")
                        return {}
                    result["vectors"] = vecs
                return result

            logger.error(f"[WORKER] ERROR: HTTP {response.status_code} from {worker_url}. Skipping.")
            return {}

        except Exception as e:
            logger.error(f"[WORKER] ERROR: Could not reach worker {worker_url} — {str(e)}")
            return {}

# ─────────────────────────────────────────────────────────────────────────────
# DISTRIBUTE & BUILD
# Step 1 — Extract all chunks
# Step 2 — Check available workers
# Step 3 — Split chunks across workers
# Step 4 — Launch tasks in parallel
# Step 5 — Collect and validate results
# Step 6 — Combine summaries in order
# Step 7 — Build FAISS index
# ─────────────────────────────────────────────────────────────────────────────
async def _distribute_and_build(file_path: Path, cache_key: str) -> None:
    try:
        logger.info("=" * 60)
        logger.info(f"[MANAGER] Starting distributed build for cache key: {cache_key}")

        logger.info(f"[MANAGER] STEP 1/7 — Extracting all text chunks...")
        processor = PDFProcessor(str(file_path))
        all_chunks = processor.process_pdf(use_ocr=False, use_sections=True)
        total_chunks = len(all_chunks)
        
        # Determine actual number of available workers
        available_workers = []
        for url in WORKER_URLS:
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    response = await client.get(f"{url}/health")
                    if response.status_code == 200:
                        available_workers.append(url)
            except:
                pass
        
        num_nodes = len(available_workers)  # Only workers, master is coordinator only
        logger.info(f"[MANAGER] Total chunks: {total_chunks} | Available workers: {num_nodes}")

        if not available_workers:
            logger.info("[MANAGER] WARNING: No workers available. Processing entire file locally.")
            # Fallback to local processing
            result = await asyncio.get_event_loop().run_in_executor(
                executor,
                _process_chunks_locally,
                all_chunks
            )
            
            # Build index from local result
            master_vs = VectorStore(max_workers=4)
            master_vs.build_from_distributed(
                all_vectors=[result["vectors"]],
                all_chunks=result["chunks"],
                cache_source=cache_key,
            )
            
            # Register store
            with _vs_lock:
                vector_stores[cache_key] = master_vs
                master_vs.summary = result["summary"]
                
            logger.info(f"[MANAGER] Local build COMPLETE for key: {cache_key}")
            logger.info("=" * 60)
            return
        
        # Split chunks based on actual node count
        chunk_ranges = _split_chunks(total_chunks, num_nodes)
        
        logger.info(f"[MANAGER] STEP 2/7 — Splitting chunks across workers...")
        for i, (s, e) in enumerate(chunk_ranges):
            logger.info(f"[MANAGER] Worker-{i+1} assigned chunks {s} -> {e} ({e - s} chunks)")

        logger.info(f"[MANAGER] STEP 3/7 — Launching all tasks in parallel...")
        worker_tasks = []
        loop = asyncio.get_event_loop()
        
        # Create tasks for each worker
        for i, (start_idx, end_idx) in enumerate(chunk_ranges):
            worker_url = available_workers[i]
            worker_chunks = all_chunks[start_idx:end_idx]
            task = _call_worker_process_chunks(worker_url, worker_chunks)
            worker_tasks.append(task)
        
        logger.info(f"[MANAGER] Waiting for tasks to finish...")
        worker_results = await asyncio.gather(*worker_tasks)
        
        logger.info(f"[MANAGER] All tasks finished. Starting merge...")

        logger.info(f"[MANAGER] STEP 4/7 — Collecting and validating packages from all nodes...")
        all_vectors: List[np.ndarray] = []
        all_chunks:  List[dict]       = []
        all_summaries: List[str]      = []

        # Process worker results
        for i, res in enumerate(worker_results):
            worker_label = f"Worker-{i+1} ({available_workers[i]})"

            if not res or "vectors" not in res:
                logger.warning(f"[MANAGER] WARNING: {worker_label} failed. Falling back to local build...")
                start_idx, end_idx = chunk_ranges[i]
                worker_chunks = all_chunks[start_idx:end_idx]
                res = await loop.run_in_executor(
                    executor,
                    _process_chunks_locally,
                    worker_chunks
                )

            if "vectors" in res:
                vecs = res["vectors"]
                if isinstance(vecs, np.ndarray) and vecs.ndim == 2 and vecs.shape[0] > 0:
                    all_vectors.append(vecs)
                    all_chunks.extend(res.get("chunks", []))
                    all_summaries.append(res.get("summary", ""))
                    logger.info(f"[MANAGER] {worker_label} accepted: {vecs.shape[0]} vectors and {len(res.get('summary', ''))} summary chars")
                else:
                    logger.error(f"[MANAGER] ERROR: {worker_label} returned invalid vector format")
            else:
                logger.error(f"[MANAGER] ERROR: {worker_label} result missing vectors")

        if not all_vectors:
            logger.error("[MANAGER] ERROR: No valid vectors collected. Build aborted.")
            return

        logger.info(f"[MANAGER] STEP 5/7 — Combining summaries in chunk order...")
        # ترتيب الأجزاء قبل الدمج
        ordered_chunks = sorted(all_chunks, key=lambda x: x['page_num'])
        full_summary = "\n\n".join([chunk['summary'] for chunk in ordered_chunks])
        logger.info(f"[MANAGER] Combined summary length: {len(full_summary)} characters")

        logger.info(f"[MANAGER] STEP 6/7 — Building FAISS index from all vectors...")
        master_vs = VectorStore(max_workers=4)
        master_vs.build_from_distributed(
            all_vectors=all_vectors,
            all_chunks=all_chunks,
            cache_source=cache_key,
        )
        logger.info(f"[MANAGER] FAISS index built successfully.")

        logger.info(f"[MANAGER] STEP 7/7 — Registering store in memory...")
        with _vs_lock:
            vector_stores[cache_key] = master_vs
            # Store summary separately
            master_vs.summary = full_summary

        logger.info(f"[MANAGER] Build COMPLETE. Store registered for key: {cache_key} | "
                    f"Total chunks: {len(all_chunks)} | Summary length: {len(full_summary)}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"[MANAGER] ERROR: Distributed build crashed — {str(e)}", exc_info=True)
    finally:
        with _vs_lock:
            vs_building.discard(cache_key)

# ─────────────────────────────────────────────────────────────────────────────
# DISTRIBUTED SUMMARIZATION
# ─────────────────────────────────────────────────────────────────────────────
async def _distribute_summarization(file_path: Path, total_pages: int) -> str:
    logger.info("=" * 60)
    logger.info(f"[MANAGER] Starting distributed summarization for file: {file_path.name}")
    
    # Determine available workers
    available_workers = []
    for url in WORKER_URLS:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{url}/health")
                if response.status_code == 200:
                    available_workers.append(url)
        except:
            pass
    
    num_workers = len(available_workers)
    logger.info(f"[MANAGER] Available workers for summarization: {num_workers}")
    
    if not available_workers:
        logger.info("[MANAGER] WARNING: No workers available. Summarizing locally.")
        return await _summarize_locally(file_path)
    
    # Split pages among workers
    pages_per_worker = total_pages // num_workers
    remainder = total_pages % num_workers
    
    page_ranges = []
    start = 0
    for i in range(num_workers):
        end = start + pages_per_worker - 1
        if i < remainder:
            end += 1
        page_ranges.append((start, end))
        start = end + 1
    
    logger.info(f"[MANAGER] Page ranges for summarization: {page_ranges}")
    
    # Create tasks
    summarization_tasks = []
    for i, (start_page, end_page) in enumerate(page_ranges):
        worker_url = available_workers[i]
        task = _call_worker_summarize(worker_url, file_path, start_page, end_page)
        summarization_tasks.append(task)
    
    logger.info("[MANAGER] Distributing summarization tasks to workers...")
    partial_summaries = await asyncio.gather(*summarization_tasks)
    
    # Combine summaries while preserving order
    full_summary = "\n\n".join(partial_summaries)
    logger.info(f"[MANAGER] Combined summary length: {len(full_summary)} characters")
    logger.info("=" * 60)
    
    return full_summary

# ─────────────────────────────────────────────────────────────────────────────
# LOCAL SUMMARIZATION FALLBACK
# ─────────────────────────────────────────────────────────────────────────────
async def _summarize_locally(file_path: Path) -> str:
    logger.info("[MANAGER] Starting local summarization...")
    processor = PDFProcessor(str(file_path))
    pages_data = processor.process_pdf(use_ocr=False, use_sections=True)
    
    text_chunks = []
    for page in pages_data:
        if page["text"].strip():
            text_chunks.extend(split_into_chunks(page["text"], max_words=200))
    
    if not text_chunks:
        return ""
    
    summarizer = PDFSummarizer()
    summary, _ = summarizer.summarize_text_with_ollama(
        text_chunks=text_chunks,
        model_name=summarizer.model_name,
        temperature=0.1,
        max_tokens=512
    )
    
    logger.info(f"[MANAGER] Local summarization complete. Length: {len(summary)} characters")
    return summary

# ─────────────────────────────────────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────────────────────────────────────
@app.on_event("startup")
def _preload_caches() -> None:
    def _load_all():
        logger.info("[STARTUP] Server starting — scanning cache directory...")
        index_files = list(CACHE_DIR.glob("*.index"))
        logger.info(f"[STARTUP] Found {len(index_files)} cached index files in {CACHE_DIR}")
        for index_file in index_files:
            try:
                cache_id = index_file.stem
                vs = VectorStore(max_workers=4)
                if vs.load(cache_id):
                    with _vs_lock:
                        vector_stores[cache_id] = vs
                    logger.info(f"[STARTUP] Loaded: {index_file.name} ({len(vs.documents)} chunks)")
                else:
                    logger.warning(f"[STARTUP] WARNING: Failed to load {index_file.name}")
            except Exception as e:
                logger.warning(f"[STARTUP] WARNING: Error loading {index_file.name} — {str(e)}")
        logger.info(f"[STARTUP] Complete. {len(vector_stores)} stores ready in memory.")

    threading.Thread(target=_load_all, daemon=True).start()

# ─────────────────────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {"status": "healthy", "nodes_loaded": len(vector_stores)}


@app.post("/api/summarize")
async def summarize(request: SummarizeRequest):
    logger.info("=" * 60)
    logger.info("[SUMMARIZE] New summarize request received.")
    try:
        file_path = _get_clean_path(request.filePath)
        cache_key = request.fileId if request.fileId else _cache_key(str(file_path))
        logger.info(f"[SUMMARIZE] File: {file_path.name} | Cache key: {cache_key}")

        logger.info("[SUMMARIZE] Starting PDF summarization...")
        summarizer     = PDFSummarizer()
        summary_result = summarizer.summarize(str(file_path))
        logger.info(f"[SUMMARIZE] Summarization done. Length: {len(summary_result)} characters.")

        with _vs_lock:
            if cache_key not in vector_stores and cache_key not in vs_building:
                vs_building.add(cache_key)
                logger.info(f"[SUMMARIZE] Vector store not found. Launching background build for: {cache_key}")
                asyncio.create_task(_distribute_and_build(file_path, cache_key))
            else:
                logger.info(f"[SUMMARIZE] Vector store already exists or is being built for: {cache_key}")

        return {
            "status":   "success",
            "summary":  summary_result,
            "metadata": {"filename": file_path.name, "cache_key": cache_key},
        }
    except Exception as e:
        logger.error(f"[SUMMARIZE] ERROR: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ask")
async def ask(request: QuestionRequest):
    logger.info("=" * 60)
    logger.info("[ASK] New question request received.")
    try:
        if not request.question.strip():
            raise HTTPException(status_code=400, detail="Empty question")

        file_path = _get_clean_path(request.filePath)
        cache_key = request.fileId if request.fileId else _cache_key(str(file_path))
        logger.info(f"[ASK] File: {file_path.name} | Cache key: {cache_key}")
        logger.info(f"[ASK] Question: {request.question}")

        wait = 0
        while cache_key in vs_building and wait < 60:
            logger.info(f"[ASK] Vector store is still building for {cache_key}... waiting ({wait}s)")
            await asyncio.sleep(1)
            wait += 1

        if cache_key not in vector_stores:
            logger.info(f"[ASK] Store not in memory. Trying to load from disk...")
            vs = VectorStore(max_workers=4)
            if vs.load(cache_key):
                with _极vs_lock:
                    vector_stores[cache_key] = vs
                logger.info(f"[ASK] Successfully loaded from disk: {cache_key}")
            else:
                logger.info(f"[ASK] Not on disk. Triggering full distributed build...")
                with _vs_lock:
                    vs_building.add(cache_key)
                await _distribute_and_build(file_path, cache_key)

        if cache_key not in vector_stores:
            logger.error(f"[ASK] ERROR: Vector store could not be initialized for {cache_key}")
            raise HTTPException(status_code=500, detail="Vector Store initialization failed")

        logger.info(f"[ASK] Store ready. Running RAG pipeline...")
        rag    = RAGPipeline(vector_store=vector_stores[cache_key])
        loop   = asyncio.get_event_loop()
        result = await loop.run_in_executor(executor, rag.query, request.question)

        logger.info(f"[ASK] Answer generated. Sources found: {len(result.get('sources', []))}")
        return {
            "status":  "success",
            "answer":  result.get("answer", ""),
            "sources": result.get("sources", []),
        }
    except Exception as e:
        logger.error(f"[ASK] ERROR: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    