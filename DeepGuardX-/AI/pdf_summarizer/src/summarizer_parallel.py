"""
Parallel summarization support using Direct API (Requests)
"""
import requests
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Callable

logger = logging.getLogger(__name__)

def summarize_chunks_parallel(
    text_chunks: List[str],
    model_name: str,
    temperature: float,
    max_tokens: int,
    prompt_func: Callable,
    max_workers: int = 4,
    use_gpu: bool = True
) -> List[str]:
    """
    تلخيص chunks بشكل متوازي باستخدام Requests بدل مكتبة ollama
    """
    url = "http://localhost:11434/api/chat"
    partial_summaries = [None] * len(text_chunks)
    
    def process_chunk(index, chunk):
        try:
            prompt = prompt_func(chunk)
            # تجهيز البيانات للـ API
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
            
            # طلب مباشر من Ollama
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            
            result = response.json()
            summary = result.get("message", {}).get("content", f"Error: chunk {index}")
            
            logger.info(f"✅ Completed chunk {index + 1}/{len(text_chunks)}")
            return index, summary
            
        except Exception as e:
            logger.error(f"❌ Error in chunk {index + 1}: {e}")
            return index, f"Error: Failed to summarize chunk {index + 1}"
    
    # تنفيذ المهام بشكل متوازي
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_chunk, i, chunk): i 
            for i, chunk in enumerate(text_chunks)
        }
        
        for future in as_completed(futures):
            index, summary = future.result()
            partial_summaries[index] = summary
    
    return partial_summaries