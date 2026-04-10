import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# إعداد مسارات المكتبات
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent / "pdf_summarizer" / "src"))

try:
    from pdf_summarizer.src.summarizer import PDFSummarizer
except ImportError:
    from summarizer import PDFSummarizer

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# الجسر الأساسي للوصول لملفات الـ WSL من الويندوز
# هنخلي المسار يقف عند backend-node عشان نتجنب التكرار يدويًا
WSL_BASE_PATH = Path(r"\\wsl.localhost\Ubuntu\home\rawannada\graduation_infra\backend-node")

class SummarizeRequest(BaseModel):
    filePath: str 

@app.get("/")
async def root():
    return {"status": "healthy", "message": "AI Service is running"}

@app.post("/api/summarize")
def summarize(request: SummarizeRequest):
    try:
        # 1. تحويل المسار المستلم لـ Path object
        incoming_path = Path(request.filePath)

        # 2. فحص المسار: لو بيبدأ بـ uploads أو /uploads هنستخدمه كما هو مع الجسر
        # الـ Path.joinpath بيتعامل مع المسارات بذكاء
        # لو المسار اللي جاي "uploads/user/file.pdf" والـ Base آخره "backend-node"
        # النتيجة هتكون "backend-node/uploads/user/file.pdf" (وهو ده الصح)
        file_path = WSL_BASE_PATH.joinpath(incoming_path).resolve()

        print(f"\n[DEBUG] AI Service checking path: {file_path}")

        # 3. التأكد من وجود الملف فعلياً
        if not file_path.exists():
            print(f"🔴 [ERROR] File not found at: {file_path}")
            raise HTTPException(
                status_code=404, 
                detail=f"PDF file not found at {file_path}. Please verify WSL accessibility."
            )

        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="Path is not a file")

        if file_path.suffix.lower() != ".pdf":
            raise HTTPException(status_code=400, detail="File must be a PDF")

        print(f"[INFO] Starting Summarization for: {file_path.name}")

        summarizer = PDFSummarizer()
        summary_result = summarizer.summarize(str(file_path))

        print(f"✅ [SUCCESS] Summarization finished for: {file_path.name}")

        return {
            "status": "success",
            "summary": summary_result,
            "metadata": {
                "filename": file_path.name,
                "filePath": str(file_path)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"🔴 [ERROR] Summarize failed: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Summarization failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    # host 0.0.0.0 ضروري عشان الـ Docker يشوف السيرفر
    uvicorn.run(app, host="0.0.0.0", port=8000)