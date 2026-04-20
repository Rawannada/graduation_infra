import re
import requests
from vector_store import VectorStore

class RAGPipeline:
    def __init__(self, vector_store: VectorStore, llm_model: str = "llama3"):
        self.vector_store = vector_store
        self.llm_model = llm_model
        self.url = "http://localhost:11434/api/generate"

    ACRONYM_EXPANSIONS = {
        "LAN":   "Local Area Network",
        "WAN":   "Wide Area Network",
        "MAN":   "Metropolitan Area Network",
        "PAN":   "Personal Area Network",
        "TCP":   "Transmission Control Protocol",
        "UDP":   "User Datagram Protocol",
        "IP":    "Internet Protocol",
        "HTTP":  "Hypertext Transfer Protocol",
        "HTTPS": "Hypertext Transfer Protocol Secure",
        "DNS":   "Domain Name System",
        "DHCP":  "Dynamic Host Configuration Protocol",
        "MAC":   "Media Access Control",
        "OSI":   "Open Systems Interconnection",
        "NAT":   "Network Address Translation",
        "VPN":   "Virtual Private Network",
        "FTP":   "File Transfer Protocol",
        "SMTP":  "Simple Mail Transfer Protocol",
        "NIC":   "Network Interface Card",
        "STP":   "Spanning Tree Protocol",
        "VLAN":  "Virtual Local Area Network",
    }

    STOP_WORDS = {
        "what", "is", "are", "how", "does", "do", "explain", "define",
        "describe", "tell", "me", "about", "the", "a", "an", "and",
        "or", "in", "of", "for", "to", "from", "it", "its", "this",
        "that", "which", "where", "when", "why", "can", "could",
        "would", "should", "please", "give", "show", "list", "wan",
    }

    def _extract_keywords(self, question: str) -> list:
        tokens   = re.findall(r'[A-Za-z0-9/\-]+', question)
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
        q     = question.strip()
        parts = re.split(r'\band\b|&|\balso\b', q, flags=re.IGNORECASE)
        parts = [p.strip().rstrip('?').strip(',').strip() for p in parts]
        parts = [p for p in parts if len(p) > 3]

        if len(parts) <= 1:
            return [question]

        first_part  = parts[0]
        verb_match  = re.match(
            r'^(what\s+is|what\s+are|explain|define|describe|'
            r'how\s+does|how\s+do|tell\s+me\s+about|compare)\s+',
            first_part, flags=re.IGNORECASE,
        )
        prefix  = verb_match.group(0) if verb_match else ""
        queries = [first_part + "?"]

        for part in parts[1:]:
            already_has_verb = re.match(
                r'^(what|explain|define|describe|how|tell|is|are|compare)\b',
                part, flags=re.IGNORECASE,
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
            "sources": [],
        }

    def _check_not_found(self, answer: str) -> bool:
        not_found_phrases = [
            "not found", "not covered", "no information", "not mentioned",
            "not discussed", "cannot find", "not present", "not in document",
            "could not find", "no mention of", "does not appear",
            "i cannot find", "i can't find",
            "error communicating", "500 server error", "error generating",
            "i don't have", "i do not have", "not available",
        ]
        answer_lower = answer.lower()
        return any(phrase in answer_lower for phrase in not_found_phrases)

    def query(self, question: str,
              use_mmr: bool = True,
              use_query_expansion: bool = False) -> dict:
        """Full RAG pipeline: split → retrieve → deduplicate → generate."""

        queries = self._split_compound_question(question)

        seen_keys     = set()
        relevant_docs = []

        for q in queries:
            keywords = self._extract_keywords(q)
            if keywords:
                docs = self.vector_store.search_with_keyword_boost(
                    q, keywords=keywords, k=4, keyword_bonus=0.4,
                )
            elif use_mmr:
                docs = self.vector_store.search_mmr(
                    q, k=4, fetch_k=12, lambda_mult=0.75,
                )
            else:
                # [FIX] Simplified extraction from tuple
                search_results = self.vector_store.search(q, k=4)
                docs = [doc for _, doc in search_results]

            for doc in docs:
                key = f"{doc['source']}::{doc['page']}"
                if key not in seen_keys:
                    seen_keys.add(key)
                    relevant_docs.append(doc)

        relevant_docs = relevant_docs[:6]

        if not relevant_docs:
            return self._not_found_response()

        # [MODIFICATION] Enhanced context string to include Section Titles
        # This helps the LLM understand the structure of the document
        context_parts = []
        for d in relevant_docs:
            header = f"[Source: {d['source']}, Page: {d['page']}"
            if d.get("section_title"):
                header += f", Section: {d['section_title']}"
            header += "]"
            context_parts.append(f"{header}\n{d['text']}")
        
        context = "\n\n".join(context_parts)

        keywords_all  = self._extract_keywords(question)
        acronym_hints = [
            f'"{kw.upper()}" also appears as "{self.ACRONYM_EXPANSIONS[kw.upper()]}"'
            for kw in keywords_all
            if kw.upper() in self.ACRONYM_EXPANSIONS
        ]

        hint_line = ""
        if acronym_hints:
            hint_line = (
                f"\nNOTE: {'; '.join(acronym_hints)}. "
                "Search for BOTH forms in the context.\n"
            )

        # [MODIFICATION] Updated prompt to instruct the LLM to use section titles for better context
        prompt = f"""You are a helpful document assistant. Use the context below to answer the question.
{hint_line}
Rules:
- Use ONLY the provided context. Do not use outside knowledge.
- The context includes Section Titles; use them to understand the topic better.
- You do NOT need a formal definition sentence. If the document discusses or describes the concept anywhere, summarise what it says.
- Always cite the page number(s), e.g. "(Page 5)".
- If the question is about multiple topics, address each in its own paragraph.
- Answer in the same language as the question.

Context:
{context}

Question: {question}
Answer:"""

        try:
            response = requests.post(
                self.url,
                json={"model": self.llm_model, "prompt": prompt, "stream": False},
                timeout=120,
            )
            response.raise_for_status()
            answer = response.json().get("response", "Error generating answer.")
        except Exception as e:
            answer = f"Error communicating with Ollama: {str(e)}"

        if self._check_not_found(answer):
            return {"answer": answer, "sources": []}

        return {
            "answer":  answer,
            "sources": [
                {"source": d["source"], "page": d["page"]}
                for d in relevant_docs
            ],
        }