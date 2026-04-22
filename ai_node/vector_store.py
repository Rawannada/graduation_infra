import hashlib
import pickle
import logging
from pathlib import Path
import numpy as np
import faiss
from embeddings import EmbeddingGenerator

logger = logging.getLogger("VECTOR_STORE")

# ─────────────────────────────────────────────────────────────────────────────
# CACHE DIRECTORY
# All FAISS indexes and metadata files are stored here on disk
# ─────────────────────────────────────────────────────────────────────────────
CACHE_DIR = Path(__file__).parent / "vs_cache"
CACHE_DIR.mkdir(exist_ok=True)


def _cache_key(source: str) -> str:
    # If source is a MongoDB ObjectId (24 hex chars) use it directly
    # Otherwise generate an MD5 hash from the source string
    if len(source) == 24 and all(c in "0123456789abcdefABCDEF" for c in source):
        return source
    return hashlib.md5(str(source).encode()).hexdigest()


class VectorStore:
    def __init__(self, max_workers: int = 4):
        self.embedding_generator = EmbeddingGenerator(max_workers=max_workers)
        self.index     = None   # FAISS index — used for fast similarity search
        self.documents = []     # List of dicts: text + source + page + section_title
        self.vectors   = None   # Normalized vectors — used for MMR and keyword boost

    # ─────────────────────────────────────────
    # PERSISTENCE
    # ─────────────────────────────────────────

    def save(self, cache_source: str) -> None:
        if self.index is None:
            logger.warning("[SAVE] Nothing to save — index is empty.")
            return

        key        = _cache_key(cache_source)
        index_path = CACHE_DIR / f"{key}.index"
        meta_path  = CACHE_DIR / f"{key}.meta"

        logger.info(f"[SAVE] Saving FAISS index to {index_path.name}...")
        faiss.write_index(self.index, str(index_path))

        logger.info(f"[SAVE] Saving metadata (documents + vectors) to {meta_path.name}...")
        with open(meta_path, "wb") as f:
            pickle.dump(
                {
                    "documents":     self.documents,
                    "vectors":       self.vectors,   # normalized — needed for MMR on reload
                    "original_path": cache_source,
                },
                f,
                protocol=pickle.HIGHEST_PROTOCOL,
            )
        logger.info(f"[SAVE] Done. {len(self.documents)} chunks saved to disk.")

    def load(self, cache_source: str) -> bool:
        key        = _cache_key(cache_source)
        index_path = CACHE_DIR / f"{key}.index"
        meta_path  = CACHE_DIR / f"{key}.meta"

        if not index_path.exists() or not meta_path.exists():
            logger.info(f"[LOAD] No cache found for key: {key}")
            return False

        try:
            logger.info(f"[LOAD] Loading FAISS index from {index_path.name}...")
            self.index = faiss.read_index(str(index_path))

            logger.info(f"[LOAD] Loading metadata from {meta_path.name}...")
            with open(meta_path, "rb") as f:
                meta = pickle.load(f)

            self.documents = meta.get("documents", [])
            self.vectors   = meta.get("vectors")

            logger.info(f"[LOAD] Load complete. {len(self.documents)} chunks | vectors shape: {self.vectors.shape if self.vectors is not None else 'None'}")
            return True

        except Exception as e:
            logger.error(f"[LOAD] ERROR: Failed to load cache — {str(e)}")
            return False

    # ─────────────────────────────────────────
    # BUILD — Standard (no distribution)
    # Used when no remote workers are available
    # Embeds locally, normalizes, and builds the index in one shot
    # ─────────────────────────────────────────

    def create_vector_store(self, pages_data: list, cache_source: str = None) -> None:
        valid_pages = [p for p in pages_data if p.get("text") and p["text"].strip()]
        if not valid_pages:
            logger.warning("[BUILD] No text found to index.")
            return

        logger.info(f"[BUILD] Generating embeddings for {len(valid_pages)} chunks...")
        texts      = [p["text"] for p in valid_pages]
        embeddings = self.embedding_generator.embed_documents(texts)
        emb_np     = np.array(embeddings).astype("float32")
        logger.info(f"[BUILD] Embeddings shape: {emb_np.shape}")

        norms             = np.linalg.norm(emb_np, axis=1, keepdims=True)
        norms[norms == 0] = 1
        normalized        = emb_np / norms

        self._finalize_index(normalized, emb_np, valid_pages)
        logger.info(f"[BUILD] Index built with {len(valid_pages)} chunks.")

        if cache_source:
            self.save(cache_source)

    # ─────────────────────────────────────────
    # BUILD — Distributed (called by manager after collecting all worker packages)
    # Steps:
    #   1. Stack all normalized vectors into one matrix (single vstack)
    #   2. Unify metadata keys to: source + page
    #   3. Build FAISS index once from the full matrix
    #   4. Save to disk
    # ─────────────────────────────────────────

    def build_from_distributed(
        self,
        all_vectors:  list,   # list of np.ndarray — one per node (already normalized)
        all_chunks:   list,   # flat list of dicts: {text, filename, page_num, section_title}
        cache_source: str = None
    ) -> None:
        if not all_vectors:
            logger.warning("[DISTRIBUTED] No vectors received. Build aborted.")
            return

        logger.info(f"[DISTRIBUTED] Stacking {len(all_vectors)} vector batches into one matrix...")
        final_vectors = np.vstack(all_vectors).astype("float32")
        logger.info(f"[DISTRIBUTED] Final matrix shape: {final_vectors.shape} | dtype: {final_vectors.dtype}")

        # Unify metadata — all docs must have: source, page, text, section_title
        logger.info(f"[DISTRIBUTED] Unifying metadata keys (filename->source, page_num->page)...")
        unified_docs = [
            {
                "text":          c.get("text", ""),
                "source":        c.get("filename", c.get("source", "unknown")),
                "page":          c.get("page_num",  c.get("page", 0)),
                "section_title": c.get("section_title", ""),
            }
            for c in all_chunks
        ]
        logger.info(f"[DISTRIBUTED] Unified {len(unified_docs)} documents.")

        # Build FAISS index once from the full stacked matrix
        logger.info(f"[DISTRIBUTED] Building FAISS IndexFlatL2 with dim={final_vectors.shape[1]}...")
        dimension  = final_vectors.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(final_vectors)

        self.vectors   = final_vectors
        self.documents = unified_docs

        logger.info(f"[DISTRIBUTED] FAISS index built. Total vectors: {self.index.ntotal}")

        if cache_source:
            self.save(cache_source)

    # ─────────────────────────────────────────
    # INTERNAL HELPER
    # Adds embeddings and metadata to the index incrementally
    # Used by create_vector_store (standard mode)
    # ─────────────────────────────────────────

    def _finalize_index(
        self,
        normalized_emb: np.ndarray,
        raw_emb:        np.ndarray,
        pages_metadata: list
    ) -> None:
        dimension = raw_emb.shape[1]

        if self.index is None:
            self.index = faiss.IndexFlatL2(dimension)
        self.index.add(raw_emb)

        if self.vectors is None:
            self.vectors = normalized_emb
        else:
            self.vectors = np.vstack([self.vectors, normalized_emb])

        new_docs = [
            {
                "text":          p["text"],
                "source":        p.get("filename", p.get("source", "unknown")),
                "page":          p.get("page_num",  p.get("page", 0)),
                "section_title": p.get("section_title", ""),
            }
            for p in pages_metadata
        ]
        self.documents.extend(new_docs)

    # ─────────────────────────────────────────
    # SEARCH — Basic L2 similarity search
    # ─────────────────────────────────────────

    def search(self, query: str, k: int = 4) -> list:
        if self.index is None:
            return []
        query_vec = np.array(
            [self.embedding_generator.embed_query(query)]
        ).astype("float32")
        _, indices = self.index.search(query_vec, k)
        results = [
            self.documents[i]
            for i in indices[0]
            if i != -1 and i < len(self.documents)
        ]
        results.sort(key=lambda x: x["page"])
        return results

    # ─────────────────────────────────────────
    # SEARCH — Keyword boost (cosine + keyword bonus)
    # Boosts chunks that contain the query keywords
    # ─────────────────────────────────────────

    def search_with_keyword_boost(
        self,
        query:         str,
        keywords:      list,
        k:             int   = 4,
        keyword_bonus: float = 0.4
    ) -> list:
        if self.index is None or self.vectors is None:
            return []

        query_vec = np.array(
            [self.embedding_generator.embed_query(query)]
        ).astype("float32")
        q_norm         = np.linalg.norm(query_vec)
        query_vec_norm = query_vec / q_norm if q_norm > 0 else query_vec

        all_sims = (self.vectors @ query_vec_norm.T).flatten()

        scored = []
        for idx, doc in enumerate(self.documents):
            text_lower = doc["text"].lower()
            boost = sum(
                keyword_bonus
                for kw in keywords
                if kw.lower() in text_lower
            )
            scored.append((idx, float(all_sims[idx]) + boost))

        scored.sort(key=lambda x: x[1], reverse=True)
        top = [self.documents[idx] for idx, _ in scored[:k]]
        top.sort(key=lambda x: x["page"])
        return top

    # ─────────────────────────────────────────
    # SEARCH — MMR (Maximal Marginal Relevance)
    # Balances relevance and diversity in results
    # lambda_mult: 1.0 = pure relevance, 0.0 = pure diversity
    # ─────────────────────────────────────────

    def search_mmr(
        self,
        query:       str,
        k:           int   = 4,
        fetch_k:     int   = 12,
        lambda_mult: float = 0.75
    ) -> list:
        if self.index is None or self.vectors is None:
            return []

        query_vec = np.array(
            [self.embedding_generator.embed_query(query)]
        ).astype("float32")
        q_norm         = np.linalg.norm(query_vec)
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
                    sel_vecs            = self.vectors[selected_doc_indices]
                    max_sim_to_selected = float(
                        np.max(sel_vecs @ self.vectors[doc_idx])
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

        final = [self.documents[i] for i in selected_doc_indices]
        final.sort(key=lambda x: x["page"])
        return final
