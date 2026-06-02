"""
MECOS Vector Store
==================
Local semantic search using ChromaDB + sentence-transformers.
Everything runs on your machine. No API keys. No internet required after setup.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CHROMA_DIR = Path("mecos_chroma")


class VectorStore:
    """
    Stores text chunks as embeddings for semantic (fuzzy) search.
    Complements the Knowledge Graph (which handles logical/relational search).
    """

    def __init__(self, persist_dir: Path = CHROMA_DIR, collection_name: str = "mecos_knowledge"):
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self._client = None
        self._collection = None
        self._embedder = None

    def _init(self):
        """Lazy init so import does not crash if deps are not installed yet."""
        if self._client is not None:
            return

        try:
            import chromadb
        except ImportError as exc:
            raise ImportError("Run: pip install chromadb") from exc

        try:
            from sentence_transformers import SentenceTransformer

            self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
        except ImportError as exc:
            raise ImportError("Run: pip install sentence-transformers") from exc

        self._client = chromadb.PersistentClient(path=str(self.persist_dir))
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("VectorStore ready: %d documents", self._collection.count())

    def add(self, doc_id: str, text: str, metadata: dict | None = None):
        """Store a text chunk with its embedding."""
        self._init()
        embedding = self._embedder.encode(text).tolist()
        self._collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata or {}],
        )

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Find the most semantically similar documents to a query."""
        self._init()
        query_embedding = self._embedder.encode(query).tolist()
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self._collection.count() or 1),
            include=["documents", "metadatas", "distances"],
        )
        output = []
        for index, doc in enumerate(results["documents"][0]):
            output.append(
                {
                    "text": doc,
                    "metadata": results["metadatas"][0][index],
                    "score": 1 - results["distances"][0][index],
                }
            )
        return output

    def count(self) -> int:
        self._init()
        return self._collection.count()

    def stats(self) -> dict:
        return {
            "documents": self.count(),
            "persist_dir": str(self.persist_dir),
            "collection": self.collection_name,
        }
