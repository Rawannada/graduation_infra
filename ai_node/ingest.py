import os
from dotenv import load_dotenv
from pdf_processor import process_all_pdfs
from src.chunker import split_into_chunks
from rag_pipeline import VectorStore

def main():
    load_dotenv()
    PDF_DIRECTORY = os.getenv("PDF_DIRECTORY", "./data/pdfs")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
    CHUNK_MAX_WORDS = int(os.getenv("CHUNK_SIZE", "300"))
    USE_OCR = os.getenv("USE_OCR", "false").lower() == "true"

    print("\n" + "=" * 80)
    print("PDF INGESTION & IN-MEMORY VECTOR STORE (FAISS)")
    print("=" * 80 + "\n")

    print("Step 1: Processing PDF files...")
    try:
        pages_data = process_all_pdfs(PDF_DIRECTORY, use_ocr=USE_OCR, use_sections=True)
        print(f"✓ Extracted {len(pages_data)} sections from PDFs\n")
    except Exception as e:
        print(f"✗ Error: {e}\n")
        return

    print("Step 2: Chunking sections...")
    chunked_data = []
    for section in pages_data:
        for chunk in split_into_chunks(section["text"], max_words=CHUNK_MAX_WORDS):
            chunked_data.append({
                "text": chunk,
                "filename": section["filename"],
                "page_num": section["page_num"],
                "source": section.get("source", section["filename"]),
                "section_title": section.get("section_title", ""),
            })
    print(f"✓ Total chunks: {len(chunked_data)}\n")

    print("Step 3: Creating FAISS vector store...")
    try:
        vector_store = VectorStore(embedding_model=EMBEDDING_MODEL)
        vector_store.create_vector_store(chunked_data)
        print("✓ FAISS vector store created!\n")
    except Exception as e:
        print(f"✗ Error: {e}\n")
        return

    print("=" * 80)
    print("INGESTION COMPLETE!")
    print("=" * 80)

if __name__ == "__main__":
    main()
