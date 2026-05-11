import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer
from loguru import logger
from config import settings
import time

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
        
        self.collection.add(
            documents=[content],
            metadatas=[metadata],
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

class MemorySystem:
    def __init__(self):
        self.vector_memory = VectorMemory()
        self.short_term_buffer = []

    async def add_experience(self, content: str, source: str = "general"):
        """Add a new experience to both short-term and long-term memory."""
        # 1. Add to short-term buffer
        self.short_term_buffer.append({
            "content": content,
            "source": source,
            "timestamp": time.time()
        })
        
        # 2. Persist to long-term vector memory
        await self.vector_memory.store(content, {"source": source})
        
        # Keep buffer manageable
        if len(self.short_term_buffer) > 100:
            self.short_term_buffer.pop(0)

    async def retrieve_context(self, query: str):
        """Retrieve relevant context for reasoning."""
        return await self.vector_memory.query(query)
