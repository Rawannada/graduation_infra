import re
import requests
import numpy as np
import faiss
from concurrent.futures import ThreadPoolExecutor, as_completed


# ---------------------------------------------------------------------------
# Part 1: Embedding Generator
# ---------------------------------------------------------------------------
class EmbeddingGenerator:
    def __init__(self, model_name: str = "nomic-embed-text", max_workers: int = 4):
        self.model_name = model_name
        self.url = "http://localhost:11434/api/embeddings"
        self.max_workers = max_workers

    def _embed_single(self, text: str) -> list:
        response = requests.post(
            self.url,
            json={"model": self.model_name, "prompt": text},
            timeout=300
        )
        if response.status_code == 200:
            return response.json()["embedding"]
        raise Exception(f"Ollama Error: {response.text}")

    def embed_documents(self, texts: list) -> list:
        """Embed all chunks IN PARALLEL — 3-4x faster than sequential loop."""
        embeddings = [None] * len(texts)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_index = {
                executor.submit(self._embed_single, text): i
                for i, text in enumerate(texts)
            }
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    embeddings[index] = future.result()
                except Exception as e:
                    raise Exception(f"Failed to embed chunk {index}: {e}")
        return embeddings

    def embed_query(self, text: str) -> list:
        response = requests.post(
            self.url,
            json={"model": self.model_name, "prompt": text},
            timeout=60
        )
        if response.status_code == 200:
            return response.json()["embedding"]
        raise Exception(f"Ollama Error: {response.text}")


# ---------------------------------------------------------------------------
# Part 2: Vector Store
# ---------------------------------------------------------------------------
class VectorStore:
    def __init__(self, max_workers: int = 4):
        self.embedding_generator = EmbeddingGenerator(max_workers=max_workers)
        self.index = None
        self.documents = []
        self.vectors = None

    def create_vector_store(self, pages_data: list):
        """Build FAISS index. Embeddings generated in parallel."""
        valid_pages = [p for p in pages_data if p.get("text") and p["text"].strip()]
        if not valid_pages:
            print("⚠️ No text found to index.")
            return

        texts = [p["text"] for p in valid_pages]
        self.documents = [
            {"text": p["text"], "source": p["filename"], "page": p["page_num"]}
            for p in valid_pages
        ]

        print(f"[INFO] Embedding {len(texts)} chunks in parallel...")
        embeddings = self.embedding_generator.embed_documents(texts)
        embeddings_np = np.array(embeddings).astype("float32")

        norms = np.linalg.norm(embeddings_np, axis=1, keepdims=True)
        norms[norms == 0] = 1
        self.vectors = embeddings_np / norms

        dimension = embeddings_np.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings_np)
        print(f"✅ FAISS Index created with {len(texts)} chunks.")

    def search(self, query: str, k: int = 4) -> list:
        """Basic L2 similarity search sorted by page number."""
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
        # ✅ FIX: ترتيب حسب رقم الصفحة
        results.sort(key=lambda x: x[1]['page'])
        return results

    def search_with_keyword_boost(self, query: str, keywords: list,
                                   k: int = 4, keyword_bonus: float = 0.4) -> list:
        """Keyword-boosted hybrid search — searches ALL documents."""
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
            boost = 0.0
            for kw in keywords:
                kw_lower = kw.lower()
                if kw_lower in text_lower:
                    boost += keyword_bonus
            scored.append((doc_idx, float(all_sims[doc_idx]) + boost))

        scored.sort(key=lambda x: x[1], reverse=True)
        top_results = [self.documents[doc_idx] for doc_idx, _ in scored[:k]]
        # ✅ FIX: ترتيب حسب رقم الصفحة
        top_results.sort(key=lambda x: x['page'])
        return top_results

    def search_mmr(self, query: str, k: int = 4, fetch_k: int = 12,
                   lambda_mult: float = 0.75) -> list:
        """MMR search — used as fallback when no keywords are extracted."""
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
        query_sims = (candidate_vecs @ query_vec_norm.T).flatten()

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
                    max_sim = float(np.max(selected_vecs @ self.vectors[doc_idx]))
                    diversity = 1.0 - max_sim
                else:
                    diversity = 1.0
                score = lambda_mult * relevance + (1.0 - lambda_mult) * diversity
                if score > best_score:
                    best_score = score
                    best_pos = pos
            if best_pos is not None:
                selected_positions.append(best_pos)
                selected_doc_indices.append(candidate_indices[best_pos])

        final_results = [self.documents[i] for i in selected_doc_indices]
        # ✅ FIX: ترتيب حسب رقم الصفحة
        final_results.sort(key=lambda x: x['page'])
        return final_results


