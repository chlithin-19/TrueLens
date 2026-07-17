import logging
import uuid
from sentence_transformers import SentenceTransformer
from app.db.chroma import chroma_manager
from app.core.config import settings

logger = logging.getLogger("truelens.embedding")

class EmbeddingService:
    def __init__(self):
        self.model = None
        self.collection = None

    def _ensure_initialized(self):
        if not self.model:
            logger.info(f"Loading SentenceTransformer model: {settings.EMBEDDING_MODEL}")
            self.model = SentenceTransformer(settings.EMBEDDING_MODEL)
            
        if not self.collection:
            client = chroma_manager.get_client()
            self.collection = client.get_or_create_collection(name=settings.CHROMA_COLLECTION)

    def generate_embedding(self, text: str) -> list:
        self._ensure_initialized()
        if not text:
            return []
        # SentenceTransformer returns a numpy array, convert to list of floats
        embedding = self.model.encode(text)
        return embedding.tolist()

    def store_article(self, article_id: str, text: str, metadata: dict) -> str:
        self._ensure_initialized()
        
        # We can chunk the text to store it
        # For simplicity, we just store the full text as one document or first 2000 chars if too long
        chunk_text = text[:5000] if len(text) > 5000 else text
        embedding = self.generate_embedding(chunk_text)
        
        # Create a unique ID for this embedding entry
        embedding_id = str(uuid.uuid4())
        
        # Add metadata
        full_metadata = metadata.copy()
        full_metadata["article_id"] = article_id
        
        self.collection.add(
            ids=[embedding_id],
            embeddings=[embedding],
            metadatas=[full_metadata],
            documents=[chunk_text]
        )
        
        return embedding_id

    def search_similar(self, text: str, top_k: int = 5) -> list:
        self._ensure_initialized()
        
        embedding = self.generate_embedding(text)
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k
        )
        
        similar_items = []
        if results and "documents" in results and results["documents"]:
            for i in range(len(results["ids"][0])):
                similar_items.append({
                    "id": results["ids"][0][i],
                    "document": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i] if "distances" in results else None
                })
                
        return similar_items
