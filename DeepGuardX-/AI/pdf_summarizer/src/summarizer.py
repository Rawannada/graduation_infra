import requests
import logging
from typing import List, Tuple, Optional
from pdf_summarizer.src.utils import get_model_config, retry
# استيراد الدالة المتوازية اللي لسه مصلحينها
from pdf_summarizer.src.summarizer_parallel import summarize_chunks_parallel

logger = logging.getLogger(__name__)

class PDFSummarizer:
    def __init__(self, model_name: str = "llama3"):
        self.model_name = model_name

    def summarize(self, file_path: str) -> str:
        """الدالة التي يستدعيها السيرفر مباشرة"""
        # 1. استخراج النص (بافتراض وجود موديول معالجة أو استخدام بسيط هنا)
        from pdf_processor import PDFProcessor
        processor = PDFProcessor(file_path)
        pages_data = processor.process_pdf()
        text_chunks = [p["text"] for p in pages_data if p["text"].strip()]
        
        # 2. مناداة دالة التلخيص
        summary, _ = self.summarize_text_with_ollama(
            text_chunks=text_chunks,
            model_name=self.model_name,
            temperature=0.1,
            max_tokens=2000
        )
        return summary

    def summarize_text_with_ollama(
        self,
        text_chunks: List[str],
        model_name: str,
        temperature: float,
        max_tokens: int,
        use_parallel: bool = True,
        max_workers: int = 4,
        language: str = "auto",
        style: str = "technical"
    ) -> Tuple[str, List[str]]:
        
        # التأكد من استخدام الـ API المباشر
        if use_parallel:
            # استخدام الدالة اللي في الملف التاني اللي لسه مصلحينه
            from pdf_summarizer.src.summarizer import get_chunk_prompt
            partial_summaries = summarize_chunks_parallel(
                text_chunks, model_name, temperature, max_tokens,
                lambda c: get_chunk_prompt(c, language, style),
                max_workers
            )
        else:
            # التنفيذ التسلسلي (Sequential) باستخدام requests
            url = "http://localhost:11434/api/chat"
            partial_summaries = []
            for chunk in text_chunks:
                payload = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": chunk}],
                    "stream": False
                }
                res = requests.post(url, json=payload)
                partial_summaries.append(res.json()["message"]["content"])

        # دمج الملخصات
        final_summary = " ".join(partial_summaries) # تبسيط للدمج
        return final_summary, partial_summaries

# دوال مساعدة خارج الكلاس (Prompt Helpers)
def get_chunk_prompt(chunk: str, language: str, style: str) -> str:
    return f"Summarize this technical text: {chunk}"