"""
Text chunking — works with header-based sections from pdf_processor.
"""
from nltk.tokenize import sent_tokenize
import re
import logging

logger = logging.getLogger(__name__)


def split_into_chunks(text: str, max_words: int = 300) -> list:
    """
    Split a section's text into chunks.
    - لو النص أقل من max_words → يرجع as-is في list واحدة
    - لو أكبر → يقسم بالجمل مع الحفاظ على الـ section title في أول كل chunk
    """
    try:
        text = text.strip()
        if not text:
            return []

        # استخرج الـ title لو موجود (أول سطر)
        lines = text.split("\n\n", 1)
        title = lines[0].strip() if len(lines) > 1 else ""
        body = lines[1].strip() if len(lines) > 1 else text

        # لو النص كله أصغر من max_words → رجّعه as-is
        if len(text.split()) <= max_words:
            return [text]

        # قسّم الـ body بالجمل
        sentences = sent_tokenize(body)
        chunks = []
        current_chunk = title + "\n\n" if title else ""

        for sentence in sentences:
            addition = sentence + " "
            if len((current_chunk + addition).split()) <= max_words:
                current_chunk += addition
            else:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                # كل chunk جديد يبدأ بالـ title عشان الـ RAG يعرف هو في أنهي section
                current_chunk = (title + "\n\n" if title else "") + addition

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        # لو آخر chunk صغير جداً (أقل من 30% من max_words) → دمّجه مع اللي قبله
        if len(chunks) >= 2 and len(chunks[-1].split()) < 0.3 * max_words:
            chunks[-2] = (chunks[-2] + "\n\n" + chunks[-1]).strip()
            chunks.pop()

        logger.info(f"Split section '{title[:40]}' into {len(chunks)} chunks")
        return chunks

    except Exception as e:
        logger.error(f"Error splitting text into chunks: {e}")
        raise
