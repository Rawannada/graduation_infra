import logging
import numpy as np
import io
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

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
# STARTUP — initialize models once
# ─────────────────────────────────────────────────────────────────────────────
embedding_generator = EmbeddingGenerator(max_workers=4)
summarizer_engine   = PDFSummarizer() if PDFSummarizer else None

logger.info("=" * 60)
logger.info("[STARTUP] Worker node starting...")
logger.info(f"[STARTUP] Embedding model: {embedding_generator.model_name}")
logger.info(f"[STARTUP] Summarization: {'ENABLED' if summarizer_engine else 'DISABLED'}")
logger.info("[STARTUP] Worker ready.")
logger.info("=" * 60)

# ─────────────────────────────────────────────────────────────────────────────
# HEALTH CHECK
# BUG FIX A: manager was calling GET /health — added /health alias so both
# GET / and GET /health work. Manager's _get_available_workers() hits GET /
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/")
@app.get("/health")
def health_check():
    logger.info("[HEALTH] Health check received.")
    return {
        "status": "ready",
        "capabilities": {
            "vectorization": True,
            "summarization": summarizer_engine is not None,
        }
    }

# ─────────────────────────────────────────────────────────────────────────────
# SUMMARIZATION ENDPOINT — /process_summary
# Receives PDF bytes + page range, returns partial summary string
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/process_summary")
async def process_summary_fragment(
    file:      UploadFile = File(...),
    startPage: int        = Form(...),
    endPage:   int        = Form(...)
):
    logger.info("=" * 60)
    logger.info(f"[SUMMARIZE] File: {file.filename} | Pages: {startPage} → {endPage}")

    if not summarizer_engine:
        raise HTTPException(status_code=501, detail="Summarization not available on this worker.")

    try:
        file_content = await file.read()
        pdf_stream   = io.BytesIO(file_content)

        processor  = PDFProcessor(pdf_stream)
        pages_data = processor.process_pdf(
            use_ocr=False, use_sections=True,
            start_page=startPage, end_page=endPage
        )
        logger.info(f"[SUMMARIZE] Extracted {len(pages_data)} pages.")

        text_chunks = []
        for page in pages_data:
            if page["text"].strip():
                text_chunks.extend(split_into_chunks(page["text"], max_words=200))

        if not text_chunks:
            logger.warning("[SUMMARIZE] No text found. Returning empty summary.")
            return {"partial_summary": ""}

        partial_summary, _ = summarizer_engine.summarize_text_with_ollama(
            text_chunks=text_chunks,
            model_name=summarizer_engine.model_name,
            temperature=0.1,
            max_tokens=512
        )
        logger.info(f"[SUMMARIZE] Done. Length: {len(partial_summary)} chars.")
        return {"partial_summary": partial_summary}

    except Exception as e:
        logger.error(f"[SUMMARIZE] Failed — {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────────────────────────────────────────
# MAIN PROCESSING ENDPOINT — /process
# Vectorizes + optionally summarizes assigned PDF page range.
# BUG FIX B: old code returned no summary key from this endpoint — added it.
# Manager's _call_worker_process_chunks reads result.get("summary", "")
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/process")
async def process_task(
    file:      UploadFile = File(...),
    startPage: int        = Form(...),
    endPage:   int        = Form(...),
    task_type: str        = Form("vectorize")   # 'vectorize' | 'both'
):
    logger.info("=" * 60)
    logger.info(f"[TASK] task_type={task_type} | File: {file.filename} | Pages: {startPage}→{endPage}")

    try:
        # ── STEP 1: Read PDF ────────────────────────────────────────────────
        file_content = await file.read()
        pdf_stream   = io.BytesIO(file_content)
        logger.info(f"[TASK] PDF size: {len(file_content)} bytes")

        # ── STEP 2: Extract text ─────────────────────────────────────────────
        processor  = PDFProcessor(pdf_stream)
        pages_data = processor.process_pdf(
            use_ocr=False,
            use_sections=True,
            start_page=startPage,
            end_page=endPage
        )
        logger.info(f"[TASK] Extracted {len(pages_data)} sections.")

        if not pages_data:
            logger.warning("[TASK] No text in assigned page range. Returning empty.")
            return {"status": "empty", "vectors": [], "chunks": [], "summary": ""}

        # ── STEP 3: Split into chunks ─────────────────────────────────────────
        chunked_data = []
        for section in pages_data:
            for chunk_text in split_into_chunks(section["text"], max_words=100):
                chunked_data.append({
                    "text":          chunk_text,
                    "filename":      section.get("filename", file.filename),
                    "page_num":      section.get("page_num", 0),
                    "section_title": section.get("section_title", ""),
                })
        logger.info(f"[TASK] Total chunks: {len(chunked_data)}")

        # ── STEP 4: Embed ────────────────────────────────────────────────────
        texts      = [c["text"] for c in chunked_data]
        embeddings = embedding_generator.embed_documents(texts)
        emb_np     = np.array(embeddings).astype("float32")
        logger.info(f"[TASK] Embeddings shape: {emb_np.shape}")

        # ── STEP 5: Normalize ─────────────────────────────────────────────────
        norms             = np.linalg.norm(emb_np, axis=1, keepdims=True)
        norms[norms == 0] = 1
        normalized        = emb_np / norms
        logger.info(f"[TASK] Normalized shape: {normalized.shape}")

        # ── STEP 6: Summarize (optional) ─────────────────────────────────────
        # BUG FIX B: was never generating summary here — manager expected it
        summary = ""
        if summarizer_engine and task_type in ("both", "summarize"):
            logger.info("[TASK] Generating summary...")
            try:
                summary, _ = summarizer_engine.summarize_text_with_ollama(
                    text_chunks=texts,
                    model_name=summarizer_engine.model_name,
                    temperature=0.1,
                    max_tokens=512
                )
                logger.info(f"[TASK] Summary length: {len(summary)} chars")
            except Exception as e:
                logger.error(f"[TASK] Summary failed — {str(e)}")

        logger.info(f"[TASK] DONE. {len(chunked_data)} chunks | {normalized.shape[0]} vectors | {len(summary)} summary chars")
        return {
            "status":       "success",
            "vectors":      normalized.tolist(),
            "chunks":       chunked_data,
            "summary":      summary,
            "vector_count": normalized.shape[0],
        }

    except Exception as e:
        logger.error(f"[TASK] Failed — {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────────────────────────────────────────
# JSON CHUNKS ENDPOINT — /process_chunks
# BUG FIX C: manager's old code sent JSON chunks but worker had no such endpoint.
# Added this so older manager versions still work if needed.
# Accepts {chunks: [...]} JSON body, embeds + returns vectors.
# ─────────────────────────────────────────────────────────────────────────────
class ChunksRequest(BaseModel):
    chunks: List[dict]

@app.post("/process_chunks")
async def process_chunks_json(req: ChunksRequest):
    logger.info("=" * 60)
    logger.info(f"[CHUNKS] Received {len(req.chunks)} chunks via JSON")

    if not req.chunks:
        return {"vectors": [], "chunks": [], "summary": ""}

    try:
        texts  = [c["text"] for c in req.chunks]
        embs   = embedding_generator.embed_documents(texts)
        emb_np = np.array(embs).astype("float32")

        norms             = np.linalg.norm(emb_np, axis=1, keepdims=True)
        norms[norms == 0] = 1
        normalized        = emb_np / norms

        summary = ""
        if summarizer_engine:
            try:
                summary, _ = summarizer_engine.summarize_text_with_ollama(
                    text_chunks=texts,
                    model_name=summarizer_engine.model_name,
                    temperature=0.1,
                    max_tokens=512
                )
            except Exception as e:
                logger.error(f"[CHUNKS] Summary failed — {str(e)}")

        logger.info(f"[CHUNKS] Done. {normalized.shape[0]} vectors | {len(summary)} summary chars")
        return {
            "status":       "success",
            "vectors":      normalized.tolist(),
            "chunks":       req.chunks,
            "summary":      summary,
            "vector_count": normalized.shape[0],
        }

    except Exception as e:
        logger.error(f"[CHUNKS] Failed — {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
