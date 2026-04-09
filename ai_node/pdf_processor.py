import re, logging, os
from typing import List, Dict, Any
from pathlib import Path
import pytesseract
from pdf2image import convert_from_path
from pypdf import PdfReader

logger = logging.getLogger(__name__)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


class PDFProcessor:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.filename = Path(pdf_path).name

    @staticmethod
    def _is_header(line: str) -> bool:
        line = line.strip()
        if not line or len(line) < 3:
            return False

        # ✅ Exclusions أول حاجة
        exclude_patterns = [
            r'^(Examine|Click|Right-click|Select|Open|Press|Navigate|Go to|Type|Enter)\s+',
            r'^Figure\s+\d+',
            r'^F\s*i\s*g\s*[Uu]\s*[Rr]\s*[Ee]',
            r'^\d+\.\s+',
        ]
        for pattern in exclude_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                return False

        # Rule 1: ALL CAPS (min 2 words)
        if line.isupper() and len(line.split()) >= 2:
            return True

        # Rule 2: Numbered section "1.2 Title" or "1. Title"
        if re.match(r'^\d+[\.\-]\d*\s+\w+', line):
            return True

        # Rule 3: Ends with colon → definite header
        if line.endswith(':') and len(line.split()) <= 8:
            return True

        # Rule 4: General patterns
        known_patterns = [
            r'^(Chapter|Section|Part|Unit)\s+\d+',
            r'^(Introduction|Conclusion|Summary|Overview|Background|References|Appendix)\b',
            r'^(Abstract|Methodology|Results|Discussion|Analysis|Recommendations)\b',
        ]
        for pattern in known_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                return True

        # Rule 5: Title Case, short, no punctuation at end
        words = line.split()
        if (
            3 <= len(words) <= 8
            and not line.endswith(('.', ',', ';', '?', '!'))
            and sum(1 for w in words if w[0].isupper()) >= len(words) * 0.6
            and len(line) < 70
            and not any(c in line for c in ['(', ')', '=', '+'])
        ):
            return True

        return False

    def _split_into_sections(self, pages_data):
        all_lines = []
        for page in pages_data:
            for line in page["text"].split(". "):
                all_lines.append({
                    "text": line.strip(),
                    "page_num": page["page_num"],
                    "filename": page["filename"]
                })
        if not all_lines:
            return pages_data
        sections = []
        current_header = "Introduction"
        current_lines = []
        current_page = all_lines[0]["page_num"]
        for line_data in all_lines:
            line = line_data["text"]
            if not line:
                continue
            if self._is_header(line):
                if current_lines:
                    sections.append({
                        "page_num": current_page,
                        "text": f"{current_header}\n\n" + ". ".join(current_lines),
                        "source": f"{self.filename} — {current_header}",
                        "type": "section",
                        "filename": self.filename,
                        "section_title": current_header
                    })
                current_header = line
                current_lines = []
                current_page = line_data["page_num"]
            else:
                current_lines.append(line)
        if current_lines:
            sections.append({
                "page_num": current_page,
                "text": f"{current_header}\n\n" + ". ".join(current_lines),
                "source": f"{self.filename} — {current_header}",
                "type": "section",
                "filename": self.filename,
                "section_title": current_header
            })
        logger.info(f"  ✓ Detected {len(sections)} sections from headers")
        return sections if sections else pages_data

    def extract_text_from_pdf(self):
        pages_data = []
        try:
            reader = PdfReader(self.pdf_path)
            for page_num, page in enumerate(reader.pages, start=1):
                text = self._clean_text(page.extract_text() or "")
                if text.strip():
                    pages_data.append({
                        "page_num": page_num,
                        "text": text,
                        "source": f"{self.filename} — page {page_num}",
                        "type": "text",
                        "filename": self.filename,
                    })
        except Exception as e:
            logger.error(f"Error extracting text: {e}")
        return pages_data

    def extract_text_with_ocr(self):
        pages_data = []
        try:
            images = convert_from_path(self.pdf_path, dpi=150)
            for page_num, image in enumerate(images, start=1):
                ocr_text = self._clean_text(pytesseract.image_to_string(image, lang="eng") or "")
                if ocr_text.strip():
                    pages_data.append({
                        "page_num": page_num,
                        "text": ocr_text,
                        "source": f"{self.filename} — page {page_num} (OCR)",
                        "type": "ocr",
                        "filename": self.filename,
                    })
        except Exception as e:
            logger.error(f"Error performing OCR: {e}")
        return pages_data

    def process_pdf(self, use_ocr: bool = False, use_sections: bool = True):
        logger.info(f"\n=== Processing PDF: {self.filename} ===")
        text_pages = self.extract_text_from_pdf()
        all_pages = list(text_pages)
        if use_ocr:
            ocr_pages = self.extract_text_with_ocr()
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
        if use_sections:
            all_pages = self._split_into_sections(all_pages)
        logger.info(f"  ✓ Total entries: {len(all_pages)}")
        return all_pages

    @staticmethod
    def _clean_text(text: str) -> str:
        text = text.replace("\r", " ")
        text = re.sub(r"\s+", " ", text)
        return text.strip()


def process_all_pdfs(pdf_directory: str, use_ocr: bool = False, use_sections: bool = True):
    all_pages = []
    pdf_files = [f for f in os.listdir(pdf_directory) if f.endswith(".pdf")]
    if not pdf_files:
        logger.warning(f"No PDF files found in {pdf_directory}")
        return []
    for pdf_file in pdf_files:
        processor = PDFProcessor(os.path.join(pdf_directory, pdf_file))
        all_pages.extend(processor.process_pdf(use_ocr=use_ocr, use_sections=use_sections))
    return all_pages
