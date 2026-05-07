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
WORKER_URLS: List[str] = ["http://192.168.1.150:8001"]

vector_stores: Dict[str, VectorStore] = {}
vs_building:   set                    = set()
_vs_lock                              = threading.Lock()  # was originally named with a stray unicode char before vs_lock

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

    try:
        from pdf_summarizer.src.summarizer import PDFSummarizer
        summarizer_available = True
    except ImportError:
        summarizer_available = False

    logger.info(f"[LOCAL] Processing {len(chunks)} chunks locally...")

    if not chunks:
        logger.warning("[LOCAL] WARNING: No chunks provided. Returning empty package.")
        return {"vectors": np.empty((0, 768), dtype="float32"), "chunks": [], "summary": ""}

    logger.info("[LOCAL] STEP 1/3 — Generating embeddings via Ollama...")
    emb_gen    = EmbeddingGenerator(max_workers=4)
    texts      = [c["text"] for c in chunks]
    embeddings = emb_gen.embed_documents(texts)
    emb_np     = np.array(embeddings).astype("float32")
    logger.info(f"[LOCAL] Embeddings shape: {emb_np.shape}")

    logger.info("[LOCAL] STEP 2/3 — Normalizing vectors...")
    norms             = np.linalg.norm(emb_np, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normalized        = emb_np / norms
    logger.info(f"[LOCAL] Normalization done. Shape: {normalized.shape}")

    summary = ""
    if summarizer_available:
        logger.info("[LOCAL] STEP 3/3 — Generating summary...")
        try:
            summarizer   = PDFSummarizer()
            summary, _   = summarizer.summarize_text_with_ollama(
                text_chunks=texts,
                model_name=summarizer.model_name,
                temperature=0.1,
                max_tokens=512
            )
            logger.info(f"[LOCAL] Summary generated. Length: {len(summary)} characters")
        except Exception as e:
            logger.error(f"[LOCAL] ERROR: Summary generation failed — {str(e)}")
    else:
        logger.info("[LOCAL] STEP 3/3 — Skipping summary (summarizer not available)")

    return {"vectors": normalized, "chunks": chunks, "summary": summary}

# ─────────────────────────────────────────────────────────────────────────────
# REMOTE WORKER CALLER
# BUG FIX 2: worker endpoint was /process_chunks but worker_server.py exposes /process
# Changed to POST /process with multipart form (file + startPage + endPage)
# because worker_server.py accepts UploadFile not JSON chunks
# ─────────────────────────────────────────────────────────────────────────────
async def _call_worker_process_chunks(
    worker_url:  str,
    chunks:      List[dict],
    file_path:   Path,
    start_page:  int,
    end_page:    int
) -> dict:
    logger.info(f"[WORKER] Sending pages {start_page}-{end_page} to worker: {worker_url}")
    try:
        with open(file_path, "rb") as f:
            pdf_bytes = f.read()

        async with httpx.AsyncClient(timeout=1200) as client:
            response = await client.post(
                f"{worker_url}/process",
                data={"startPage": start_page, "endPage": end_page, "task_type": "both"},
                files={"file": (file_path.name, pdf_bytes, "application/pdf")},
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(
                    f"[WORKER] Response from {worker_url}: "
                    f"{len(result.get('vectors', []))} vectors | "
                    f"{len(result.get('summary', ''))} summary chars"
                )
                if result.get("vectors"):
                    vecs = np.array(result["vectors"], dtype=np.float32)
                    if vecs.ndim != 2:
                        logger.error(f"[WORKER] Non-2D vectors from {worker_url}. Skipping.")
                        return {}
                    result["vectors"] = vecs
                return result

            logger.error(f"[WORKER] HTTP {response.status_code} from {worker_url}. Skipping.")
            return {}

    except Exception as e:
        logger.error(f"[WORKER] Could not reach {worker_url} — {str(e)}")
        return {}

# ─────────────────────────────────────────────────────────────────────────────
# HEALTH CHECK HELPER
# ─────────────────────────────────────────────────────────────────────────────
async def _get_available_workers() -> List[str]:
    # BUG FIX 3: health check was hitting /health but worker exposes GET /
    available = []
    for url in WORKER_URLS:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{url}/")   # worker root = health check
                if response.status_code == 200:
                    available.append(url)
        except Exception:
            pass
    return available

# ─────────────────────────────────────────────────────────────────────────────
# DISTRIBUTE & BUILD
# ─────────────────────────────────────────────────────────────────────────────
async def _distribute_and_build(file_path: Path, cache_key: str) -> None:
    try:
        logger.info("=" * 60)
        logger.info(f"[MANAGER] Starting distributed build for cache key: {cache_key}")

        # STEP 1: Extract all chunks from the full PDF
        logger.info("[MANAGER] STEP 1/7 — Extracting all text chunks...")
        processor         = PDFProcessor(str(file_path))
        original_chunks   = processor.process_pdf(use_ocr=False, use_sections=True)  # BUG FIX 4: renamed to original_chunks to avoid shadowing
        total_chunks      = len(original_chunks)

        # STEP 2: Discover available workers
        available_workers = await _get_available_workers()
        num_nodes         = len(available_workers)
        logger.info(f"[MANAGER] Total chunks: {total_chunks} | Available workers: {num_nodes}")

        # ── NO WORKERS: full local fallback ────────────────────────────────
        if not available_workers:
            logger.info("[MANAGER] WARNING: No workers available. Processing locally.")
            result = await asyncio.get_event_loop().run_in_executor(
                executor, _process_chunks_locally, original_chunks
            )
            master_vs = VectorStore(max_workers=4)
            master_vs.build_from_distributed(
                all_vectors=[result["vectors"]],
                all_chunks=result["chunks"],
                cache_source=cache_key,
            )
            with _vs_lock:
                vector_stores[cache_key] = master_vs
                master_vs.summary        = result["summary"]
            logger.info(f"[MANAGER] Local build COMPLETE for key: {cache_key}")
            logger.info("=" * 60)
            return

        # STEP 3: Compute page ranges (not chunk ranges) to send to workers
        reader      = PdfReader(str(file_path))
        total_pages = len(reader.pages)
        chunk_ranges  = _split_chunks(total_pages, num_nodes)   # page-level split for workers
        logger.info("[MANAGER] STEP 2/7 — Page ranges per worker:")
        for i, (s, e) in enumerate(chunk_ranges):
            logger.info(f"  Worker-{i+1}: pages {s} → {e}")

        # STEP 4: Launch worker tasks in parallel
        logger.info("[MANAGER] STEP 3/7 — Launching all tasks in parallel...")
        worker_tasks = [
            _call_worker_process_chunks(
                worker_url  = available_workers[i],
                chunks      = [],           # workers extract their own chunks from the PDF
                file_path   = file_path,
                start_page  = s,
                end_page    = e,
            )
            for i, (s, e) in enumerate(chunk_ranges)
        ]
        worker_results = await asyncio.gather(*worker_tasks)
        logger.info("[MANAGER] All tasks finished. Starting merge...")

        # STEP 5: Collect & validate — with per-worker fallback
        # BUG FIX 5: renamed collector lists to avoid shadowing original_chunks
        all_vectors:   List[np.ndarray] = []
        all_flat_chunks: List[dict]     = []
        all_summaries: List[str]        = []

        loop = asyncio.get_event_loop()
        for i, res in enumerate(worker_results):
            worker_label  = f"Worker-{i+1} ({available_workers[i]})"
            s, e          = chunk_ranges[i]

            # Per-worker fallback: if worker failed, process its page range locally
            if not res or "vectors" not in res:
                logger.warning(f"[MANAGER] {worker_label} failed. Local fallback for pages {s}→{e}...")
                # BUG FIX 6: use original_chunks filtered by page range instead of empty all_flat_chunks
                # s and e are 0-based page indices from _split_chunks, but page_num is 1-based
                # Worker processes range(s,e) = pages s+1..e, so filter is s < page_num <= e
                fallback_chunks = [c for c in original_chunks if s < c.get("page_num", 0) <= e]
                res = await loop.run_in_executor(
                    executor, _process_chunks_locally, fallback_chunks
                )

            if "vectors" in res:
                vecs = res["vectors"]
                if isinstance(vecs, np.ndarray) and vecs.ndim == 2 and vecs.shape[0] > 0:
                    all_vectors.append(vecs)
                    all_flat_chunks.extend(res.get("chunks", []))
                    all_summaries.append(res.get("summary", ""))
                    logger.info(f"[MANAGER] {worker_label} accepted: {vecs.shape[0]} vectors")
                else:
                    logger.error(f"[MANAGER] {worker_label} returned invalid vector format")
            else:
                logger.error(f"[MANAGER] {worker_label} result missing vectors")

        if not all_vectors:
            logger.error("[MANAGER] No valid vectors collected. Build aborted.")
            return

        # STEP 6: Merge summaries — BUG FIX 7: use all_summaries list not chunk['summary']
        # original code tried chunk['summary'] which doesn't exist on PDFProcessor output
        logger.info("[MANAGER] STEP 5/7 — Combining summaries...")
        full_summary = "\n\n".join(s for s in all_summaries if s and s.strip())
        logger.info(f"[MANAGER] Combined summary length: {len(full_summary)} characters")

        # STEP 7: Build FAISS index
        logger.info("[MANAGER] STEP 6/7 — Building FAISS index...")
        master_vs = VectorStore(max_workers=4)
        master_vs.build_from_distributed(
            all_vectors  = all_vectors,
            all_chunks   = all_flat_chunks,
            cache_source = cache_key,
        )

        # STEP 8: Register in memory
        logger.info("[MANAGER] STEP 7/7 — Registering store in memory...")
        with _vs_lock:
            vector_stores[cache_key] = master_vs
            master_vs.summary        = full_summary

        logger.info(
            f"[MANAGER] Build COMPLETE. key={cache_key} | "
            f"chunks={len(all_flat_chunks)} | summary={len(full_summary)} chars"
        )
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"[MANAGER] Distributed build crashed — {str(e)}", exc_info=True)
    finally:
        with _vs_lock:
            vs_building.discard(cache_key)

# ─────────────────────────────────────────────────────────────────────────────
# LOCAL SUMMARIZATION FALLBACK
# ─────────────────────────────────────────────────────────────────────────────
async def _summarize_locally(file_path: Path) -> str:
    logger.info("[MANAGER] Starting local summarization...")
    processor  = PDFProcessor(str(file_path))
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
# STARTUP — preload cached indexes from disk
# ─────────────────────────────────────────────────────────────────────────────
@app.on_event("startup")
def _preload_caches() -> None:
    def _load_all():
        logger.info("[STARTUP] Scanning cache directory...")
        index_files = list(CACHE_DIR.glob("*.index"))
        logger.info(f"[STARTUP] Found {len(index_files)} cached indexes in {CACHE_DIR}")
        for index_file in index_files:
            try:
                cache_id = index_file.stem
                vs       = VectorStore(max_workers=4)
                if vs.load(cache_id):
                    with _vs_lock:
                        vector_stores[cache_id] = vs
                    logger.info(f"[STARTUP] Loaded: {index_file.name} ({len(vs.documents)} chunks)")
                else:
                    logger.warning(f"[STARTUP] Failed to load {index_file.name}")
            except Exception as e:
                logger.warning(f"[STARTUP] Error loading {index_file.name} — {str(e)}")
        logger.info(f"[STARTUP] Complete. {len(vector_stores)} stores ready.")

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
    logger.info("[SUMMARIZE] New request received.")
    try:
        file_path  = _get_clean_path(request.filePath)
        cache_key  = request.fileId if request.fileId else _cache_key(str(file_path))
        logger.info(f"[SUMMARIZE] File: {file_path.name} | Cache key: {cache_key}")

        summarizer     = PDFSummarizer()
        summary_result = summarizer.summarize(str(file_path))
        logger.info(f"[SUMMARIZE] Done. Length: {len(summary_result)} chars.")

        with _vs_lock:
            if cache_key not in vector_stores and cache_key not in vs_building:
                vs_building.add(cache_key)
                logger.info(f"[SUMMARIZE] Launching background vector build for: {cache_key}")
                asyncio.create_task(_distribute_and_build(file_path, cache_key))
            else:
                logger.info(f"[SUMMARIZE] Store already exists/building for: {cache_key}")

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
    logger.info("[ASK] New question received.")
    try:
        if not request.question.strip():
            raise HTTPException(status_code=400, detail="Empty question")

        file_path = _get_clean_path(request.filePath)
        cache_key = request.fileId if request.fileId else _cache_key(str(file_path))
        logger.info(f"[ASK] File: {file_path.name} | Cache key: {cache_key}")
        logger.info(f"[ASK] Question: {request.question}")

        # Wait for build to finish (max 60s)
        wait = 0
        while cache_key in vs_building and wait < 60:
            logger.info(f"[ASK] Store still building... ({wait}s)")
            await asyncio.sleep(1)
            wait += 1

        if cache_key not in vector_stores:
            logger.info("[ASK] Store not in memory. Trying disk...")
            vs = VectorStore(max_workers=4)
            if vs.load(cache_key):
                with _vs_lock:
                    vector_stores[cache_key] = vs
                logger.info(f"[ASK] Loaded from disk: {cache_key}")
            else:
                logger.info("[ASK] Not on disk. Triggering distributed build...")
                with _vs_lock:
                    vs_building.add(cache_key)
                await _distribute_and_build(file_path, cache_key)

        if cache_key not in vector_stores:
            logger.error(f"[ASK] Vector store could not be initialized for {cache_key}")
            raise HTTPException(status_code=500, detail="Vector Store initialization failed")

        logger.info("[ASK] Store ready. Running RAG pipeline...")
        rag    = RAGPipeline(vector_store=vector_stores[cache_key])
        loop   = asyncio.get_event_loop()
        result = await loop.run_in_executor(executor, rag.query, request.question)

        logger.info(f"[ASK] Done. Sources: {len(result.get('sources', []))}")
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
