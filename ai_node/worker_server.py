import logging
import numpy as np
import io
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

# نفس الملفات اللي عند رواند
from pdf_processor import PDFProcessor
from embeddings import EmbeddingGenerator

# محاولة عمل import للـ chunker من المسارات الممكنة
try:
    from pdf_summarizer.src.chunker import split_into_chunks
except ImportError:
    try:
        from chunker import split_into_chunks
    except ImportError:
        from src.chunker import split_into_chunks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("WORKER")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

embedding_generator = EmbeddingGenerator(max_workers=4)

@app.get("/")
def root():
    return {"status": "worker_ready"}

# ─────────────────────────────────────────────────────────────────────────────
# التعديل: استبدال الـ JSON بـ UploadFile و Form لتمكين الـ Streaming
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/process")
async def process(
    file: UploadFile = File(...),      # استلام الملف كـ Bytes
    startPage: int = Form(...),        # الصفحة اللي هيبدأ منها
    endPage: int = Form(...)           # الصفحة اللي هيوقف عندها
):
    """
    بيستقبل جزء من الـ PDF كـ Stream ويرجع النتيجة.
    """
    logger.info(
        f"استلمت ملف: {file.filename} "
        f"(صفحة {startPage} → {endPage})"
    )

    try:
        # 1. قراءة محتوى الملف في الذاكرة (RAM) وتحويله لـ BytesIO
        file_content = await file.read()
        pdf_stream = io.BytesIO(file_content)
        # بنعطي الـ stream اسم عشان الـ processor يعرفه
        pdf_stream.name = file.filename

        # 2. استخراج النص باستخدام الـ Processor (النسخة اللي عدلناها للـ Bytes)
        processor = PDFProcessor(pdf_stream)
        pages_data = processor.process_pdf(
            use_ocr=False,
            use_sections=True,
            start_page=startPage,
            end_page=endPage,
        )

        if not pages_data:
            logger.warning("مفيش نص اتستخرج من الصفحات دي")
            return {"documents": [], "vectors": [], "raw_vectors": []}

        # 3. تقطيع النص لـ chunks
        chunked_data = []
        for section in pages_data:
            chunks = split_into_chunks(section["text"], max_words=100)
            for chunk in chunks:
                chunked_data.append({
                    "text":           chunk,
                    "filename":      section["filename"],
                    "page_num":      section["page_num"],
                    "source":        section.get("source", section["filename"]),
                    "section_title": section.get("section_title", ""),
                })

        logger.info(f"تم تقطيع النص لـ {len(chunked_data)} chunk")

        # 4. عمل الـ embeddings
        texts = [c["text"] for c in chunked_data]
        embeddings = embedding_generator.embed_documents(texts)
        emb_np = np.array(embeddings).astype("float32")

        # 5. تنسيب الـ vectors (normalized)
        norms = np.linalg.norm(emb_np, axis=1, keepdims=True)
        norms[norms == 0] = 1
        normalized = emb_np / norms

        logger.info(f"تم عمل الـ embeddings بنجاح ({len(embeddings)} vector)")

        return {
            "documents":   chunked_data,
            "vectors":      normalized.tolist(),
            "raw_vectors": emb_np.tolist(),
        }

    except Exception as e:
        logger.error(f"خطأ في المعالجة عند الوركير: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # التأكد من تشغيل السيرفر على 0.0.0.0 للسماح بالاتصال عبر الشبكة
    uvicorn.run(app, host="0.0.0.0", port=8001)