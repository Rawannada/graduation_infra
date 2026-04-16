import hashlib
import pickle
import logging
from pathlib import Path
import numpy as np
import faiss
from embeddings import EmbeddingGenerator

# إعداد اللوجر
logger = logging.getLogger("VECTOR_STORE")

# ─────────────────────────────────────────────
# مسار تخزين الكاش
# ─────────────────────────────────────────────
CACHE_DIR = Path(__file__).parent / "vs_cache"
CACHE_DIR.mkdir(exist_ok=True)

def _cache_key(source: str) -> str:
    if len(source) == 24 and all(c in "0123456789abcdefABCDEF" for c in source):
        return source
    return hashlib.md5(str(source).encode()).hexdigest()

class VectorStore:
    def __init__(self, max_workers: int = 4):
        self.embedding_generator = EmbeddingGenerator(max_workers=max_workers)
        self.index = None
        self.documents = []    # المخزن الأساسي للنصوص والميتا داتا
        self.vectors = None    # المتجهات الموحدة (Normalized) للبحث
        self.embeddings = None # المتجهات الخام (Raw) للدمج الموزع

    # ─────────────────────────────────────────
    # الـ Aliases لضمان التوافق مع أي API (حل مشكلة AttributeError)
    # ─────────────────────────────────────────
    @property
    def chunks(self):
        return self.documents
    
    @chunks.setter
    def chunks(self, value):
        self.documents = value

    @property
    def metadata(self):
        return self.documents

    @metadata.setter
    def metadata(self, value):
        self.documents = value

    # ─────────────────────────────────────────
    # الحفظ والتحميل (Persistence)
    # ─────────────────────────────────────────

    def save(self, cache_source: str) -> None:
        if self.index is None:
            logger.warning("Nothing to save – index is empty.")
            return

        key = _cache_key(cache_source)
        index_path = CACHE_DIR / f"{key}.index"
        meta_path = CACHE_DIR / f"{key}.meta"

        faiss.write_index(self.index, str(index_path))

        with open(meta_path, "wb") as f:
            pickle.dump(
                {
                    "documents": self.documents,
                    "vectors": self.vectors,
                    "embeddings": self.embeddings,
                    "original_path": cache_source,
                },
                f,
                protocol=pickle.HIGHEST_PROTOCOL,
            )
        logger.info(f"💾 [CACHE] Saved vector store → {index_path.name}")

    def load(self, cache_source: str) -> bool:
        key = _cache_key(cache_source)
        index_path = CACHE_DIR / f"{key}.index"
        meta_path = CACHE_DIR / f"{key}.meta"

        if not index_path.exists() or not meta_path.exists():
            return False

        try:
            self.index = faiss.read_index(str(index_path))
            with open(meta_path, "rb") as f:
                meta = pickle.load(f)

            self.documents = meta.get("documents", [])
            self.vectors = meta.get("vectors")
            self.embeddings = meta.get("embeddings")

            logger.info(f"⚡ [CACHE] Loaded vector store from disk ({len(self.documents)} chunks)")
            return True
        except Exception as e:
            logger.error(f"⚠️ [CACHE] Failed to load cache ({e}), will rebuild.")
            return False

    # ─────────────────────────────────────────
    # بناء الفهرس (Build Methods)
    # ─────────────────────────────────────────

    def create_vector_store(self, pages_data: list, cache_source: str = None) -> None:
        valid_pages = [p for p in pages_data if p.get("text") and p["text"].strip()]
        if not valid_pages:
            logger.warning("No text found to index.")
            return

        texts = [p["text"] for p in valid_pages]
        embeddings = self.embedding_generator.embed_documents(texts)
        embeddings_np = np.array(embeddings).astype("float32")
        
        self._build_from_embeddings(embeddings_np, valid_pages)

        if cache_source:
            self.save(cache_source)

    def _build_from_embeddings(self, embeddings_np: np.ndarray, pages_metadata: list):
        """المنطق الجوهري لدمج المتجهات وتحديث الفهرس"""
        # 1. تحديث المتجهات الخام
        if self.embeddings is None:
            self.embeddings = embeddings_np
        else:
            self.embeddings = np.vstack([self.embeddings, embeddings_np])
        
        # 2. التوحيد (Normalization) للبحث بدقة أعلى
        norms = np.linalg.norm(embeddings_np, axis=1, keepdims=True)
        norms[norms == 0] = 1
        new_vectors = embeddings_np / norms
        
        if self.vectors is None:
            self.vectors = new_vectors
        else:
            self.vectors = np.vstack([self.vectors, new_vectors])

        # 3. تحديث فهرس Faiss
        dimension = embeddings_np.shape[1]
        if self.index is None:
            self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings_np)

        # 4. تحديث المستندات
        new_docs = [
            {
                "text": p["text"],
                "source": p.get("filename", "unknown"),
                "page": p.get("page_num", 0),
                "section_title": p.get("section_title", ""),
            }
            for p in pages_metadata
        ]
        self.documents.extend(new_docs)

    # ─────────────────────────────────────────
    # البحث (Search)
    # ─────────────────────────────────────────

    def search(self, query: str, k: int = 4) -> list:
        if self.index is None: return []
        query_vector = np.array([self.embedding_generator.embed_query(query)]).astype("float32")
        _, indices = self.index.search(query_vector, k)
        
        results = []
        for i in indices[0]:
            if i != -1 and i < len(self.documents):
                results.append(self.documents[i])
        
        results.sort(key=lambda x: x["page"])
        return results