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
WORKER_URLS: List[str] = ["http://10.40.22.153:8001"]

# What fraction of pages the manager handles (rest goes to workers).
# 0.2 = manager handles 20%, workers share 80%.
# Lower = faster overall, since workers are typically faster at LLM inference.
MANAGER_LOAD_RATIO: float = 0.2

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
# PAGE RANGE SPLITTER
# Splits total_pages across (workers + manager) evenly.
# Example: 57 pages, 1 worker + manager = 2 nodes → [(0,28), (28,57)]
# ─────────────────────────────────────────────────────────────────────────────
def _split_page_ranges(total_pages: int, num_nodes: int) -> List[tuple]:
    chunk_size = total_pages // num_nodes
    ranges, start = [], 0
    for i in range(num_nodes):
        end = start + chunk_size if i < num_nodes - 1 else total_pages
        ranges.append((start, end))
        start = end
    return ranges

# ─────────────────────────────────────────────────────────────────────────────
# MANAGER LOCAL PROCESSOR
# Runs embedding (and optional summarization) on a page range locally.
# Called in an executor thread so it doesn't block the event loop.
# ─────────────────────────────────────────────────────────────────────────────
def _process_pages_locally(
    file_path:        Path,
    start_page:       int,
    end_page:         int,
    existing_summary: str = "",
) -> dict:
    """
    Processes pages [start_page, end_page) on the manager machine itself.
    Returns the same structure that _call_worker returns:
        { "vectors": np.ndarray, "chunks": list[dict], "summary": str }
    """
    from embeddings import EmbeddingGenerator

    try:
        from pdf_summarizer.src.summarizer import PDFSummarizer as _S
        summarizer_available = True
    except ImportError:
        summarizer_available = False

    logger.info(f"[MANAGER-LOCAL] Processing pages {start_page}→{end_page} locally...")

    # ── Extract text ────────────────────────────────────────────────────────
    processor  = PDFProcessor(str(file_path))
    pages_data = processor.process_pdf(
        use_ocr=False,
        use_sections=True,
        start_page=start_page,
        end_page=end_page,
    )

    if not pages_data:
        logger.warning(f"[MANAGER-LOCAL] No text found for pages {start_page}→{end_page}.")
        return {"vectors": np.empty((0, 768), dtype="float32"), "chunks": [], "summary": ""}

    # ── Chunk ────────────────────────────────────────────────────────────────
    chunked_data = []
    for section in pages_data:
        for chunk_text in split_into_chunks(section["text"], max_words=100):
            chunked_data.append({
                "text":          chunk_text,
                "filename":      section.get("filename", file_path.name),
                "page_num":      section.get("page_num", 0),
                "section_title": section.get("section_title", ""),
            })
    logger.info(f"[MANAGER-LOCAL] {len(pages_data)} sections → {len(chunked_data)} chunks")

    # ── Embed ────────────────────────────────────────────────────────────────
    texts      = [c["text"] for c in chunked_data]
    emb_gen    = EmbeddingGenerator(max_workers=4)
    embeddings = emb_gen.embed_documents(texts)
    emb_np     = np.array(embeddings).astype("float32")
    logger.info(f"[MANAGER-LOCAL] Embeddings shape: {emb_np.shape}")

    # ── Normalize ────────────────────────────────────────────────────────────
    norms             = np.linalg.norm(emb_np, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normalized        = emb_np / norms
    logger.info(f"[MANAGER-LOCAL] Normalized shape: {normalized.shape}")

    # ── Summarize (only if no pre-existing summary) ──────────────────────────
    summary = ""
    if existing_summary:
        logger.info("[MANAGER-LOCAL] Pre-existing summary available — skipping local summarization.")
    elif summarizer_available:
        logger.info("[MANAGER-LOCAL] Generating partial summary...")
        try:
            s_engine   = _S()
            summary, _ = s_engine.summarize_text_with_ollama(
                text_chunks=texts,
                model_name=s_engine.model_name,
                temperature=0.1,
                max_tokens=512,
            )
            logger.info(f"[MANAGER-LOCAL] Summary length: {len(summary)} chars")
        except Exception as e:
            logger.error(f"[MANAGER-LOCAL] Summary failed — {e}")

    logger.info(
        f"[MANAGER-LOCAL] DONE. {len(chunked_data)} chunks | "
        f"{normalized.shape[0]} vectors | {len(summary)} summary chars"
    )
    return {"vectors": normalized, "chunks": chunked_data, "summary": summary}

# ─────────────────────────────────────────────────────────────────────────────
# WORKER CALLER
# ─────────────────────────────────────────────────────────────────────────────
async def _call_worker(
    worker_url: str,
    pdf_bytes:  bytes,
    filename:   str,
    start_page: int,
    end_page:   int,
    task_type:  str = "both",
) -> dict:
    logger.info(f"[WORKER] -> {worker_url} | pages {start_page}→{end_page} | task={task_type}")
    try:
        async with httpx.AsyncClient(timeout=1200) as client:
            response = await client.post(
                f"{worker_url}/process",
                data={
                    "startPage": start_page,
                    "endPage":   end_page,
                    "task_type": task_type,
                },
                files={"file": (filename, pdf_bytes, "application/pdf")},
            )

        if response.status_code != 200:
            logger.error(f"[WORKER] HTTP {response.status_code} from {worker_url}")
            return {}

        result   = response.json()
        raw_vecs = result.get("vectors", [])
        if not raw_vecs:
            logger.warning(f"[WORKER] Empty vectors from {worker_url}")
            return {}

        vecs = np.array(raw_vecs, dtype=np.float32)
        if vecs.ndim != 2:
            logger.error(f"[WORKER] Non-2D vectors from {worker_url}. Skipping.")
            return {}

        result["vectors"] = vecs
        logger.info(
            f"[WORKER] OK {worker_url} done | "
            f"{vecs.shape[0]} vectors | "
            f"{len(result.get('summary', ''))} summary chars"
        )
        return result

    except Exception as e:
        logger.error(f"[WORKER] FAILED {worker_url} — {type(e).__name__}: {str(e)}")
        return {}

# ─────────────────────────────────────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────────────────────────────────────
async def _get_available_workers() -> List[str]:
    available = []
    for url in WORKER_URLS:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{url}/")
                logger.info(f"[HEALTH] {url}/ -> status {r.status_code}")
                if r.status_code == 200:
                    available.append(url)
                    logger.info(f"[HEALTH] {url} is AVAILABLE")
        except Exception as e:
            logger.error(f"[HEALTH] {url} -> FAILED: {type(e).__name__}: {str(e)}")
    logger.info(f"[HEALTH] Available workers: {available}")
    return available

# ─────────────────────────────────────────────────────────────────────────────
# DISTRIBUTED BUILD  ← CORE CHANGE
#
# OLD behaviour (broken):
#   num_nodes = len(available_workers)          # e.g. 1
#   → all 57 pages sent to 1 worker
#   → manager sits idle
#
# NEW behaviour (fixed):
#   num_nodes = len(available_workers) + 1      # workers  PLUS  manager itself
#   → last slice always kept by manager and processed locally
#   → worker slices sent in parallel via _call_worker
#   → manager's local slice processed in executor (non-blocking)
#   → asyncio.gather() waits for ALL of them simultaneously
#
# Example with 1 worker + manager, 57 pages:
#   Slice 0  (pages  0→28) → Worker-1  [HTTP]
#   Slice 1  (pages 28→57) → Manager   [local executor thread]
# ─────────────────────────────────────────────────────────────────────────────
async def _distribute_and_build(
    file_path:        Path,
    cache_key:        str,
    existing_summary: str = ""
) -> str:
    try:
        logger.info("=" * 60)
        logger.info(f"[MANAGER] Starting distributed build | key={cache_key}")

        # ── STEP 1: Read PDF bytes ───────────────────────────────────────────
        logger.info("[MANAGER] STEP 1/6 — Reading PDF bytes...")
        pdf_bytes   = file_path.read_bytes()
        reader      = PdfReader(file_path)
        total_pages = len(reader.pages)
        logger.info(f"[MANAGER] PDF: {file_path.name} | {total_pages} pages | {len(pdf_bytes)} bytes")

        # ── STEP 2: Discover available workers ──────────────────────────────
        logger.info("[MANAGER] STEP 2/6 — Discovering workers...")
        available_workers = await _get_available_workers()
        num_workers       = len(available_workers)

        # ── STEP 3: Split pages across (workers + manager) ───────────────────
        #
        # The manager is typically slower at LLM inference than a dedicated
        # worker, so we give it a smaller share (MANAGER_LOAD_RATIO).
        # Workers share the remaining pages evenly.
        #
        # Example with 57 pages, 1 worker, MANAGER_LOAD_RATIO=0.2:
        #   Manager: 57 × 0.2 ≈ 11 pages  (pages 46→57)
        #   Worker:  57 - 11 = 46 pages    (pages 0→46)
        #
        if num_workers > 0:
            manager_pages = max(1, int(total_pages * MANAGER_LOAD_RATIO))
            worker_pages  = total_pages - manager_pages
            worker_ranges = _split_page_ranges(worker_pages, num_workers)
            # Manager takes the LAST range (highest page numbers)
            manager_range = (worker_pages, total_pages)
        else:
            # No workers — manager handles everything
            worker_ranges = []
            manager_range = (0, total_pages)

        logger.info("[MANAGER] STEP 3/6 — Splitting page ranges...")
        for i, (s, e) in enumerate(worker_ranges):
            logger.info(f"  Worker-{i+1} ({available_workers[i]}): pages {s} → {e}  ({e-s} pages)")
        ms, me = manager_range
        logger.info(f"  Manager  (local):                  pages {ms} → {me}  ({me-ms} pages)")

        # ── STEP 4: Launch everything in parallel ────────────────────────────
        #
        # asyncio.gather() runs all coroutines concurrently:
        #   • remote worker calls  → _call_worker()   (async HTTP, non-blocking)
        #   • manager's own slice  → run_in_executor() wrapping the sync
        #                            _process_pages_locally() so it runs in a
        #                            thread and doesn't block the event loop
        #
        worker_task_type = "vectorize" if existing_summary else "both"
        logger.info(f"[MANAGER] STEP 4/6 — Launching parallel tasks (task_type={worker_task_type})...")

        loop = asyncio.get_event_loop()

        # Build the list of coroutines
        all_tasks = []

        # Remote worker tasks (one per available worker)
        for i, worker_url in enumerate(available_workers):
            s, e = worker_ranges[i]
            all_tasks.append(
                _call_worker(
                    worker_url=worker_url,
                    pdf_bytes=pdf_bytes,
                    filename=file_path.name,
                    start_page=s,
                    end_page=e,
                    task_type=worker_task_type,
                )
            )

        # Manager's own local task (runs in thread pool, wrapped as a coroutine)
        all_tasks.append(
            loop.run_in_executor(
                executor,
                _process_pages_locally,
                file_path,
                ms,
                me,
                existing_summary,
            )
        )

        # Fire all tasks at once and wait for all to finish
        all_results = await asyncio.gather(*all_tasks)
        logger.info("[MANAGER] All parallel tasks finished. Merging results...")

        # ── STEP 5: Merge results ────────────────────────────────────────────
        logger.info("[MANAGER] STEP 5/6 — Merging results...")

        all_vectors:     List[np.ndarray] = []
        all_flat_chunks: List[dict]       = []
        all_summaries:   List[str]        = []

        # Remote worker results
        for i, res in enumerate(all_results[:-1]):
            s, e         = worker_ranges[i]
            worker_label = f"Worker-{i+1} ({available_workers[i]}) pages {s}→{e}"

            if not res or "vectors" not in res:
                logger.warning(f"[MANAGER] {worker_label} FAILED → running local fallback for its slice...")
                res = await loop.run_in_executor(
                    executor,
                    _process_pages_locally,
                    file_path, s, e, existing_summary,
                )

            _collect_result(res, all_vectors, all_flat_chunks, all_summaries, worker_label)

        # Manager's own result (last item in all_results)
        manager_result = all_results[-1]
        _collect_result(manager_result, all_vectors, all_flat_chunks, all_summaries, f"Manager pages {ms}→{me}")

        if not all_vectors:
            logger.error("[MANAGER] No valid vectors collected. Build ABORTED.")
            return ""

        # Determine final summary
        if existing_summary:
            full_summary = existing_summary
            logger.info(f"[MANAGER] Using pre-existing summary ({len(full_summary)} chars)")
        elif all_summaries:
            full_summary = "\n\n".join(all_summaries)
            logger.info(f"[MANAGER] Combined {len(all_summaries)} partial summaries → {len(full_summary)} chars")
        else:
            full_summary = ""
            logger.warning("[MANAGER] No summaries collected.")

        # ── STEP 6: Build FAISS index ────────────────────────────────────────
        logger.info("[MANAGER] STEP 6/6 — Building FAISS index...")
        master_vs = VectorStore(max_workers=4)
        master_vs.build_from_distributed(
            all_vectors=all_vectors,
            all_chunks=all_flat_chunks,
            cache_source=cache_key,
            summary=full_summary,
        )

        with _vs_lock:
            vector_stores[cache_key] = master_vs

        logger.info(
            f"[MANAGER] Build COMPLETE | key={cache_key} | "
            f"chunks={len(all_flat_chunks)} | "
            f"vectors={sum(v.shape[0] for v in all_vectors)} | "
            f"summary={len(full_summary)} chars"
        )
        logger.info("=" * 60)
        return full_summary

    except Exception as e:
        logger.error(f"[MANAGER] Distributed build CRASHED — {str(e)}", exc_info=True)
        return ""
    finally:
        with _vs_lock:
            vs_building.discard(cache_key)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER — collect one result batch into the running lists
# ─────────────────────────────────────────────────────────────────────────────
def _collect_result(
    res:             dict,
    all_vectors:     List[np.ndarray],
    all_flat_chunks: List[dict],
    all_summaries:   List[str],
    label:           str,
) -> None:
    vecs = res.get("vectors") if res else None
    if isinstance(vecs, np.ndarray) and vecs.ndim == 2 and vecs.shape[0] > 0:
        all_vectors.append(vecs)
        all_flat_chunks.extend(res.get("chunks", []))
        partial = res.get("summary", "")
        if partial and partial.strip():
            all_summaries.append(partial)
        logger.info(f"[MANAGER] OK {label} → {vecs.shape[0]} vectors | {len(partial)} summary chars")
    else:
        logger.error(f"[MANAGER] FAILED {label} → invalid or empty vectors")


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
    logger.info("[SUMMARIZE] New request received — Parallel Mode")
    try:
        file_path = _get_clean_path(request.filePath)
        cache_key = request.fileId if request.fileId else _cache_key(str(file_path))
        logger.info(f"[SUMMARIZE] File: {file_path.name} | Cache key: {cache_key}")

        # ── Check if already built ──────────────────────────────────────────
        with _vs_lock:
            already_done = cache_key in vector_stores

        if already_done:
            vs = vector_stores[cache_key]
            logger.info(f"[SUMMARIZE] Store already exists for: {cache_key}")
            return {
                "status":   "success",
                "summary":  vs.summary,
                "metadata": {"filename": file_path.name, "cache_key": cache_key},
            }

        # ── Check if already building ───────────────────────────────────────
        with _vs_lock:
            already_building = cache_key in vs_building

        if already_building:
            logger.info(f"[SUMMARIZE] Already building for: {cache_key} — returning processing status")
            return {
                "status":    "processing",
                "message":   "Distributed build already in progress",
                "metadata":  {"filename": file_path.name, "cache_key": cache_key},
            }

        # ── Mark as building & launch IMMEDIATELY (fire-and-forget) ─────────
        # NO pre-summarization on the entire PDF!
        # Both master AND workers do embeddings + summarization in PARALLEL.
        # Each node summarizes only its own page range → much faster.
        with _vs_lock:
            vs_building.add(cache_key)

        logger.info(
            f"[SUMMARIZE] Launching distributed build "
            f"(parallel summarization + embeddings) for: {cache_key}"
        )
        asyncio.create_task(
            _distribute_and_build(file_path, cache_key, existing_summary="")
        )

        return {
            "status":    "processing",
            "message":   "Distributed Parallel Processing started (Summary + Vectors)...",
            "metadata":  {"filename": file_path.name, "cache_key": cache_key},
        }
    except HTTPException:
        raise
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

        wait = 0
        while cache_key in vs_building and wait < 120:
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
                with _vs_lock:
                    already_building = cache_key in vs_building
                    if not already_building:
                        vs_building.add(cache_key)

                if already_building:
                    logger.info("[ASK] Build still running. Waiting up to 180s more...")
                    extra = 0
                    while cache_key in vs_building and extra < 180:
                        if cache_key in vector_stores:
                            break
                        await asyncio.sleep(1)
                        extra += 1
                else:
                    logger.info("[ASK] Not on disk. Triggering distributed build...")
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
