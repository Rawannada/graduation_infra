import requests

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

    @property
    def embeddings(self):
        return self