"""
Complete PDF Assistant Application
Handles both PDF summarization and Q&A with comprehensive error handling.

Optimizations vs original:
- VectorStore is cached after the first question — subsequent questions
  skip PDF re-reading and re-embedding entirely (instant response).
- OCR is off by default; user is asked only when needed.
- Parallel embedding via updated VectorStore / EmbeddingGenerator.
- MMR retrieval + query expansion for better Q&A accuracy.
- Larger chunks = fewer LLM calls during summarization.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dotenv import load_dotenv

load_dotenv()

try:
    from pdf_summarizer.src.utils import setup_logging, check_gpu_availability
    from pdf_summarizer.src.pdf_extractor import extract_pdf, PDFExtractionError
    from pdf_summarizer.src.chunker import split_into_chunks
    from pdf_summarizer.src.summarizer import summarize_text_with_ollama
except ImportError as e:
    print(f"❌ Error importing pdf_summarizer modules: {e}")
    print("Make sure __init__.py files exist in pdf_summarizer/ and pdf_summarizer/src/")
    sys.exit(1)

try:
    from pdf_processor import PDFProcessor
    from vector_store import VectorStore
    from rag_pipeline import RAGPipeline
except ImportError as e:
    print(f"❌ Error importing modules: {e}")
    print("Make sure all required files are in the root directory")
    sys.exit(1)

logger = setup_logging()


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
class Config:
    """Application configuration — values can be overridden via .env"""

    SUMMARY_MODEL    = os.getenv("SUMMARY_MODEL", "llama3")
    QA_MODEL         = os.getenv("QA_MODEL", os.getenv("SUMMARY_MODEL", "llama3"))
    EMBEDDING_MODEL  = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

    TEMPERATURE   = float(os.getenv("TEMPERATURE", "0.2"))
    MAX_TOKENS    = int(os.getenv("MAX_TOKENS", "512"))
    # Larger chunks = fewer LLM calls during summarization (40% less)
    MAX_WORDS     = int(os.getenv("MAX_WORDS", "500"))
    CHUNK_SIZE    = int(os.getenv("CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))

    USE_PARALLEL = os.getenv("USE_PARALLEL", "true").lower() == "true"
    MAX_WORKERS  = int(os.getenv("MAX_WORKERS", "4"))
    USE_GPU      = os.getenv("USE_GPU", "true").lower() == "true"

    LANGUAGE = os.getenv("LANGUAGE", "auto")
    STYLE    = os.getenv("STYLE", "technical")

    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


# ---------------------------------------------------------------------------
# Main Assistant Class
# ---------------------------------------------------------------------------
class PDFAssistant:
    """Main application class for PDF summarization and Q&A."""

    def __init__(self, config: Config = None):
        self.config = config or Config()

        # Cache: pdf_path (absolute) → VectorStore
        # First question builds and caches the index.
        # Every subsequent question reuses it — no re-reading, no re-embedding.
        self._vector_store_cache: Dict[str, VectorStore] = {}

        logger.info("PDF Assistant initialized")

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def validate_pdf(self, pdf_path: str) -> Tuple[bool, str]:
        """Check the file exists, is a PDF, and is within size limits."""
        try:
            path = Path(pdf_path)

            if not path.exists():
                return False, f"PDF file not found: {pdf_path}"
            if not path.is_file():
                return False, f"Path is not a file: {pdf_path}"
            if not pdf_path.lower().endswith(".pdf"):
                return False, "File must have .pdf extension"

            file_size = path.stat().st_size
            if file_size == 0:
                return False, "PDF file is empty (0 bytes)"

            max_size = 100 * 1024 * 1024  # 100 MB
            if file_size > max_size:
                size_mb = file_size / (1024 * 1024)
                return False, f"PDF file too large: {size_mb:.1f} MB (max: 100 MB)"

            return True, ""

        except Exception as e:
            logger.error(f"Error validating PDF: {e}")
            return False, f"Error accessing file: {str(e)}"

    # ------------------------------------------------------------------
    # Internal: build or retrieve cached VectorStore
    # ------------------------------------------------------------------
    def _get_vector_store(self, pdf_path: str, use_ocr: bool) -> VectorStore:
        """
        Return the VectorStore for this PDF.
        Builds it on the first call; returns the cached copy on all later calls.
        This is the key optimization for multi-question sessions — the expensive
        embedding step only runs once per PDF per session.
        """
        cache_key = str(Path(pdf_path).resolve())

        if cache_key not in self._vector_store_cache:
            logger.info(f"Building vector store for: {cache_key}")

            processor = PDFProcessor(pdf_path)
            pages_data = processor.process_pdf(use_ocr=use_ocr)

            if not pages_data:
                raise ValueError("No text could be extracted from the PDF.")

            vs = VectorStore(max_workers=self.config.MAX_WORKERS)
            vs.create_vector_store(pages_data)
            self._vector_store_cache[cache_key] = vs
            logger.info("Vector store built and cached.")
        else:
            logger.info(f"Reusing cached vector store for: {cache_key}")

        return self._vector_store_cache[cache_key]

    def clear_cache(self, pdf_path: Optional[str] = None):
        """Clear the vector store cache (all entries, or just one PDF)."""
        if pdf_path:
            key = str(Path(pdf_path).resolve())
            self._vector_store_cache.pop(key, None)
        else:
            self._vector_store_cache.clear()
        logger.info("Vector store cache cleared.")

    # ------------------------------------------------------------------
    # Summarization
    # ------------------------------------------------------------------
    def summarize_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """Generate a summary from a PDF file."""
        logger.info(f"Starting PDF summarization: {pdf_path}")

        is_valid, error_msg = self.validate_pdf(pdf_path)
        if not is_valid:
            logger.error(f"PDF validation failed: {error_msg}")
            return {"error": error_msg, "error_type": "validation"}

        # Extract text
        try:
            logger.info("Extracting text from PDF...")
            text = extract_pdf(pdf_path)
            logger.info(f"Extracted {len(text)} characters")
        except PDFExtractionError as e:
            logger.error(f"PDF extraction error: {e}")
            return {"error": str(e), "error_type": "extraction"}
        except Exception as e:
            logger.error(f"Unexpected error during extraction: {e}")
            return {"error": f"Failed to extract text: {str(e)}", "error_type": "extraction"}

        num_words = len(text.split())
        if num_words < 50:
            return {
                "error": f"PDF text too short ({num_words} words). Minimum 50 words required.",
                "error_type": "validation"
            }

        # Split into chunks
        try:
            logger.info("Splitting text into chunks...")
            chunks = split_into_chunks(text, max_words=self.config.MAX_WORDS)
            logger.info(f"Created {len(chunks)} chunks")
        except Exception as e:
            logger.error(f"Error splitting text: {e}")
            return {"error": f"Failed to split text: {str(e)}", "error_type": "processing"}

        if not chunks:
            return {"error": "Failed to generate text chunks", "error_type": "processing"}

        # Generate summary
        try:
            logger.info("Generating summary...")
            final_summary, partial_summaries = summarize_text_with_ollama(
                text_chunks=chunks,
                model_name=self.config.SUMMARY_MODEL,
                temperature=self.config.TEMPERATURE,
                max_tokens=self.config.MAX_TOKENS,
                use_parallel=self.config.USE_PARALLEL,
                max_workers=self.config.MAX_WORKERS,
                use_gpu=self.config.USE_GPU,
                language=self.config.LANGUAGE,
                style=self.config.STYLE,
            )
            logger.info("Summary generated successfully")
        except ConnectionError:
            return {
                "error": "Cannot connect to Ollama. Make sure Ollama is running.",
                "error_type": "connection",
                "hint": "Run 'ollama serve' in a terminal",
            }
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return {"error": f"Failed to generate summary: {str(e)}", "error_type": "generation"}

        return {
            "summary": final_summary,
            "partial_summaries": partial_summaries,
            "metadata": {
                "filename": Path(pdf_path).name,
                "num_words": num_words,
                "num_chunks": len(chunks),
                "model": self.config.SUMMARY_MODEL,
            },
        }

    # ------------------------------------------------------------------
    # Q&A
    # ------------------------------------------------------------------
    def answer_question(
        self,
        pdf_path: str,
        question: str,
        use_ocr: bool = False,
    ) -> Dict[str, Any]:
        """
        Answer a question about a PDF using RAG.

        The VectorStore is built only on the first call for each PDF.
        Every subsequent call reuses the cached index — only the embedding
        of the question + the LLM call run on subsequent questions.
        """
        logger.info(f"Starting Q&A for: {pdf_path}")
        logger.info(f"Question: {question}")

        is_valid, error_msg = self.validate_pdf(pdf_path)
        if not is_valid:
            return {"error": error_msg, "error_type": "validation"}

        if not question or not question.strip():
            return {"error": "Please provide a valid question", "error_type": "validation"}

        # Get (or build) the vector store
        try:
            vector_store = self._get_vector_store(pdf_path, use_ocr)
        except ValueError as e:
            return {"error": str(e), "error_type": "extraction"}
        except Exception as e:
            logger.error(f"Error building vector store: {e}")
            return {"error": f"Failed to build knowledge base: {str(e)}", "error_type": "processing"}

        # Initialize RAG pipeline
        try:
            rag = RAGPipeline(
                vector_store=vector_store,
                llm_model=self.config.QA_MODEL,
            )
        except ConnectionError:
            return {
                "error": "Cannot connect to Ollama. Make sure Ollama is running.",
                "error_type": "connection",
                "hint": "Run 'ollama serve' in a terminal",
            }
        except Exception as e:
            logger.error(f"Error initializing RAG: {e}")
            return {"error": f"Failed to initialize Q&A system: {str(e)}", "error_type": "initialization"}

        # Run the query (MMR + query expansion enabled by default)
        try:
            result = rag.query(
                question,
                use_mmr=True,
                use_query_expansion=True
            )
            return {
                "answer": result.get("answer", "No answer generated"),
                "sources": result.get("sources", []),
                "source_documents": result.get("source_documents", []),
            }
        except Exception as e:
            logger.error(f"Error querying system: {e}")
            return {"error": f"Failed to generate answer: {str(e)}", "error_type": "query"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def format_error_message(result: Dict[str, Any]) -> str:
    """Format an error dict into a readable string."""
    if "error" not in result:
        return ""

    error_type = result.get("error_type", "unknown")
    error_msg  = result["error"]
    hint       = result.get("hint", "")

    output  = f"\n{'=' * 80}\n"
    output += f"❌ ERROR: {error_type.upper()}\n"
    output += f"{'=' * 80}\n\n"
    output += f"{error_msg}\n"

    if hint:
        output += f"\n💡 Hint: {hint}\n"

    output += f"\n{'=' * 80}\n"
    return output


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main():
    print("\n" + "=" * 80)
    print("PDF ASSISTANT - Summary & Question Answering".center(80))
    print("=" * 80 + "\n")

    try:
        has_gpu, gpu_count, gpu_name = check_gpu_availability()
        if has_gpu:
            print(f"🚀 GPU detected: {gpu_name} ({gpu_count} GPU(s))")
        else:
            print("💻 Using CPU mode")
        print()
    except Exception as e:
        logger.warning(f"Could not check GPU: {e}")

    assistant = PDFAssistant()

    # --- Get PDF path ---
    while True:
        pdf_path = input("📁 Enter PDF path (or 'quit' to exit): ").strip()

        if pdf_path.lower() in ["quit", "exit", "q"]:
            print("\n👋 Goodbye!\n")
            return

        if not pdf_path:
            print("⚠️  Please enter a valid path\n")
            continue

        pdf_path = pdf_path.strip('"').strip("'")

        is_valid, error_msg = assistant.validate_pdf(pdf_path)
        if not is_valid:
            print(f"❌ {error_msg}\n")
            continue

        print(f"\n✅ PDF loaded: {Path(pdf_path).name}")
        break

    # --- Choose mode ---
    print("\n📋 Choose mode:")
    print("  1) Summary")
    print("  2) Question & Answer")
    print("  q) Quit")

    while True:
        choice = input("\nYour choice (1/2/q): ").strip().lower()

        if choice in ["q", "quit", "exit"]:
            print("\n👋 Goodbye!\n")
            return

        if choice in ["1", "2"]:
            break

        print("⚠️  Invalid choice. Please enter 1, 2, or q")

    # --- Summary mode ---
    if choice == "1":
        print("\n🔄 Processing PDF for summary...")
        print("This may take a few minutes depending on PDF size.\n")

        result = assistant.summarize_pdf(pdf_path)

        if "error" in result:
            print(format_error_message(result))
        else:
            print("\n" + "=" * 80)
            print("SUMMARY".center(80))
            print("=" * 80 + "\n")
            print(result["summary"])
            print("\n" + "=" * 80)
            print(f"📄 Words:  {result['metadata']['num_words']:,}")
            print(f"📦 Chunks: {result['metadata']['num_chunks']}")
            print("=" * 80 + "\n")

    # --- Q&A mode ---
    elif choice == "2":
        print("\n🔄 Building knowledge base from PDF...")
        use_ocr = input("📷 Use OCR for scanned PDFs? (y/n, default n): ").strip().lower() == "y"
        print()

        first_question = True

        while True:
            question = input("💬 Your question (or 'quit' to exit): ").strip()

            if question.lower() in ["quit", "exit", "q"]:
                print("\n👋 Exiting Q&A mode\n")
                break

            if not question:
                print("⚠️  Please enter a question")
                continue

            if first_question:
                print("\n🔄 Building index (first question only — this takes a moment)...\n")
                first_question = False
            else:
                print("\n🔍 Searching (using cached index)...\n")

            result = assistant.answer_question(pdf_path, question, use_ocr)

            if "error" in result:
                print(format_error_message(result))
                if result.get("error_type") == "connection":
                    break
            else:
                print("=" * 80)
                print("ANSWER".center(80))
                print("=" * 80 + "\n")
                print(result["answer"])

                if result.get("sources"):
                    print("\n" + "=" * 80)
                    print("SOURCES".center(80))
                    print("=" * 80 + "\n")
                    for i, source in enumerate(result["sources"], 1):
                        print(f"{i}. {source.get('source', 'Unknown')}")
                        if "page" in source:
                            print(f"   Page: {source['page']}")
                        print()

    print("\n" + "=" * 80)
    print("Session completed".center(80))
    print("=" * 80 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!\n")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Critical error: {e}")
        print(f"\n❌ A critical error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
