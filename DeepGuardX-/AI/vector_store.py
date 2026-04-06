import numpy as np
import faiss
from embeddings import EmbeddingGenerator

class VectorStore:
    def __init__(self):
        self.embedding_generator = EmbeddingGenerator()
        self.index = None
        self.documents = []

    def create_vector_store(self, pages_data):
        texts = [p["text"] for p in pages_data if p["text"].strip()]
        self.documents = [{"text": p["text"], "source": p["filename"], "page": p["page_num"]} for p in pages_data if p["text"].strip()]
        
        embeddings = self.embedding_generator.embed_documents(texts)
        embeddings_np = np.array(embeddings).astype('float32')
        
        dimension = embeddings_np.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings_np)
        print(f"✅ FAISS Index created with {len(texts)} chunks.")

    def search(self, query, k=4):
        query_vector = np.array([self.embedding_generator.embed_query(query)]).astype('float32')
        distances, indices = self.index.search(query_vector, k)
        results = []
        for i in indices[0]:
            if i != -1 and i < len(self.documents):
                results.append(self.documents[i])
        return results