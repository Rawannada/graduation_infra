import numpy as np
import faiss
from embeddings import EmbeddingGenerator


class VectorStore:
    def __init__(self, max_workers: int = 4):
        self.embedding_generator = EmbeddingGenerator(max_workers=max_workers)
        self.index = None
        self.documents = []
        # Normalised vectors stored for cosine similarity inside MMR search
        self.vectors = None

    def create_vector_store(self, pages_data: list):
        """
        Build FAISS index from PDF pages.
        Embeddings are generated in parallel (handled inside EmbeddingGenerator).
        Also stores normalised vectors needed for MMR diversity scoring.
        """
        valid_pages = [p for p in pages_data if p.get("text") and p["text"].strip()]

        if not valid_pages:
            print("⚠️  No text found to index.")
            return

        texts = [p["text"] for p in valid_pages]
        self.documents = [
            {
                "text": p["text"],
                "source": p["filename"],
                "page": p["page_num"]
            }
            for p in valid_pages
        ]

        print(f"[INFO] Generating embeddings for {len(texts)} chunks (parallel)...")
        embeddings = self.embedding_generator.embed_documents(texts)
        embeddings_np = np.array(embeddings).astype("float32")

        # Normalise and store for cosine similarity in MMR
        norms = np.linalg.norm(embeddings_np, axis=1, keepdims=True)
        norms[norms == 0] = 1
        self.vectors = embeddings_np / norms

        dimension = embeddings_np.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings_np)
        print(f"✅ FAISS Index created with {len(texts)} chunks.")

    def search(self, query: str, k: int = 4) -> list:
        """Basic L2 similarity search. Returns list of (doc_index, doc) tuples."""
        if self.index is None:
            return []
        query_vector = np.array(
            [self.embedding_generator.embed_query(query)]
        ).astype("float32")
        _, indices = self.index.search(query_vector, k)
        return [
            (i, self.documents[i])
            for i in indices[0]
            if i != -1 and i < len(self.documents)
        ]

    def search_mmr(self, query: str, k: int = 4, fetch_k: int = 20,
                   lambda_mult: float = 0.6) -> list:
        """
        Maximal Marginal Relevance search.

        Old search returned the k most similar chunks — they often came from
        the same page and repeated the same information.

        MMR instead balances two goals:
          - Relevance:  how similar is this chunk to the question?
          - Diversity:  how different is this chunk from already-selected ones?

        lambda_mult controls the balance:
          1.0 = pure similarity (same as basic search)
          0.0 = pure diversity
          0.6 = good balance for Q&A (default)

        This gives the LLM richer context covering more of the document,
        leading to more complete and accurate answers.
        """
        if self.index is None or self.vectors is None:
            return []

        # Embed and normalise query vector for cosine similarity
        query_vec = np.array(
            [self.embedding_generator.embed_query(query)]
        ).astype("float32")
        q_norm = np.linalg.norm(query_vec)
        query_vec_norm = query_vec / q_norm if q_norm > 0 else query_vec

        # Step 1: fetch a large candidate pool
        fetch_k = min(fetch_k, len(self.documents))
        _, raw_indices = self.index.search(query_vec, fetch_k)
        candidate_indices = [
            i for i in raw_indices[0]
            if i != -1 and i < len(self.documents)
        ]
        if not candidate_indices:
            return []

        # Cosine similarity: query vs each candidate
        candidate_vecs = self.vectors[candidate_indices]
        query_sims = (candidate_vecs @ query_vec_norm.T).flatten()

        # Step 2: iteratively pick the best MMR chunk
        selected_positions = []
        selected_doc_indices = []

        for _ in range(min(k, len(candidate_indices))):
            best_pos, best_score = None, -999.0

            for pos, doc_idx in enumerate(candidate_indices):
                if pos in selected_positions:
                    continue

                relevance = float(query_sims[pos])

                if selected_doc_indices:
                    selected_vecs = self.vectors[selected_doc_indices]
                    max_sim_to_selected = float(
                        np.max(selected_vecs @ self.vectors[doc_idx])
                    )
                    diversity = 1.0 - max_sim_to_selected
                else:
                    diversity = 1.0

                score = lambda_mult * relevance + (1.0 - lambda_mult) * diversity

                if score > best_score:
                    best_score = score
                    best_pos = pos

            if best_pos is not None:
                selected_positions.append(best_pos)
                selected_doc_indices.append(candidate_indices[best_pos])

        return [self.documents[i] for i in selected_doc_indices]
