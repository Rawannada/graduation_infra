import os
import sys
import shutil
import asyncio
from pathlib import Path
from typing import Dict
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor

# إضافة المسارات عشان السيرفر يشوف الفولدرات
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent / "pdf_summarizer" / "src"))

from rag_pipeline import VectorStore, RAGPipeline
from pdf_processor import PDFProcessor

# استدعاء كلاس التلخيص
try:
    from pdf_summarizer.src.summarizer import PDFSummarizer
except ImportError:
    from summarizer import PDFSummarizer

app = FastAPI()

# سنستخدم هذا الـ executor فقط للعمليات التي تحتاج await يدوي
executor = ThreadPoolExecutor(max_workers=4)
vector_stores: Dict[str, VectorStore] = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class QuestionRequest(BaseModel):
    sessionId: str
    question: str

@app.get("/")
async def root():
    return {"status": "healthy", "message": "AI Service is running"}

# --- تعديل دالة التلخيص لتكون Synchronous لضمان استلام الرد ---
@app.post("/api/summarize")
def summarize(sessionId: str = Form(...), file: UploadFile = File(...)):
    try:
        print(f"\n[INFO] Starting Summarization for Session: {sessionId}")
        
        # 1. حفظ الملف في فولدر الـ Session
        upload_path = Path(f"./uploads/{sessionId}")
        upload_path.mkdir(parents=True, exist_ok=True)
        file_path = upload_path / file.filename
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        print(f"[INFO] File saved to: {file_path}")

        # 2. تشغيل التلخيص (نادِ الدالة مباشرة بدون await loop)
        # هذا يمنع تعليق السيرفر ويسمح للدالة بإنهاء الـ Chunks وإرجاع النتيجة
        summarizer = PDFSummarizer()
        
        print(f"[INFO] Processing {file.filename} through AI Summarizer...")
        summary_result = summarizer.summarize(str(file_path))

        # 3. تنظيف الـ Vector Store القديم للجلسة لضمان دقة الأسئلة الجديدة
        if sessionId in vector_stores:
            del vector_stores[sessionId]
            print(f"[INFO] Cleared old vector store for session: {sessionId}")

        print(f"✅ [SUCCESS] Summarization finished for {sessionId}")
        
        # إرجاع الرد النهائي - هذا ما سيظهر كـ 200 OK في الـ Terminal
        return {
            "status": "success",
            "summary": summary_result,
            "metadata": {"filename": file.filename}
        }

    except Exception as e:
        print(f"🔴 [ERROR] Summarize failed: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Summarization failed: {str(e)}")

@app.post("/api/ask")
async def ask(request: QuestionRequest):
    try:
        session_folder = Path(f"./uploads/{request.sessionId}")
        if not session_folder.exists():
            raise HTTPException(status_code=404, detail="Session not found")

        # إذا لم يكن الـ Vector Store موجوداً في الذاكرة، نقوم بإنشائه
        if request.sessionId not in vector_stores:
            pdf_files = list(session_folder.glob("*.pdf"))
            if not pdf_files: 
                raise HTTPException(status_code=404, detail="No PDF file found in session folder")
            
            print(f"[INFO] Building Vector Store for session: {request.sessionId}")
            processor = PDFProcessor(str(pdf_files[0]))
            pages_data = processor.process_pdf()
            
            vs = VectorStore()
            vs.create_vector_store(pages_data)
            vector_stores[request.sessionId] = vs

        # تشغيل الـ RAG Pipeline للرد على السؤال
        rag = RAGPipeline(vector_store=vector_stores[request.sessionId])
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(executor, rag.query, request.question)
        
        return result
    except Exception as e:
        print(f"🔴 [ERROR] Ask failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/session/{sessionId}")
async def cleanup_session(sessionId: str):
    try:
        if sessionId in vector_stores:
            del vector_stores[sessionId]
        
        path = Path(f"./uploads/{sessionId}")
        if path.exists():
            shutil.rmtree(path)
        return {"status": "success", "message": f"Session {sessionId} cleaned up"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # تشغيل السيرفر
    uvicorn.run(app, host="0.0.0.0", port=8000)