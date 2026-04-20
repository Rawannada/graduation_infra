import logging
import numpy as np
import io
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

# Project internal imports
from pdf_processor import PDFProcessor
from embeddings import EmbeddingGenerator

# handling for chunker
try:
    from pdf_summarizer.src.chunker import split_into_chunks
except ImportError:
    try:
        from chunker import split_into_chunks
    except ImportError:
        from src.chunker import split_into_chunks

# Attempt to import PDFSummarizer
try:
    from pdf_summarizer.src.summarizer import PDFSummarizer
except ImportError:
    try:
        from summarizer import PDFSummarizer
    except ImportError:
        PDFSummarizer = None

# Configure Instant Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("WORKER_NODE")

app = FastAPI(title="Distributed Processing Worker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize engines
embedding_generator = EmbeddingGenerator(max_workers=4)
summarizer_engine = PDFSummarizer() if PDFSummarizer else None

@app.get("/")
def health_check():
    return {
        "status": "ready", 
        "capabilities": ["vectorization", "summarization" if summarizer_engine else "none"]
    }

# ─────────────────────────────────────────────────────────────────────────────
# Distributed Summarization
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/process_summary")
async def process_summary_fragment(
    file: UploadFile = File(...),
    startPage: int = Form(...),
    endPage: int = Form(...)
):
    if not summarizer_engine:
        logger.error("Summarizer engine not found on this worker.")
        raise HTTPException(status_code=501, detail="Summarization module not installed on worker.")

    logger.info(f"Task Started: Summarizing {file.filename} | Pages {startPage}-{endPage}")
    
    try:
        file_content = await file.read()
        pdf_stream = io.BytesIO(file_content)
        processor = PDFProcessor(pdf_stream)
        pages_data = processor.process_pdf(start_page=startPage, end_page=endPage)
        
        text_chunks = []
        for page in pages_data:
            if page["text"].strip():
                chunks = split_into_chunks(page["text"], max_words=200)
                text_chunks.extend(chunks)

        if not text_chunks:
            return {"partial_summary": ""}

        # تأكدي إن الدالة دي موجودة في ملف summarizer.py عندك
        partial_summary, _ = summarizer_engine.summarize_text_with_ollama(
            text_chunks=text_chunks,
            model_name=summarizer_engine.model_name,
            temperature=0.1,
            max_tokens=512
        )
        
        logger.info(f"Task Completed: Summary generated for pages {startPage}-{endPage}")
        return {"partial_summary": partial_summary}

    except Exception as e:
        logger.error(f"Summarization failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────────────────────────────────────────
# Vectorization (التعديل لضمان الدمج في الـ Manager)
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/process")
async def process_vectors(
    file: UploadFile = File(...),
    startPage: int = Form(...),
    endPage: int = Form(...)
):
    logger.info(f"Task Started: Vectorizing {file.filename} | Pages {startPage}-{endPage}")

    try:
        file_content = await file.read()
        pdf_stream = io.BytesIO(file_content)
        processor = PDFProcessor(pdf_stream)
        
        # استخراج الصفحات المطلوبة فقط
        pages_data = processor.process_pdf(
            use_ocr=False, 
            use_sections=True, 
            start_page=startPage, 
            end_page=endPage
        )

        if not pages_data:
            return {"chunks": [], "embeddings": [], "documents": []}

        chunked_data = []
        for section in pages_data:
            chunks = split_into_chunks(section["text"], max_words=100)
            for chunk in chunks:
                chunked_data.append({
                    "text": chunk,
                    "filename": section.get("filename", file.filename),
                    "page_num": section.get("page_num", 0),
                    "section_title": section.get("section_title", ""),
                })

        # توليد الـ Embeddings
        texts = [c["text"] for c in chunked_data]
        embeddings = embedding_generator.embed_documents(texts)
        emb_np = np.array(embeddings).astype("float32")

        logger.info(f"Task Completed: Generated {len(embeddings)} vectors.")

        # بنرجع chunks و documents بنفس القيمة لضمان التوافق مع الـ Manager
        return {
            "status": "success",
            "chunks": chunked_data,
            "documents": chunked_data, 
            "embeddings": emb_np.tolist()
        }

    except Exception as e:
        logger.error(f"Vectorization failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # البورت 8001 هو بورت الوركر الثابت في كود المدير
    uvicorn.run(app, host="0.0.0.0", port=8001)