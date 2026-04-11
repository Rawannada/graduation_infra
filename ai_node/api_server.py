import sys
import asyncio
import threading
from pathlib import Path
from typing import Dict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor

# 1. إعداد مسارات المكتبات (نفس نظامك)
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent / "pdf_summarizer" / "src"))

from rag_pipeline import VectorStore, RAGPipeline
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

# 2. الجسر الأساسي بتاعك للوصول للملفات من الويندوز
WSL_BASE_PATH = Path(r"\\wsl.localhost\Ubuntu\home\rawannada\graduation_infra\backend-node")

# مخازن الذاكرة للـ Vector Stores
vector_stores: Dict[str, VectorStore] = {}
vs_building: set = set()

class SummarizeRequest(BaseModel):
    filePath: str

class QuestionRequest(BaseModel):
    filePath: str
    question: str

# 3. دالة تنظيف المسار (السر اللي هيخلي الـ 500 تختفي)
def _get_clean_path(raw_path: str) -> Path:
    p = Path(raw_path)
    parts = p.parts
    
    # بندور على 'uploads' عشان ناخد المسار النسبي ونركبه على الجسر
    if "uploads" in parts:
        index = parts.index("uploads")
        relative_path = Path(*parts[index:])
    else:
        relative_path = Path("uploads") / p.name

    # دمج المسار النسبي مع الـ WSL Base
    file_path = WSL_BASE_PATH.joinpath(relative_path).resolve()
    
    print(f"\n[DEBUG] Final Resolved Path: {file_path}")

    if not file_path.exists():
        print(f"🔴 [ERROR] File not found at: {file_path}")
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    
    return file_path

# 4. بناء الـ Vector Store في الخلفية
def _build_vector_store(file_path: Path):
    cache_key = str(file_path)
    try:
        if cache_key in vector_stores:
            return

        print(f"[INFO] Building Vector Store for: {file_path.name}")
        processor = PDFProcessor(str(file_path))
        pages_data = processor.process_pdf(use_ocr=False, use_sections=True)

        chunked_data = []
        for section in pages_data:
            for chunk in split_into_chunks(section["text"], max_words=100):
                chunked_data.append({
                    "text": chunk,
                    "filename": section["filename"],
                    "page_num": section["page_num"],
                    "source": section.get("source", section["filename"]),
                    "section_title": section.get("section_title", ""),
                })

        vs = VectorStore(max_workers=4)
        vs.create_vector_store(chunked_data)
        vector_stores[cache_key] = vs
        print(f"✅ [INFO] Vector Store is ready for: {file_path.name}")
    except Exception as e:
        print(f"🔴 [ERROR] Failed to build vector store: {e}")
    finally:
        vs_building.discard(cache_key)

@app.get("/")
async def root():
    return {"status": "healthy", "message": "AI Service is running"}

# 5. التلخيص (Summarize)
@app.post("/api/summarize")
def summarize(request: SummarizeRequest):
    try:
        file_path = _get_clean_path(request.filePath)
        cache_key = str(file_path)

        print(f"[INFO] Starting Summarization...")
        summarizer = PDFSummarizer()
        summary_result = summarizer.summarize(str(file_path))

        # بناء الـ Vector store للأسئلة في الخلفية
        if cache_key not in vs_building:
            vs_building.add(cache_key)
            t = threading.Thread(target=_build_vector_store, args=(file_path,), daemon=True)
            t.start()

        return {
            "status": "success",
            "summary": summary_result,
            "metadata": {"filename": file_path.name}
        }
    except Exception as e:
        print(f"🔴 Summarize Exception: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 6. الأسئلة (Ask Question)
@app.post("/api/ask")
async def ask(request: QuestionRequest):
    try:
        if not request.question.strip():
            raise HTTPException(status_code=400, detail="Question is required")

        file_path = _get_clean_path(request.filePath)
        cache_key = str(file_path)

        # انتظار البناء لو لسه شغال
        wait_count = 0
        while cache_key in vs_building and wait_count < 60:
            await asyncio.sleep(1)
            wait_count += 1

        # لو مش جاهز ابنيه فوراً
        if cache_key not in vector_stores:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(executor, _build_vector_store, file_path)

        if cache_key not in vector_stores:
            raise HTTPException(status_code=500, detail="Failed to initialize Vector Store")

        # تشغيل الـ RAG Pipeline
        rag = RAGPipeline(vector_store=vector_stores[cache_key])
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(executor, rag.query, request.question)

        return {
            "status": "success",
            "answer": result.get("answer", ""),
            "sources": result.get("sources", [])
        }
    except Exception as e:
        print(f"🔴 Ask Exception: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)