"""
Text chunking with heading detection
"""
from nltk.tokenize import sent_tokenize
import re
import logging

logger = logging.getLogger(__name__)

def _is_heading(paragraph: str) -> bool:
    """تخمين ما إذا كان السطر عنواناً بناءً على طول وشكل النص."""
    p = paragraph.strip()
    if not p:
        return False
    
    if len(p) <= 120:
        if re.match(r"^([0-9]+[\.\-)]|[A-Za-z]\.|[IVXLC]+\.)\s", p):
            return True
        if p.endswith(":"):
            return True
        words = p.split()
        if words and sum(1 for w in words if w[:1].isupper()) / len(words) >= 0.8:
            return True
    return False

def split_into_chunks(text: str, max_words: int = 300):
    """
    تقسيم النص إلى chunks بناءً على فقرات وعناوين إن وُجدت.
    """
    try:
        raw_paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        paragraphs = []
        
        for p in raw_paragraphs:
            if len(p) <= 3 and re.match(r"^[0-9]+$", p):
                continue
            paragraphs.append(p)

        sections = []
        i = 0
        while i < len(paragraphs):
            current = paragraphs[i]
            if _is_heading(current) and i + 1 < len(paragraphs):
                sections.append(current + "\n" + paragraphs[i + 1])
                i += 2
            else:
                sections.append(current)
                i += 1

        if len(sections) <= 2:
            sentences = sent_tokenize(text)
            chunks = []
            current_chunk = ""
            for sentence in sentences:
                if len(current_chunk.split()) + len(sentence.split()) <= max_words:
                    current_chunk += sentence + " "
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = sentence + " "
            if current_chunk:
                chunks.append(current_chunk.strip())
            return chunks

        chunks = []
        current_chunk = ""
        for section in sections:
            section_words = len(section.split())
            chunk_words = len(current_chunk.split()) if current_chunk else 0

            if section_words >= max_words:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                chunks.append(section.strip())
                continue

            if chunk_words + section_words <= max_words:
                current_chunk = (current_chunk + "\n\n" + section).strip()
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = section

        if current_chunk:
            chunks.append(current_chunk.strip())

        if len(chunks) >= 2:
            last_words = len(chunks[-1].split())
            if last_words < 0.3 * max_words:
                chunks[-2] = (chunks[-2] + "\n\n" + chunks[-1]).strip()
                chunks.pop()

        logger.info(f"Split text into {len(chunks)} chunks")
        return chunks
        
    except Exception as e:
        logger.error(f"Error splitting text into chunks: {e}")
        raise