"""
Ingest PDFs and Build In-Memory FAISS Vector Store
This is mainly a test script to verify PDF processing and embedding.
"""

import os
from dotenv import load_dotenv

from src.pdf_processor import process_all_pdfs
from src.vector_store import VectorStore


def main():
    # Load environment variables
    load_dotenv()

    # Configuration
    PDF_DIRECTORY = os.getenv("PDF_DIRECTORY", "./data/pdfs")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1500"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
    USE_OCR = os.getenv("USE_OCR", "false").lower() == "true"

    print("\n" + "=" * 80)
    print("PDF INGESTION & IN-MEMORY VECTOR STORE (FAISS)")
    print("=" * 80 + "\n")

    # Step 1: Process PDFs
    print("Step 1: Processing PDF files...")
    try:
        pages_data = process_all_pdfs(PDF_DIRECTORY, use_ocr=USE_OCR)
        print(f"\n✓ Successfully processed {len(pages_data)} entries from PDFs\n")
    except Exception as e:
        print(f"\n✗ Error processing PDFs: {e}\n")
        return

    # Step 2: Create in-memory FAISS store
    print("Step 2: Creating in-memory FAISS vector store...")
    try:
        vector_store = VectorStore(
            embedding_model=EMBEDDING_MODEL,
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        )
        vector_store.create_vector_store(pages_data)
        print("✓ FAISS vector store created in memory!\n")

    except Exception as e:
        print(f"\n✗ Error creating vector store: {e}\n")
        return

    print("=" * 80)
    print("INGESTION TEST COMPLETE!")
    print("=" * 80)
    print("\nNote: FAISS store is in memory only and will be lost when this script ends.\n")


if __name__ == "__main__":
    main()