"""
PDF Processing with Text Extraction and OCR
"""

import re
import logging
from typing import List, Dict, Any
from pathlib import Path

import pytesseract
from pdf2image import convert_from_path
from pypdf import PdfReader

logger = logging.getLogger(__name__)

# Configure Tesseract path for Windows
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


class PDFProcessor:
    """Process a single PDF with text extraction and OCR."""

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.filename = Path(pdf_path).name

    def extract_text_from_pdf(self) -> List[Dict[str, Any]]:
        """Extract text from PDF pages using pypdf."""
        pages_data: List[Dict[str, Any]] = []

        try:
            reader = PdfReader(self.pdf_path)

            for page_num, page in enumerate(reader.pages, start=1):
                raw_text = page.extract_text() or ""
                text = self._clean_text(raw_text)

                if text.strip():
                    pages_data.append({
                        "page_num": page_num,
                        "text": text,
                        "source": f"{self.filename} — page {page_num}",
                        "type": "text",
                        "filename": self.filename,
                    })

        except Exception as e:
            logger.error(f"Error extracting text from {self.filename}: {e}")

        return pages_data

    def extract_text_with_ocr(self) -> List[Dict[str, Any]]:
        """Extract text from PDF pages using OCR (Tesseract)."""
        pages_data: List[Dict[str, Any]] = []

        try:
            images = convert_from_path(self.pdf_path, dpi=300)

            for page_num, image in enumerate(images, start=1):
                ocr_raw = pytesseract.image_to_string(image, lang="eng") or ""
                ocr_text = self._clean_text(ocr_raw)

                if ocr_text.strip():
                    pages_data.append({
                        "page_num": page_num,
                        "text": ocr_text,
                        "source": f"{self.filename} — page {page_num} (OCR)",
                        "type": "ocr",
                        "filename": self.filename,
                    })

        except Exception as e:
            logger.error(f"Error performing OCR on {self.filename}: {e}")

        return pages_data

    def process_pdf(self, use_ocr: bool = True) -> List[Dict[str, Any]]:
        """Process PDF using normal text extraction and optional OCR."""
        logger.info(f"\n=== Processing PDF: {self.filename} ===")

        text_pages = self.extract_text_from_pdf()
        logger.info(f"  - Normal text pages: {len(text_pages)}")

        all_pages: List[Dict[str, Any]] = list(text_pages)

        if use_ocr:
            logger.info(f"  - Running OCR on {self.filename} ...")
            ocr_pages = self.extract_text_with_ocr()
            logger.info(f"  - OCR pages: {len(ocr_pages)}")

            for ocr_page in ocr_pages:
                page_num = ocr_page["page_num"]
                text_page = next((p for p in text_pages if p["page_num"] == page_num), None)

                if not text_page or len(text_page["text"]) < 100:
                    if text_page and text_page in all_pages:
                        all_pages.remove(text_page)
                    all_pages.append(ocr_page)
                elif len(ocr_page["text"]) > 200:
                    all_pages.append(ocr_page)

        all_pages.sort(key=lambda x: x["page_num"])
        logger.info(f"  ✓ Total entries (text + OCR): {len(all_pages)}")
        return all_pages

    @staticmethod
    def _clean_text(text: str) -> str:
        """Normalize whitespace and strip."""
        text = text.replace("\r", " ")
        text = re.sub(r"\s+", " ", text)
        return text.strip()