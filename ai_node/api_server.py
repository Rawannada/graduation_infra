import os
import sys
import shutil
import asyncio
import threading
from pathlib import Path
from typing import Dict
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor


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

executor = ThreadPoolExecutor(max_workers=4)

vector_stores: Dict[str, VectorStore] = {}
vs_building: set = set()

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


def _build_vector_store(session_id: str, file_path: str):
    try:
        print(f"[INFO] Building Vector Store for session: {session_id}")
        processor = PDFProcessor(file_path)
        pages_data = processor.process_pdf(use_ocr=False, use_sections=True)

        # ✅ Chunk sections to fit embedding model context
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

        print(f"[INFO] Embedding {len(chunked_data)} chunks for session: {session_id}")
        vs = VectorStore(max_workers=4)
        vs.create_vector_store(chunked_data)
        vector_stores[session_id] = vs
        print(f"✅ [INFO] Vector Store ready for session: {session_id}")
    except Exception as e:
        print(f"🔴 [ERROR] Failed to build vector store for {session_id}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        vs_building.discard(session_id)


@app.post("/api/summarize")
def summarize(sessionId: str = Form(...), file: UploadFile = File(...)):
    try:
        print(f"\n[INFO] Starting Summarization for Session: {sessionId}")

        upload_path = Path(f"./uploads/{sessionId}")
        upload_path.mkdir(parents=True, exist_ok=True)
        file_path = upload_path / file.filename

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        print(f"[INFO] File saved to: {file_path}")

        summarizer = PDFSummarizer()
        print(f"[INFO] Processing {file.filename} through AI Summarizer...")
        summary_result = summarizer.summarize(str(file_path))

        if sessionId in vector_stores:
            del vector_stores[sessionId]
            print(f"[INFO] Cleared old vector store for session: {sessionId}")

        if sessionId not in vs_building:
            vs_building.add(sessionId)
            t = threading.Thread(
                target=_build_vector_store,
                args=(sessionId, str(file_path)),
                daemon=True
            )
            t.start()
            print(f"[INFO] Background vector store build started for: {sessionId}")

        print(f"✅ [SUCCESS] Summarization finished for {sessionId}")

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

        wait_count = 0
        while request.sessionId in vs_building and wait_count < 60:
            print(f"[INFO] Waiting for background VS build: {request.sessionId} ({wait_count}s)")
            await asyncio.sleep(1)
            wait_count += 1

        if request.sessionId not in vector_stores:
            pdf_files = list(session_folder.glob("*.pdf"))
            if not pdf_files:
                raise HTTPException(
                    status_code=404, detail="No PDF file found in session folder"
                )
            print(f"[INFO] Building Vector Store on-demand for: {request.sessionId}")
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                executor,
                _build_vector_store,
                request.sessionId,
                str(pdf_files[0])
            )
        else:
            print(f"[INFO] Reusing cached Vector Store for session: {request.sessionId}")

        if request.sessionId not in vector_stores:
            raise HTTPException(
                status_code=500,
                detail="Failed to build vector store. Check server logs."
            )

        rag = RAGPipeline(vector_store=vector_stores[request.sessionId])
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(executor, rag.query, request.question)

        return result

    except HTTPException:
        raise
    except Exception as e:
        print(f"🔴 [ERROR] Ask failed: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/session/{sessionId}")
async def cleanup_session(sessionId: str):
    try:
        vs_building.discard(sessionId)

        if sessionId in vector_stores:
            del vector_stores[sessionId]
            print(f"[INFO] Removed vector store for session: {sessionId}")

        path = Path(f"./uploads/{sessionId}")
        if path.exists():
            shutil.rmtree(path)

        return {"status": "success", "message": f"Session {sessionId} cleaned up"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
