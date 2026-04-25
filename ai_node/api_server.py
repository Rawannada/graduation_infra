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
# ─────────────────────────────────────────────────────────────────────────────
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
# PAGE SPLITTER
# ─────────────────────────────────────────────────────────────────────────────
def _split_pages(total_pages: int, num_workers: int) -> List[tuple]:
    chunk_size = total_pages // num_workers
    ranges, start = [], 0
    for i in range(num_workers):
        end = start + chunk_size if i < num_workers - 1 else total_pages
        ranges.append((start, end))
        start = end
    return ranges

# ─────────────────────────────────────────────────────────────────────────────
# LOCAL PARTIAL BUILD
# Processes a specific page range locally.
# Used both for the manager's own assigned range AND as fallback
# when a remote worker fails or is unreachable.
# ─────────────────────────────────────────────────────────────────────────────
def _build_local_partial(file_path: Path, start: int, end: int) -> dict:
    from embeddings import EmbeddingGenerator

    logger.info(f"[LOCAL] STEP 1/5 — Starting local build for pages {start}-{end}...")

    logger.info(f"[LOCAL] STEP 2/5 — Extracting text from pages {start}-{end}...")
    processor  = PDFProcessor(str(file_path))
    pages_data = processor.process_pdf(
        use_ocr=False, use_sections=True,
        start_page=start, end_page=end
    )
    logger.info(f"[LOCAL] Extracted {len(pages_data)} sections.")

    logger.info(f"[LOCAL] STEP 3/5 — Splitting into chunks (max 100 words each)...")
    chunked_data = []
    for section in pages_data:
        for chunk in split_into_chunks(section["text"], max_words=100):
            chunked_data.append({
                "text":          chunk,
                "filename":      section["filename"],
                "page_num":      section["page_num"],
                "section_title": section.get("section_title", ""),
            })
    logger.info(f"[LOCAL] Total chunks ready: {len(chunked_data)}")

    if not chunked_data:
        logger.warning(f"[LOCAL] WARNING: No text found in pages {start}-{end}. Returning empty package.")
        return {"vectors": [], "chunks": []}

    logger.info(f"[LOCAL] STEP 4/5 — Generating embeddings via Ollama...")
    emb_gen    = EmbeddingGenerator(max_workers=4)
    texts      = [c["text"] for c in chunked_data]
    embeddings = emb_gen.embed_documents(texts)
    emb_np     = np.array(embeddings).astype("float32")
    logger.info(f"[LOCAL] Embeddings shape: {emb_np.shape} | dtype: {emb_np.dtype}")

    logger.info(f"[LOCAL] STEP 5/5 — Normalizing vectors...")
    norms             = np.linalg.norm(emb_np, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normalized        = emb_np / norms
    logger.info(f"[LOCAL] Normalization done. Shape: {normalized.shape}")

    logger.info(f"[LOCAL] Task COMPLETE. {len(chunked_data)} chunks ready for merge.")
    return {"vectors": normalized, "chunks": chunked_data}

# ─────────────────────────────────────────────────────────────────────────────
# REMOTE WORKER CALLER
# ─────────────────────────────────────────────────────────────────────────────
async def _call_worker_vectorize(
    worker_url: str,
    file_path:  Path,
    start:      int,
    end:        int
) -> dict:
    logger.info(f"[WORKER] Sending pages {start}-{end} to worker: {worker_url}")
    async with httpx.AsyncClient(timeout=600) as client:
        try:
            with open(file_path, "rb") as f:
                files    = {"file": (file_path.name, f, "application/pdf")}
                data     = {"startPage": str(start), "endPage": str(end)}
                response = await client.post(f"{worker_url}/process", files=files, data=data)

            if response.status_code == 200:
                result = response.json()
                logger.info(f"[WORKER] Response received from {worker_url}. Validating vectors...")
                if result.get("vectors"):
                    vecs = np.array(result["vectors"], dtype=np.float32)
                    if vecs.ndim != 2:
                        logger.error(f"[WORKER] ERROR: Non-2D vectors from {worker_url}. Skipping.")
                        return {}
                    result["vectors"] = vecs
                    logger.info(f"[WORKER] Vectors validated. Shape: {vecs.shape} from {worker_url}")
                else:
                    logger.warning(f"[WORKER] WARNING: Empty vectors from {worker_url}.")
                return result

            logger.error(f"[WORKER] ERROR: HTTP {response.status_code} from {worker_url}. Skipping.")
            return {}

        except Exception as e:
            logger.error(f"[WORKER] ERROR: Could not reach worker {worker_url} — {str(e)}")
            return {}

# ─────────────────────────────────────────────────────────────────────────────
# DISTRIBUTE & BUILD
# Step 1 — Count total pages
# Step 2 — Split pages across all nodes (workers + local)
# Step 3 — Launch all tasks in parallel
# Step 4 — Collect results; if a worker fails → fallback to local build
# Step 5 — Build one FAISS index from all vectors
# Step 6 — Save and register in memory
# ─────────────────────────────────────────────────────────────────────────────
async def _distribute_and_build(file_path: Path, cache_key: str) -> None:
    try:
        logger.info("=" * 60)
        logger.info(f"[MANAGER] Starting distributed build for cache key: {cache_key}")

        logger.info(f"[MANAGER] STEP 1/6 — Counting total pages in PDF...")
        reader      = PdfReader(str(file_path))
        total_pages = len(reader.pages)
        num_total   = len(WORKER_URLS) + 1
        logger.info(f"[MANAGER] Total pages: {total_pages} | Total nodes: {num_total} ({len(WORKER_URLS)} remote + 1 local)")

        logger.info(f"[MANAGER] STEP 2/6 — Splitting pages across nodes...")
        page_ranges = _split_pages(total_pages, num_total)
        for i, (s, e) in enumerate(page_ranges):
            node_label = f"Worker-{i+1}" if i < len(WORKER_URLS) else "Local"
            logger.info(f"[MANAGER] {node_label} assigned pages {s} -> {e} ({e - s} pages)")

        logger.info(f"[MANAGER] STEP 3/6 — Launching all tasks in parallel...")

        worker_tasks = [
            _call_worker_vectorize(url, file_path, r[0], r[1])
            for url, r in zip(WORKER_URLS, page_ranges)
        ]

        loop       = asyncio.get_event_loop()
        local_task = loop.run_in_executor(
            executor,
            _build_local_partial,
            file_path,
            page_ranges[-1][0],
            page_ranges[-1][1],
        )

        logger.info(f"[MANAGER] Waiting for all nodes to finish...")
        worker_results = await asyncio.gather(*worker_tasks)
        local_result   = await local_task
        logger.info(f"[MANAGER] All nodes finished. Starting merge...")

        logger.info(f"[MANAGER] STEP 4/6 — Collecting and validating packages from all nodes...")
        all_vectors: List[np.ndarray] = []
        all_chunks:  List[dict]       = []

        # Collect local result
        local_vecs = local_result.get("vectors")
        if local_vecs is not None and isinstance(local_vecs, np.ndarray):
            if local_vecs.ndim == 2 and local_vecs.shape[0] > 0:
                all_vectors.append(local_vecs)
                all_chunks.extend(local_result["chunks"])
                logger.info(f"[MANAGER] Local result accepted: {local_vecs.shape[0]} vectors.")
            else:
                logger.warning(f"[MANAGER] WARNING: Local result invalid shape. Skipping.")
        else:
            logger.warning(f"[MANAGER] WARNING: Local build returned no vectors.")

        # Collect worker results — fallback to local build if worker failed
        for i, res in enumerate(worker_results):
            worker_label = f"Worker-{i+1} ({WORKER_URLS[i]})"
            worker_start = page_ranges[i][0]
            worker_end   = page_ranges[i][1]

            vecs = res.get("vectors") if res else None

            # ── FALLBACK: worker failed → build its pages locally ──
            if vecs is None or (isinstance(vecs, np.ndarray) and vecs.shape[0] == 0):
                logger.warning(
                    f"[MANAGER] WARNING: {worker_label} failed or returned empty result. "
                    f"Falling back to local build for pages {worker_start}-{worker_end}..."
                )
                fallback = await loop.run_in_executor(
                    executor,
                    _build_local_partial,
                    file_path,
                    worker_start,
                    worker_end,
                )
                fallback_vecs = fallback.get("vectors")
                if (
                    fallback_vecs is not None
                    and isinstance(fallback_vecs, np.ndarray)
                    and fallback_vecs.ndim == 2
                    and fallback_vecs.shape[0] > 0
                ):
                    all_vectors.append(fallback_vecs)
                    all_chunks.extend(fallback["chunks"])
                    logger.info(
                        f"[MANAGER] Fallback for {worker_label} complete: "
                        f"{fallback_vecs.shape[0]} vectors from pages {worker_start}-{worker_end}."
                    )
                else:
                    logger.error(f"[MANAGER] ERROR: Fallback also returned no vectors for pages {worker_start}-{worker_end}.")
                continue

            if not isinstance(vecs, np.ndarray):
                vecs = np.array(vecs, dtype=np.float32)

            if vecs.ndim == 2 and vecs.shape[0] > 0:
                all_vectors.append(vecs)
                all_chunks.extend(res.get("chunks", []))
                logger.info(f"[MANAGER] {worker_label} accepted: {vecs.shape[0]} vectors.")
            else:
                logger.error(f"[MANAGER] ERROR: {worker_label} returned invalid shape {vecs.shape}.")

        if not all_vectors:
            logger.error("[MANAGER] ERROR: No valid vectors collected from any node. Build aborted.")
            return

        logger.info(f"[MANAGER] All packages collected. Total chunks: {len(all_chunks)} | Total vector batches: {len(all_vectors)}")

        logger.info(f"[MANAGER] STEP 5/6 — Building FAISS index from all vectors (single vstack)...")
        master_vs = VectorStore(max_workers=4)
        master_vs.build_from_distributed(
            all_vectors=all_vectors,
            all_chunks=all_chunks,
            cache_source=cache_key,
        )
        logger.info(f"[MANAGER] FAISS index built successfully.")

        logger.info(f"[MANAGER] STEP 6/6 — Registering store in memory...")
        with _vs_lock:
            vector_stores[cache_key] = master_vs

        logger.info(f"[MANAGER] Build COMPLETE. Store registered for key: {cache_key} | Total chunks indexed: {len(all_chunks)}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"[MANAGER] ERROR: Distributed build crashed — {str(e)}", exc_info=True)
    finally:
        with _vs_lock:
            vs_building.discard(cache_key)

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
                with _vs_lock:
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
