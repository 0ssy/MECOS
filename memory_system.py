import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer
from loguru import logger
from config import settings
import time
import json

class VectorMemory:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=settings.VECTOR_DB_PATH)
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.collection = self.client.get_or_create_collection(name="mecos_long_term")
        logger.info("Vector Memory System Initialized.")

    async def store(self, content: str, metadata: dict = None):
        """Store content with its embedding."""
        timestamp = str(time.time())
        metadata = metadata or {}
        metadata["timestamp"] = timestamp
        sanitized_metadata = {}
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool, type(None), list)):
                sanitized_metadata[key] = value
            else:
                sanitized_metadata[key] = json.dumps(value, default=str)
        
        self.collection.add(
            documents=[content],
            metadatas=[sanitized_metadata],
            ids=[f"mem_{int(time.time() * 1000)}"]
        )
        logger.debug(f"Stored memory: {content[:50]}...")

    async def query(self, text: str, n_results: int = 5):
        """Query the vector database for similar content."""
        results = self.collection.query(
            query_texts=[text],
            n_results=n_results
        )
        return results

    def count(self):
        """Return the total number of items in the collection."""
        return self.collection.count()


class MemorySystem:
    def __init__(self):
        self.vector_memory = VectorMemory()
        self.short_term_buffer = []

    async def add_experience(self, content: str, source: str = "general", metadata: dict = None):
        """Add a new experience to both short-term and long-term memory."""
        metadata = metadata or {}
        # 1. Add to short-term buffer
        self.short_term_buffer.append({
            "content": content,
            "source": source,
            "metadata": metadata,
            "timestamp": time.time()
        })
        
        # 2. Persist to long-term vector memory
        store_metadata = {"source": source}
        store_metadata.update(metadata)
        await self.vector_memory.store(content, store_metadata)
        
        # Keep buffer manageable
        if len(self.short_term_buffer) > 100:
            self.short_term_buffer.pop(0)

    async def retrieve_context(self, query: str):
        """Retrieve relevant context for reasoning."""
        return await self.vector_memory.query(query)

    async def get_stats(self):
        """Return memory statistics."""
        return {
            "experience_count": self.vector_memory.count(),
            "short_term_buffer_size": len(self.short_term_buffer)
        }
