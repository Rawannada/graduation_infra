import requests
import numpy as np
import faiss

# --- الجزء الأول: مولد المتجهات (Embedding Generator) ---
class EmbeddingGenerator:
    def __init__(self, model_name: str = "nomic-embed-text"):
        self.model_name = model_name
        self.url = "http://localhost:11434/api/embeddings"

    def embed_documents(self, texts):
        embeddings = []
        for text in texts:
            response = requests.post(self.url, json={"model": self.model_name, "prompt": text})
            if response.status_code == 200:
                embeddings.append(response.json()["embedding"])
            else:
                raise Exception(f"Ollama Error: {response.text}")
        return embeddings

    def embed_query(self, text):
        response = requests.post(self.url, json={"model": self.model_name, "prompt": text})
        return response.json()["embedding"]

# --- الجزء الثاني: مخزن المتجهات (Vector Store) ---
class VectorStore:
    def __init__(self):
        self.embedding_generator = EmbeddingGenerator()
        self.index = None
        self.documents = []

    def create_vector_store(self, pages_data):
        # تصفية النصوص الفارغة
        texts = [p["text"] for p in pages_data if p.get("text") and p["text"].strip()]
        self.documents = [{"text": p["text"], "source": p["filename"], "page": p["page_num"]} 
                          for p in pages_data if p.get("text") and p["text"].strip()]
        
        if not texts:
            print("⚠️ No text found to index.")
            return

        # تحويل النصوص لمتجهات
        embeddings = self.embedding_generator.embed_documents(texts)
        embeddings_np = np.array(embeddings).astype('float32')
        
        # بناء فهرس FAISS للبحث السريع
        dimension = embeddings_np.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings_np)
        print(f"✅ FAISS Index created with {len(texts)} chunks.")

    def search(self, query, k=4):
        if self.index is None:
            return []
        query_vector = np.array([self.embedding_generator.embed_query(query)]).astype('float32')
        distances, indices = self.index.search(query_vector, k)
        
        results = []
        for i in indices[0]:
            if i != -1 and i < len(self.documents):
                results.append(self.documents[i])
        return results

# --- الجزء الثالث: خط الـ RAG (The Pipeline) ---
class RAGPipeline:
    def __init__(self, vector_store, llm_model: str = "llama3"):
        self.vector_store = vector_store
        self.llm_model = llm_model
        self.url = "http://localhost:11434/api/generate"

    def query(self, question: str):
        # 1. استرجاع المعلومات المتعلقة بالسؤال
        relevant_docs = self.vector_store.search(question)
        
        if not relevant_docs:
            return {"answer": "I couldn't find relevant information in the documents.", "sources": []}

        # 2. تحضير السياق (Context)
        context = "\n\n".join([f"[Source: {d['source']}, Page: {d['page']}]\n{d['text']}" for d in relevant_docs])
        
        # 3. بناء البرومبت النهائي للموديل
        prompt = f"""You are a helpful assistant. Use the following pieces of retrieved context to answer the question. 
        If you don't know the answer, just say that you don't know. 

        Context:
        {context}

        Question: {question}
        Answer:"""

        # 4. إرسال الطلب لـ Ollama (Direct API Call)
        payload = {
            "model": self.llm_model,
            "prompt": prompt,
            "stream": False
        }
        
        try:
            response = requests.post(self.url, json=payload)
            response.raise_for_status()
            answer = response.json().get("response", "Error generating answer.")
        except Exception as e:
            answer = f"Error communicating with Ollama: {str(e)}"
        
        return {
            "answer": answer,
            "sources": [{"source": d["source"], "page": d["page"]} for d in relevant_docs]
        }