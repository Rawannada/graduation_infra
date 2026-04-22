import re
import logging
import os
import io
from pathlib import Path

import pytesseract
from pdf2image import convert_from_bytes, convert_from_path
from pypdf import PdfReader

logger = logging.getLogger(__name__)

# Path to Tesseract OCR binary
# Windows default path — change to /usr/bin/tesseract if running on Linux
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


class PDFProcessor:
    def __init__(self, pdf_source):
        # pdf_source can be:
        # - a file path string or Path object (used on the manager machine)
        # - a BytesIO object (used on worker machines receiving PDF bytes over HTTP)
        self.pdf_source = pdf_source

        if isinstance(pdf_source, (str, Path)):
            self.filename = Path(pdf_source).name
        elif hasattr(pdf_source, 'name') and pdf_source.name:
            self.filename = pdf_source.name
        else:
            self.filename = "document.pdf"

    # ─────────────────────────────────────────
    # HEADER DETECTION
    # Detects whether a text line is a section header.
    # Used by _split_into_sections to segment the document.
    # ─────────────────────────────────────────

    @staticmethod
    def _is_header(line: str) -> bool:
        line = line.strip()
        if not line or len(line) < 3:
            return False

        # Lines that are never headers (instructions, figures, numbered steps)
        exclude_patterns = [
            r'^(Examine|Click|Right-click|Select|Open|Press|Navigate|Go to|Type|Enter)\s+',
            r'^Figure\s+\d+',
            r'^F\s*i\s*g\s*[Uu]\s*[Rr]\s*[Ee]',
            r'^\d+\.\s+',
        ]
        for pattern in exclude_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                return False

        # Rule 1: ALL CAPS with at least 2 words
        if line.isupper() and len(line.split()) >= 2:
            return True

        # Rule 2: Numbered section like "1.2 Title" or "1. Title"
        if re.match(r'^\d+[\.\-]\d*\s+\w+', line):
            return True

        # Rule 3: Line ending with colon and short enough to be a header
        if line.endswith(':') and len(line.split()) <= 8:
            return True

        # Rule 4: Known document section keywords
        known_patterns = [
            r'^(Chapter|Section|Part|Unit)\s+\d+',
            r'^(Introduction|Conclusion|Summary|Overview|Background|References|Appendix)\b',
            r'^(Abstract|Methodology|Results|Discussion|Analysis|Recommendations)\b',
        ]
        for pattern in known_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                return True

        # Rule 5: Title Case, short, no trailing punctuation, no special chars
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

    # ─────────────────────────────────────────
    # SECTION SPLITTER
    # Groups consecutive lines under their nearest header.
    # Returns a list of section dicts with section_title attached.
    # ─────────────────────────────────────────

    def _split_into_sections(self, pages_data):
        all_lines = []
        for page in pages_data:
            for line in page["text"].split(". "):
                all_lines.append({
                    "text":     line.strip(),
                    "page_num": page["page_num"],
                    "filename": page["filename"],
                })

        if not all_lines:
            return pages_data

        sections       = []
        current_header = "Introduction"
        current_lines  = []
        current_page   = all_lines[0]["page_num"]

        for line_data in all_lines:
            line = line_data["text"]
            if not line:
                continue

            if self._is_header(line):
                if current_lines:
                    sections.append({
                        "page_num":      current_page,
                        "text":          f"{current_header}\n\n" + ". ".join(current_lines),
                        "source":        f"{self.filename} — {current_header}",
                        "type":          "section",
                        "filename":      self.filename,
                        "section_title": current_header,
                    })
                current_header = line
                current_lines  = []
                current_page   = line_data["page_num"]
            else:
                current_lines.append(line)

        if current_lines:
            sections.append({
                "page_num":      current_page,
                "text":          f"{current_header}\n\n" + ". ".join(current_lines),
                "source":        f"{self.filename} — {current_header}",
                "type":          "section",
                "filename":      self.filename,
                "section_title": current_header,
            })

        logger.info(f"[SECTIONS] Detected {len(sections)} sections.")
        return sections if sections else pages_data

    # ─────────────────────────────────────────
    # TEXT EXTRACTION
    # Extracts raw text from a given page range using pypdf.
    # Works with both file paths and BytesIO objects.
    # ─────────────────────────────────────────

    def extract_text_from_pdf(self, start_page: int = 0, end_page: int = None):
        pages_data = []
        try:
            reader      = PdfReader(self.pdf_source)
            total_pages = len(reader.pages)
            actual_end  = end_page if end_page is not None else total_pages

            for i in range(max(0, start_page), min(total_pages, actual_end)):
                page = reader.pages[i]
                text = self._clean_text(page.extract_text() or "")
                if text.strip():
                    pages_data.append({
                        "page_num": i + 1,
                        "text":     text,
                        "source":   f"{self.filename} — page {i + 1}",
                        "type":     "text",
                        "filename": self.filename,
                    })
        except Exception as e:
            logger.error(f"[EXTRACT] ERROR: Text extraction failed — {e}")
        return pages_data

    # ─────────────────────────────────────────
    # OCR EXTRACTION
    # Converts PDF pages to images and runs Tesseract OCR.
    # Used as a fallback when text extraction produces poor results.
    # ─────────────────────────────────────────

    def extract_text_with_ocr(self, start_page: int = 0, end_page: int = None):
        pages_data = []
        try:
            if isinstance(self.pdf_source, (str, Path)):
                images = convert_from_path(
                    self.pdf_source, dpi=150,
                    first_page=start_page + 1, last_page=end_page
                )
            else:
                # BytesIO path — seek to start before reading
                self.pdf_source.seek(0)
                images = convert_from_bytes(
                    self.pdf_source.read(), dpi=150,
                    first_page=start_page + 1, last_page=end_page
                )

            for i, image in enumerate(images):
                ocr_text = self._clean_text(pytesseract.image_to_string(image, lang="eng") or "")
                if ocr_text.strip():
                    pages_data.append({
                        "page_num": start_page + i + 1,
                        "text":     ocr_text,
                        "source":   f"{self.filename} — page {start_page + i + 1} (OCR)",
                        "type":     "ocr",
                        "filename": self.filename,
                    })
        except Exception as e:
            logger.error(f"[OCR] ERROR: OCR extraction failed — {e}")
        return pages_data

    # ─────────────────────────────────────────
    # MAIN ENTRY POINT
    # Runs the full extraction pipeline for a given page range.
    # OCR is used to supplement pages with very little extracted text.
    # Section splitting groups lines under their nearest detected header.
    # ─────────────────────────────────────────

    def process_pdf(
        self,
        use_ocr:      bool = False,
        use_sections: bool = True,
        start_page:   int  = 0,
        end_page:     int  = None
    ):
        logger.info(f"=== Processing: {self.filename} (Pages {start_page}-{end_page}) ===")

        all_pages = self.extract_text_from_pdf(start_page, end_page)

        if use_ocr:
            ocr_pages = self.extract_text_with_ocr(start_page, end_page)
            for ocr_p in ocr_pages:
                existing = next((p for p in all_pages if p["page_num"] == ocr_p["page_num"]), None)
                # Replace page if text was missing or too short
                if not existing or len(existing["text"]) < 100:
                    if existing:
                        all_pages.remove(existing)
                    all_pages.append(ocr_p)

        all_pages.sort(key=lambda x: x["page_num"])

        if use_sections:
            all_pages = self._split_into_sections(all_pages)

        logger.info(f"[PROCESS] Done. Total entries: {len(all_pages)}")
        return all_pages

    # ─────────────────────────────────────────
    # TEXT CLEANER
    # Removes carriage returns and collapses whitespace
    # ─────────────────────────────────────────

    @staticmethod
    def _clean_text(text: str) -> str:
        text = text.replace("\r", " ")
        text = re.sub(r"\s+", " ", text)
        return text.strip()
