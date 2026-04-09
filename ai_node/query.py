"""
Query the RAG System (FAISS, in-memory)
Run this to process PDFs, build a vector store in memory, and ask questions.
"""

import os
from dotenv import load_dotenv

from src.pdf_processor import process_all_pdfs
from src.vector_store import VectorStore
from src.rag_pipeline import RAGPipeline


def main():
    load_dotenv()

    # Configuration
    PDF_DIRECTORY = os.getenv("PDF_DIRECTORY", "./data/pdfs")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
    LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:1b")
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1500"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
    USE_OCR = os.getenv("USE_OCR", "false").lower() == "true"

    print("\n" + "=" * 80)
    print("CYBERSECURITY RAG ASSISTANT (FAISS, in-memory)")
    print("=" * 80 + "\n")

    # Step 1: Process PDFs
    print("Step 1: Processing PDF files...")
    try:
        if not os.path.exists(PDF_DIRECTORY):
            print(f"❌ PDF directory not found: {PDF_DIRECTORY}")
            print(f"   Creating directory...")
            os.makedirs(PDF_DIRECTORY, exist_ok=True)
            print(f"   ℹ️  Please add PDF files to {PDF_DIRECTORY} and run again.\n")
            return

        pages_data = process_all_pdfs(PDF_DIRECTORY, use_ocr=USE_OCR)

        if not pages_data:
            print(f"⚠️  No content extracted from PDFs in {PDF_DIRECTORY}")
            print(f"   Please check your PDF files and try again.\n")
            return

        print(f"\n✅ Successfully processed {len(pages_data)} entries from PDFs\n")

    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}\n")
        return
    except Exception as e:
        print(f"\n❌ Unexpected error processing PDFs: {e}\n")
        import traceback

        traceback.print_exc()
        return

    # Step 2: Create vector store
    print("Step 2: Creating in-memory FAISS vector store...")
    try:
        vector_store = VectorStore(
            embedding_model=EMBEDDING_MODEL,
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        )
        vector_store.create_vector_store(pages_data)

    except Exception as e:
        print(f"\n❌ Error creating vector store: {e}")
        print("   Make sure Ollama is running: ollama serve\n")
        import traceback

        traceback.print_exc()
        return

    # Step 3: Initialize RAG
    print("Step 3: Initializing RAG pipeline...\n")
    try:
        rag = RAGPipeline(
            vector_store=vector_store,
            llm_model=LLM_MODEL,
            base_url=OLLAMA_BASE_URL,
        )
    except ConnectionError as e:
        print(f"\n❌ {e}")
        print(f"   Run: ollama serve")
        print(f"   Then: ollama pull {LLM_MODEL}\n")
        return
    except Exception as e:
        print(f"\n❌ Error initializing RAG pipeline: {e}\n")
        import traceback

        traceback.print_exc()
        return

    print("✅ System ready!\n")
    print("=" * 80)
    print("Ask questions about your cybersecurity documents.")
    print("Type 'quit', 'exit', or 'q' to stop.")
    print("=" * 80 + "\n")

    # Query loop
    while True:
        try:
            question = input("\n💬 Your question: ").strip()

            if not question:
                continue

            if question.lower() in ["quit", "exit", "q"]:
                print("\n👋 Goodbye!\n")
                break

            print("\n🔍 Searching documents and generating answer...\n")

            result = rag.query(question)
            print(rag.format_response(result))

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!\n")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


if __name__ == "__main__":
    main()