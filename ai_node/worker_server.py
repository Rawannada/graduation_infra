import logging
import numpy as np
import io
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

from pdf_processor import PDFProcessor
from embeddings import EmbeddingGenerator

try:
    from pdf_summarizer.src.chunker import split_into_chunks
except ImportError:
    try:
        from chunker import split_into_chunks
    except ImportError:
        from src.chunker import split_into_chunks

try:
    from pdf_summarizer.src.summarizer import PDFSummarizer
except ImportError:
    try:
        from summarizer import PDFSummarizer
    except ImportError:
        PDFSummarizer = None

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("WORKER_NODE")

# ─────────────────────────────────────────────────────────────────────────────
# APP & MIDDLEWARE
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(title="Distributed Processing Worker")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────────────────────────────────────
embedding_generator = EmbeddingGenerator(max_workers=4)
summarizer_engine   = PDFSummarizer() if PDFSummarizer else None

logger.info("=" * 60)
logger.info("[STARTUP] Worker node is starting...")
logger.info(f"[STARTUP] Embedding model loaded: {embedding_generator.model_name}")
logger.info(f"[STARTUP] Summarization capability: {'ENABLED' if summarizer_engine else 'DISABLED'}")
logger.info("[STARTUP] Worker is ready and listening for tasks.")
logger.info("=" * 60)

# ─────────────────────────────────────────────────────────────────────────────
# HEALTH CHECK
# Manager calls this to verify the worker is alive before sending tasks
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/")
def health_check():
    logger.info("[HEALTH] Health check requested by manager.")
    return {
        "status": "ready",
        "capabilities": ["vectorization", "summarization" if summarizer_engine else "none", "combined"]
    }

