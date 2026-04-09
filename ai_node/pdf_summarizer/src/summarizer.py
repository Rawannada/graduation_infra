import requests
import logging
from typing import List, Tuple, Optional
from pdf_summarizer.src.utils import get_model_config, retry
from pdf_summarizer.src.summarizer_parallel import summarize_chunks_parallel

logger = logging.getLogger(__name__)


class PDFSummarizer:
    def __init__(self, model_name: str = "llama3"):
        self.model_name = model_name

    def summarize(self, file_path: str) -> str:
        from pdf_processor import PDFProcessor
        from pdf_summarizer.src.chunker import split_into_chunks

        processor = PDFProcessor(file_path)
        pages_data = processor.process_pdf()

        text_chunks = []
        for page in pages_data:
            if page["text"].strip():
                chunks = split_into_chunks(page["text"], max_words=200)
                text_chunks.extend(chunks)

        summary, _ = self.summarize_text_with_ollama(
            text_chunks=text_chunks,
            model_name=self.model_name,
            temperature=0.1,
            max_tokens=512
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

        if use_parallel:
            from pdf_summarizer.src.summarizer import get_chunk_prompt
            partial_summaries = summarize_chunks_parallel(
                text_chunks, model_name, temperature, max_tokens,
                lambda c: get_chunk_prompt(c, language, style),
                max_workers
            )
        else:
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

        # ✅ بنجمع بـ newlines مش spaces
        final_summary = "\n\n".join(partial_summaries)
        return final_summary, partial_summaries


def get_chunk_prompt(chunk: str, language: str, style: str) -> str:
    return (
        f"You are a technical writer. Read the text below and extract:\n"
        f"1. The MAIN TOPIC as a bold header (e.g. **Topic Name**)\n"
        f"2. A brief explanation in 2-3 sentences maximum\n\n"
        f"Rules:\n"
        f"- Start directly with **Header**\n"
        f"- No intro phrases like 'Here is' or 'This text discusses'\n"
        f"- If multiple topics exist, use multiple headers\n"
        f"- Be concise\n\n"
        f"Text:\n{chunk}"
    )
