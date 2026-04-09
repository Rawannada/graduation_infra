"""
Parallel summarization support using Direct API (Requests)
"""
import re
import requests
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Callable

logger = logging.getLogger(__name__)


def _fast_summarize(url: str, model: str, prompt: str, temp: float, tokens: int) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temp, "num_predict": tokens}
    }
    resp = requests.post(url, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json().get("response", "Summary failed")


def _merge_duplicate_headers(summaries: list) -> list:
    """
    لو نفس الـ header اتكرر، يجمع المحتوى تحته في section واحدة.
    """
    header_pattern = re.compile(r'^\*\*(.+?)\*\*', re.MULTILINE)

    grouped = defaultdict(list)
    order = []

    for summary in summaries:
        match = header_pattern.match(summary.strip())
        if match:
            header = match.group(1).strip()
            content = summary[match.end():].strip()
            if header not in grouped:
                order.append(header)
            grouped[header].append(content)
        else:
            if "General" not in grouped:
                order.append("General")
            grouped["General"].append(summary.strip())

    result = []
    for header in order:
        contents = grouped[header]
        unique_contents = list(dict.fromkeys(contents))[:2]
        merged = f"**{header}**\n" + " ".join(unique_contents)
        result.append(merged)

    return result


def summarize_chunks_parallel(
    text_chunks: List[str],
    model_name: str,
    temperature: float,
    max_tokens: int,
    prompt_func: Callable,
    max_workers: int = 2,
    use_gpu: bool = True
) -> List[str]:
    url = "http://localhost:11434/api/generate"

    def process_chunk(index, chunk):
        try:
            sentences = chunk.split('. ')[:8]
            short_chunk = '. '.join(sentences)[:3000]

            prompt = (
                f"You are a technical writer. Read the text below and extract:\n"
                f"1. The MAIN TOPIC as a bold header (e.g. **Topic Name**)\n"
                f"2. A brief explanation in 2-3 sentences maximum\n\n"
                f"Rules:\n"
                f"- Start directly with **Header**\n"
                f"- No intro phrases like 'Here is' or 'This text discusses'\n"
                f"- If multiple topics exist, use multiple headers\n"
                f"- Be concise\n\n"
                f"Text:\n{short_chunk}"
            )
            summary = _fast_summarize(url, model_name, prompt, temperature, 300)
            logger.info(f"✅ Completed chunk {index + 1}/{len(text_chunks)}")
            return index, summary
        except Exception as e:
            logger.error(f"❌ Error in chunk {index + 1}: {e}")
            return index, f"Error: Failed to summarize chunk {index + 1}"

    partial_summaries = [None] * len(text_chunks)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_chunk, i, chunk): i
            for i, chunk in enumerate(text_chunks)
        }
        for future in as_completed(futures):
            index, summary = future.result()
            partial_summaries[index] = summary

    # ✅ شيل الـ errors وادمج الـ duplicates
    valid = [s for s in partial_summaries if s and not s.startswith("Error")]
    return _merge_duplicate_headers(valid)
