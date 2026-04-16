import hashlib
import pickle
from pathlib import Path

import numpy as np
import faiss
from embeddings import EmbeddingGenerator

# ─────────────────────────────────────────────
# Where cached indexes are stored on disk
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
        self.documents = []
        self.vectors = None

    # ─────────────────────────────────────────
    # Persistence helpers
    # ─────────────────────────────────────────

    def save(self, cache_source: str) -> None:
        if self.index is None:
            print("⚠️ Nothing to save – index is empty.")
            return

        key        = _cache_key(cache_source)
        index_path = CACHE_DIR / f"{key}.index"
        meta_path  = CACHE_DIR / f"{key}.meta"

        faiss.write_index(self.index, str(index_path))

        with open(meta_path, "wb") as f:
            pickle.dump(
                {
                    "documents":     self.documents,
                    "vectors":       self.vectors,
                    "original_path": cache_source,
                },
                f,
                protocol=pickle.HIGHEST_PROTOCOL,
            )

        print(f"💾 [CACHE] Saved vector store → {index_path.name}")

    def load(self, cache_source: str) -> bool:
        key        = _cache_key(cache_source)
        index_path = CACHE_DIR / f"{key}.index"
        meta_path  = CACHE_DIR / f"{key}.meta"

        if not index_path.exists() or not meta_path.exists():
            return False

        try:
            self.index = faiss.read_index(str(index_path))

            with open(meta_path, "rb") as f:
                meta = pickle.load(f)

            self.documents = meta["documents"]
            self.vectors   = meta["vectors"]

            print(f"⚡ [CACHE] Loaded vector store from disk ({len(self.documents)} chunks)")
            return True

        except Exception as e:
            print(f"⚠️ [CACHE] Failed to load cache ({e}), will rebuild.")
            return False

    # ─────────────────────────────────────────
    # Build
    # ─────────────────────────────────────────

    def create_vector_store(self, pages_data: list, cache_source: str = None) -> None:
        valid_pages = [p for p in pages_data if p.get("text") and p["text"].strip()]

        if not valid_pages:
            print("⚠️ No text found to index.")
            return

        texts = [p["text"] for p in valid_pages]

        # [FIX] حفظ section_title جوه الـ documents عشان الـ RAG pipeline يقدر يستخدمه
        self.documents = [
            {
                "text":          p["text"],
                "source":        p["filename"],
                "page":          p["page_num"],
                "section_title": p.get("section_title", ""),
            }
            for p in valid_pages
        ]

        print(f"[INFO] Generating embeddings for {len(texts)} chunks (parallel)...")
        embeddings    = self.embedding_generator.embed_documents(texts)
        embeddings_np = np.array(embeddings).astype("float32")

        norms = np.linalg.norm(embeddings_np, axis=1, keepdims=True)
        norms[norms == 0] = 1
        self.vectors = embeddings_np / norms

        dimension  = embeddings_np.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings_np)
        print(f"✅ FAISS Index created with {len(texts)} chunks.")

        if cache_source:
            self.save(cache_source)

    # ─────────────────────────────────────────
    # Distributed Processing Helper
    # ─────────────────────────────────────────

    def merge_with(self, other_store: "VectorStore") -> None:
        """
        يدمج الـ VectorStore القادم من worker تاني (partial index)
        مع الـ index الحالي.
        يشتغل مع IndexFlatL2 عن طريق reconstruct_n بدل merge_from
        اللي بتشتغل بس مع IndexIVF.
        """
        if other_store.index is None or other_store.index.ntotal == 0:
            return

        n = other_store.index.ntotal
        d = other_store.index.d

        # [FIX] استخدام reconstruct_n بدل merge_from لأن IndexFlatL2 مش بيدعمها
        other_vecs = np.zeros((n, d), dtype="float32")
        other_store.index.reconstruct_n(0, n, other_vecs)

        if self.index is None:
            self.index     = faiss.IndexFlatL2(d)
            self.documents = []
            self.vectors   = None

        self.index.add(other_vecs)
        self.documents.extend(other_store.documents)

        if self.vectors is not None and other_store.vectors is not None:
            self.vectors = np.vstack([self.vectors, other_store.vectors])
        elif other_store.vectors is not None:
            self.vectors = other_store.vectors

    # ─────────────────────────────────────────
    # Search methods
    # ─────────────────────────────────────────

    def search(self, query: str, k: int = 4) -> list:
        if self.index is None:
            return []
        query_vector = np.array(
            [self.embedding_generator.embed_query(query)]
        ).astype("float32")
        _, indices = self.index.search(query_vector, k)
        results = [
            (i, self.documents[i])
            for i in indices[0]
            if i != -1 and i < len(self.documents)
        ]
        results.sort(key=lambda x: x[1]["page"])
        return results

    def search_with_keyword_boost(self, query: str, keywords: list,
                                   k: int = 4, keyword_bonus: float = 0.4) -> list:
        if self.index is None or self.vectors is None:
            return []

        query_vec = np.array(
            [self.embedding_generator.embed_query(query)]
        ).astype("float32")
        q_norm = np.linalg.norm(query_vec)
        query_vec_norm = query_vec / q_norm if q_norm > 0 else query_vec

        all_sims = (self.vectors @ query_vec_norm.T).flatten()

        scored = []
        for doc_idx, doc in enumerate(self.documents):
            text_lower = doc["text"].lower()
            boost = sum(
                keyword_bonus
                for kw in keywords
                if kw.lower() in text_lower
            )
            scored.append((doc_idx, float(all_sims[doc_idx]) + boost))

        scored.sort(key=lambda x: x[1], reverse=True)
        top_results = [self.documents[doc_idx] for doc_idx, _ in scored[:k]]
        top_results.sort(key=lambda x: x["page"])
        return top_results

    def search_mmr(self, query: str, k: int = 4, fetch_k: int = 12,
                    lambda_mult: float = 0.75) -> list:
        if self.index is None or self.vectors is None:
            return []

        query_vec = np.array(
            [self.embedding_generator.embed_query(query)]
        ).astype("float32")
        q_norm = np.linalg.norm(query_vec)
        query_vec_norm = query_vec / q_norm if q_norm > 0 else query_vec

        fetch_k = min(fetch_k, len(self.documents))
        _, raw_indices = self.index.search(query_vec, fetch_k)
        candidate_indices = [
            i for i in raw_indices[0]
            if i != -1 and i < len(self.documents)
        ]

        if not candidate_indices:
            return []

        candidate_vecs = self.vectors[candidate_indices]
        query_sims     = (candidate_vecs @ query_vec_norm.T).flatten()

        selected_positions   = []
        selected_doc_indices = []

        for _ in range(min(k, len(candidate_indices))):
            best_pos, best_score = None, -999.0

            for pos, doc_idx in enumerate(candidate_indices):
                if pos in selected_positions:
                    continue

                relevance = float(query_sims[pos])

                if selected_doc_indices:
                    selected_vecs       = self.vectors[selected_doc_indices]
                    max_sim_to_selected = float(
                        np.max(selected_vecs @ self.vectors[doc_idx])
                    )
                    diversity = 1.0 - max_sim_to_selected
                else:
                    diversity = 1.0

                score = lambda_mult * relevance + (1.0 - lambda_mult) * diversity

                if score > best_score:
                    best_score = score
                    best_pos   = pos

            if best_pos is not None:
                selected_positions.append(best_pos)
                selected_doc_indices.append(candidate_indices[best_pos])

        final_results = [self.documents[i] for i in selected_doc_indices]
        final_results.sort(key=lambda x: x["page"])
        return final_results