# ---------------------------------------------------------------------------
# Part 3: RAG Pipeline
# ---------------------------------------------------------------------------
class RAGPipeline:
    def __init__(self, vector_store: VectorStore, llm_model: str = "llama3"):
        self.vector_store = vector_store
        self.llm_model = llm_model
        self.url = "http://localhost:11434/api/generate"

    ACRONYM_EXPANSIONS = {
        "LAN": "Local Area Network",
        "WAN": "Wide Area Network",
        "MAN": "Metropolitan Area Network",
        "PAN": "Personal Area Network",
        "TCP": "Transmission Control Protocol",
        "UDP": "User Datagram Protocol",
        "IP": "Internet Protocol",
        "HTTP": "Hypertext Transfer Protocol",
        "HTTPS": "Hypertext Transfer Protocol Secure",
        "DNS": "Domain Name System",
        "DHCP": "Dynamic Host Configuration Protocol",
        "MAC": "Media Access Control",
        "OSI": "Open Systems Interconnection",
        "NAT": "Network Address Translation",
        "VPN": "Virtual Private Network",
        "FTP": "File Transfer Protocol",
        "SMTP": "Simple Mail Transfer Protocol",
        "NIC": "Network Interface Card",
        "STP": "Spanning Tree Protocol",
        "VLAN": "Virtual Local Area Network",
    }

    STOP_WORDS = {
        "what", "is", "are", "how", "does", "do", "explain", "define",
        "describe", "tell", "me", "about", "the", "a", "an", "and",
        "or", "in", "of", "for", "to", "from", "it", "its", "this",
        "that", "which", "where", "when", "why", "can", "could",
        "would", "should", "please", "give", "show", "list", "wan",
    }

    def _extract_keywords(self, question: str) -> list:
        tokens = re.findall(r'[A-Za-z0-9/\-]+', question)
        keywords = []
        for token in tokens:
            upper = token.upper()
            if token.lower() in self.STOP_WORDS:
                continue
            if len(token) < 2:
                continue
            keywords.append(token)
            if upper in self.ACRONYM_EXPANSIONS:
                keywords.append(self.ACRONYM_EXPANSIONS[upper])
        return list(dict.fromkeys(keywords))

    def _split_compound_question(self, question: str) -> list:
        q = question.strip()
        parts = re.split(r'\band\b|&|\balso\b', q, flags=re.IGNORECASE)
        parts = [p.strip().rstrip('?').strip(',').strip() for p in parts]
        parts = [p for p in parts if len(p) > 3]
        if len(parts) <= 1:
            return [question]
        first_part = parts[0]
        verb_match = re.match(
            r'^(what\s+is|what\s+are|explain|define|describe|'
            r'how\s+does|how\s+do|tell\s+me\s+about|compare)\s+',
            first_part, flags=re.IGNORECASE
        )
        prefix = verb_match.group(0) if verb_match else ""
        queries = [first_part + "?"]
        for part in parts[1:]:
            already_has_verb = re.match(
                r'^(what|explain|define|describe|how|tell|is|are|compare)\b',
                part, flags=re.IGNORECASE
            )
            if already_has_verb or not prefix:
                queries.append(part + "?")
            else:
                queries.append(prefix + part + "?")
        return queries

    def _not_found_response(self) -> dict:
        return {
            "answer": (
                "I could not find information about this topic in the document. "
                "Please try rephrasing your question or check if this topic "
                "is covered in the document."
            ),
            "sources": []
        }

    def _check_not_found(self, answer: str) -> bool:
        # ✅ FIX: أضفنا Ollama errors + more phrases
        not_found_phrases = [
            "not found", "not covered", "no information", "not mentioned",
            "not discussed", "cannot find", "not present", "not in document",
            "could not find", "no mention of", "does not appear",
            "i cannot find", "i can't find",
            "Error communicating", "500 Server Error", "Error generating",
            "i don't have", "i do not have", "not available"
        ]
        answer_lower = answer.lower()
        return any(phrase in answer_lower for phrase in not_found_phrases)

    def query(self, question: str,
              use_mmr: bool = True,
              use_query_expansion: bool = False) -> dict:
        """Full RAG pipeline with all fixes applied."""

        queries = self._split_compound_question(question)

        seen_keys = set()
        relevant_docs = []

        for q in queries:
            keywords = self._extract_keywords(q)
            if keywords:
                docs = self.vector_store.search_with_keyword_boost(
                    q, keywords=keywords, k=4, keyword_bonus=0.4
                )
            elif use_mmr:
                docs = self.vector_store.search_mmr(
                    q, k=4, fetch_k=12, lambda_mult=0.75
                )
            else:
                docs = [doc for _, doc in self.vector_store.search(q, k=4)]

            for doc in docs:
                key = f"{doc['source']}::{doc['page']}"
                if key not in seen_keys:
                    seen_keys.add(key)
                    relevant_docs.append(doc)

        relevant_docs = relevant_docs[:6]

        if not relevant_docs:
            return self._not_found_response()

        context = "\n\n".join([
            f"[Source: {d['source']}, Page: {d['page']}]\n{d['text']}"
            for d in relevant_docs
        ])

        keywords_all = self._extract_keywords(question)
        acronym_hints = []
        for kw in keywords_all:
            upper = kw.upper()
            if upper in self.ACRONYM_EXPANSIONS:
                acronym_hints.append(
                    f'"{upper}" also appears as "{self.ACRONYM_EXPANSIONS[upper]}"'
                )

        hint_line = ""
        if acronym_hints:
            hint_line = (
                f"\nNOTE: {'; '.join(acronym_hints)}. "
                "Search for BOTH forms in the context.\n"
            )

        prompt = f"""You are a helpful document assistant. Use the context below to answer the question.
{hint_line}
Rules:
- Use ONLY the provided context. Do not use outside knowledge.
- You do NOT need a formal definition sentence. If the document discusses or describes the concept anywhere, summarise what it says.
- Search for both the abbreviation AND the full name (e.g. both "WAN" and "Wide Area Network") — the document may use either form.
- Always cite the page number(s), e.g. "(Page 5)".
- If the question is about multiple topics, address each in its own paragraph.
- Only say the topic is not covered if it is genuinely absent from every single context page provided.
- Answer in the same language as the question.

Context:
{context}

Question: {question}
Answer:"""

        try:
            response = requests.post(
                self.url,
                json={"model": self.llm_model, "prompt": prompt, "stream": False},
                timeout=120
            )
            response.raise_for_status()
            answer = response.json().get("response", "Error generating answer.")
        except Exception as e:
            answer = f"Error communicating with Ollama: {str(e)}"

        if self._check_not_found(answer):
            return {"answer": answer, "sources": []}

        return {
            "answer": answer,
            "sources": [
                {"source": d["source"], "page": d["page"]}
                for d in relevant_docs
            ]
        }