# ─────────────────────────────────────────────────────────────────────────────
# SUMMARIZATION ENDPOINT
# Receives PDF bytes + page range, extracts text, summarizes via Ollama,
# and returns a partial summary string back to the manager
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/process_summary")
async def process_summary_fragment(
    file:      UploadFile = File(...),
    startPage: int        = Form(...),
    endPage:   int        = Form(...)
):
    logger.info("=" * 60)
    logger.info(f"[SUMMARIZE] New summarization task received.")
    logger.info(f"[SUMMARIZE] File: {file.filename} | Assigned pages: {startPage} -> {endPage}")

    if not summarizer_engine:
        logger.error("[SUMMARIZE] ERROR: Summarizer engine is not installed on this worker.")
        raise HTTPException(status_code=501, detail="Summarization module not installed on worker.")

    try:
        logger.info("[SUMMARIZE] STEP 1/3 — Reading uploaded PDF bytes...")
        file_content = await file.read()
        pdf_stream   = io.BytesIO(file_content)
        logger.info(f"[SUMMARIZE] PDF received. Size: {len(file_content)} bytes.")

        logger.info("[SUMMARIZE] STEP 2/3 — Extracting text from assigned pages...")
        processor  = PDFProcessor(pdf_stream)
        pages_data = processor.process_pdf(start_page=startPage, end_page=endPage)
        logger.info(f"[SUMMARIZE] Extracted {len(pages_data)} pages.")

        text_chunks = []
        for page in pages_data:
            if page["text"].strip():
                chunks = split_into_chunks(page["text"], max_words=200)
                text_chunks.extend(chunks)

        logger.info(f"[SUMMARIZE] Total text chunks to summarize: {len(text_chunks)}")

        if not text_chunks:
            logger.warning("[SUMMARIZE] WARNING: No text found in assigned page range. Returning empty summary.")
            return {"partial_summary": ""}

        logger.info("[SUMMARIZE] STEP 3/3 — Sending chunks to Ollama for summarization...")
        partial_summary, _ = summarizer_engine.summarize_text_with_ollama(
            text_chunks=text_chunks,
            model_name=summarizer_engine.model_name,
            temperature=0.1,
            max_tokens=512
        )

        logger.info(f"[SUMMARIZE] Task COMPLETE. Summary length: {len(partial_summary)} characters.")
        return {"partial_summary": partial_summary}

    except Exception as e:
        logger.error(f"[SUMMARIZE] ERROR: Task failed — {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────────────────────────────────────────
# VECTORIZATION ENDPOINT
# Receives PDF bytes + page range from the manager.
# Pipeline:
#   Step 1 — Read the uploaded PDF bytes into memory
#   Step 2 — Extract and section text from the assigned page range
#   Step 3 — Split sections into chunks (max 100 words each)
#   Step 4 — Generate embeddings via local Ollama (parallel)
#   Step 5 — Normalize vectors for cosine similarity
# Returns: { "status", "vectors": list (2D), "chunks": list of dicts }
# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# COMBINED PROCESSING ENDPOINT
# Handles both vectorization and summarization
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/process")
async def process_task(
    file:      UploadFile = File(...),
    startPage: int        = Form(...),
    endPage:   int        = Form(...),
    task_type: str        = Form("vectorize")  # 'vectorize' or 'summarize'
):
    logger.info("=" * 60)
    logger.info(f"[TASK] New {task_type} task received.")
    logger.info(f"[TASK] File: {file.filename} | Pages: {startPage}->{endPage}")

    try:
        # Step 1: Read PDF bytes
        logger.info("[VECTORIZE] STEP 1/5 — Reading uploaded PDF bytes...")
        file_content = await file.read()
        pdf_stream   = io.BytesIO(file_content)
        logger.info(f"[VECTORIZE] PDF received. Size: {len(file_content)} bytes.")

        # Step 2: Extract text from assigned pages
        logger.info("[VECTORIZE] STEP 2/5 — Extracting text from assigned pages...")
        processor  = PDFProcessor(pdf_stream)
        pages_data = processor.process_pdf(
            use_ocr=False,
            use_sections=True,
            start_page=startPage,
            end_page=endPage
        )
        logger.info(f"[VECTORIZE] Extracted {len(pages_data)} sections from pages {startPage}-{endPage}.")

        if not pages_data:
            logger.warning("[VECTORIZE] WARNING: No text found in assigned page range. Returning empty package.")
            return {"chunks": [], "vectors": []}

        # Step 3: Split into chunks
        logger.info("[VECTORIZE] STEP 3/5 — Splitting sections into chunks (max 100 words each)...")
        chunked_data = []
        for section in pages_data:
            chunks = split_into_chunks(section["text"], max_words=100)
            for chunk in chunks:
                chunked_data.append({
                    "text":          chunk,
                    "filename":      section.get("filename", file.filename),
                    "page_num":      section.get("page_num", 0),
                    "section_title": section.get("section_title", ""),
                })
        logger.info(f"[VECTORIZE] Total chunks ready for embedding: {len(chunked_data)}")

        # Step 4: Generate embeddings via local Ollama
        logger.info("[VECTORIZE] STEP 4/5 — Sending chunks to Ollama for embedding (parallel)...")
        texts      = [c["text"] for c in chunked_data]
        embeddings = embedding_generator.embed_documents(texts)
        emb_np     = np.array(embeddings).astype("float32")
        logger.info(f"[VECTORIZE] Embeddings generated. Shape: {emb_np.shape} | dtype: {emb_np.dtype}")

        # Step 5: Normalize vectors
        logger.info("[VECTORIZE] STEP 5/5 — Normalizing vectors before sending to manager...")
        norms             = np.linalg.norm(emb_np, axis=1, keepdims=True)
        norms[norms == 0] = 1
        normalized_emb    = emb_np / norms
        logger.info(f"[VECTORIZE] Normalization done. Final shape: {normalized_emb.shape}")

        logger.info(f"[VECTORIZE] Task COMPLETE. Returning {len(chunked_data)} chunks + {normalized_emb.shape[0]} vectors to manager.")
        return {
            "status":  "success",
            "vectors": normalized_emb.tolist(),
            "chunks":  chunked_data,
        }

    except Exception as e:
        logger.error(f"[VECTORIZE] ERROR: Task failed — {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    # 0.0.0.0 allows the manager machine to reach this worker over the network
    uvicorn.run(app, host="0.0.0.0", port=8001)
