"""
PDF Extraction with comprehensive error handling
"""
import pdfplumber
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class PDFExtractionError(Exception):
    """Custom exception for PDF extraction errors"""
    pass


def validate_pdf_file(file_path: str) -> tuple:
    """
    Validate PDF file before processing
    
    Returns:
        tuple: (is_valid, error_message)
    """
    path = Path(file_path)
    
    if not path.exists():
        return False, f"File not found: {file_path}"
    
    if not path.is_file():
        return False, f"Path is not a file: {file_path}"
    
    if path.suffix.lower() != '.pdf':
        return False, f"File is not a PDF: {file_path}"
    
    file_size = path.stat().st_size
    if file_size == 0:
        return False, "PDF file is empty"
    
    max_size = 100 * 1024 * 1024  # 100MB
    if file_size > max_size:
        return False, f"PDF file too large: {file_size / (1024*1024):.1f}MB (max: 100MB)"
    
    return True, ""


def extract_pdf(file_path: str) -> str:
    """
    Extract text from PDF with comprehensive error handling
    
    Args:
        file_path: Path to PDF file
        
    Returns:
        str: Extracted and cleaned text
        
    Raises:
        PDFExtractionError: If extraction fails
    """
    is_valid, error_msg = validate_pdf_file(file_path)
    if not is_valid:
        logger.error(f"PDF validation failed: {error_msg}")
        raise PDFExtractionError(error_msg)
    
    text = ""
    pages_processed = 0
    
    try:
        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)
            logger.info(f"Processing PDF with {total_pages} pages: {file_path}")
            
            if total_pages == 0:
                raise PDFExtractionError("PDF has no pages")
            
            for page_num, page in enumerate(pdf.pages, start=1):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                        pages_processed += 1
                    else:
                        logger.warning(f"Page {page_num} has no extractable text")
                        
                except Exception as e:
                    logger.warning(f"Error extracting text from page {page_num}: {e}")
                    continue
            
            logger.info(f"Successfully processed {pages_processed}/{total_pages} pages")
            
    except FileNotFoundError:
        error_msg = f"PDF file not found: {file_path}"
        logger.error(error_msg)
        raise PDFExtractionError(error_msg)
        
    except PermissionError:
        error_msg = f"Permission denied accessing PDF: {file_path}"
        logger.error(error_msg)
        raise PDFExtractionError(error_msg)
        
    except Exception as e:
        error_msg = f"Failed to open or extract PDF: {str(e)}"
        logger.error(error_msg)
        raise PDFExtractionError(error_msg)
    
    if not text.strip():
        raise PDFExtractionError(
            "No text could be extracted from PDF. "
            "The file might be scanned images. Try using OCR."
        )
    
    try:
        text = clean_extracted_text(text)
    except Exception as e:
        logger.warning(f"Error cleaning text: {e}. Using raw text.")
    
    return text


def clean_extracted_text(text: str) -> str:
    """
    Clean extracted text with error handling
    """
    if not text:
        return ""
    
    try:
        text = text.replace('-\n', '').replace('.\n', '. ')
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        text = '\n'.join(lines)
        return text
        
    except Exception as e:
        logger.warning(f"Error in text cleaning: {e}")
        return text