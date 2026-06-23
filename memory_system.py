import chromadb
import os
import uuid
from loguru import logger
from config import settings
import time
import json
import asyncio
from typing import Any, Dict, List, Optional, Tuple

from memory_quality import MemoryQualityGate

class VectorMemory:
    def __init__(self):
        is_pytest = "PYTEST_CURRENT_TEST" in os.environ

        if is_pytest:
            self.client = chromadb.EphemeralClient()
            collection_name = f"mecos_long_term_{os.getpid()}_{uuid.uuid4().hex[:8]}"
            logger.info("Vector Memory using EphemeralClient (pytest).")
        else:
            self.client = chromadb.PersistentClient(path=settings.VECTOR_DB_PATH)
            collection_name = "mecos_long_term"
            logger.info("Vector Memory using PersistentClient.")

        self.collection = self.client.get_or_create_collection(name=collection_name)
        self._op_lock = asyncio.Lock()
        logger.info("Vector Memory System Initialized.")

    @staticmethod
    def _is_transient_chroma_error(exc: Exception) -> bool:
        msg = str(exc).lower()
        return (
            "compaction" in msg
            or "hnsw" in msg
            or "failed to apply logs" in msg
            or "database is locked" in msg
            or "temporarily unavailable" in msg
            or "timeout" in msg
        )

    async def _run_collection_op(self, op_name: str, operation, retries: int = 3):
        last_error = None
        for attempt in range(1, retries + 1):
            async with self._op_lock:
                try:
                    return await asyncio.to_thread(operation)
                except Exception as exc:
                    last_error = exc
                    if not self._is_transient_chroma_error(exc) or attempt >= retries:
                        raise
                    backoff = 0.25 * attempt
                    logger.warning(
                        f"Transient Chroma error during {op_name} (attempt {attempt}/{retries}): {exc}. "
                        f"Retrying in {backoff:.2f}s"
                    )
            await asyncio.sleep(backoff)
        raise RuntimeError(f"Chroma operation failed for {op_name}: {last_error}")

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
        
        def _add():
            self.collection.add(
                documents=[content],
                metadatas=[sanitized_metadata],
                ids=[f"mem_{int(time.time() * 1000)}"],
            )

        await self._run_collection_op("collection.add", _add)
        logger.debug(f"Stored memory: {content[:50]}...")

    async def query(self, text: str, n_results: int = 5):
        """Query the vector database for similar content."""
        def _query():
            return self.collection.query(
                query_texts=[text],
                n_results=n_results,
            )

        results = await self._run_collection_op("collection.query", _query)
        return results

    def count(self):
        """Return the total number of items in the collection."""
        try:
            return self.collection.count()
        except Exception as exc:
            if self._is_transient_chroma_error(exc):
                logger.warning(f"Transient Chroma count error: {exc}")
                return 0
            raise


class MemorySystem:
    def __init__(self):
        self.vector_memory = VectorMemory()
        self.short_term_buffer = []
        self.quality_gate = MemoryQualityGate()
        self.quality_stats = {
            "promoted": 0,
            "demoted": 0,
            "contradictions": 0,
        }

    async def add_experience(self, content: str, source: str = "general", metadata: dict = None):
        """Add a new experience to both short-term and long-term memory."""
        metadata = dict(metadata or {})
        quality = self.quality_gate.assess(
            content=content,
            source=source,
            metadata=metadata,
            short_term_buffer=self.short_term_buffer,
        )
        metadata.update(
            {
                "quality_score": float(quality["quality_score"]),
                "source_weight": float(quality["source_weight"]),
                "timestamp_unix": float(time.time()),
                "promoted": bool(quality["promote"]),
                "contradiction_penalty": float(quality["contradiction_penalty"]),
            }
        )

        if quality["contradiction_penalty"] > 0:
            self.quality_stats["contradictions"] += 1

        # 1. Add to short-term buffer
        self.short_term_buffer.append({
            "content": content,
            "source": source,
            "metadata": metadata,
            "timestamp": time.time()
        })

        # 2. Persist to long-term vector memory only for quality-promoted memories.
        if quality["promote"]:
            store_metadata = {"source": source}
            store_metadata.update(metadata)
            await self.vector_memory.store(content, store_metadata)
            self.quality_stats["promoted"] += 1
        else:
            self.quality_stats["demoted"] += 1
            logger.debug(
                f"Memory demoted (not persisted): source={source} quality={quality['quality_score']:.2f} "
                f"content={content[:80]}"
            )

        # Keep buffer manageable
        if len(self.short_term_buffer) > 250:
            self.short_term_buffer.pop(0)

    async def retrieve_context(self, query: str, n_results: int = 5):
        """Retrieve relevant context for reasoning."""
        fetch_n = max(int(n_results), 1)
        raw = await self.vector_memory.query(query, n_results=min(5000, max(10, fetch_n * 4)))
        return self._rerank_results(raw, query=query, n_results=fetch_n)

    def _rerank_results(self, raw: Dict[str, Any], query: str, n_results: int) -> Dict[str, Any]:
        docs = (raw.get("documents") or [[]])[0]
        metas = (raw.get("metadatas") or [[]])[0]
        ids = (raw.get("ids") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]

        rows: List[Tuple[float, str, Dict[str, Any], Any, Any]] = []
        for idx, doc in enumerate(docs):
            meta = metas[idx] if idx < len(metas) and isinstance(metas[idx], dict) else {}
            retrieval_score = self.quality_gate.retrieval_score(
                content=str(doc),
                query=query,
                metadata=meta,
            )
            if retrieval_score < self.quality_gate.min_retrieval_score:
                continue
            row_id = ids[idx] if idx < len(ids) else None
            row_dist = distances[idx] if idx < len(distances) else None
            rows.append((retrieval_score, str(doc), meta, row_id, row_dist))

        rows.sort(key=lambda r: r[0], reverse=True)
        selected = rows[:n_results]

        selected_docs = [r[1] for r in selected]
        selected_metas = [dict(r[2], retrieval_score=float(r[0])) for r in selected]
        selected_ids = [r[3] for r in selected]
        selected_distances = [r[4] for r in selected if r[4] is not None]

        return {
            "documents": [selected_docs],
            "metadatas": [selected_metas],
            "ids": [selected_ids],
            "distances": [selected_distances],
        }

    async def get_stats(self):
        """Return memory statistics."""
        return {
            "experience_count": self.vector_memory.count(),
            "short_term_buffer_size": len(self.short_term_buffer),
            "quality": dict(self.quality_stats),
        }
