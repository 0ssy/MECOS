"""
MECOS Memory Layer — Vector Memory
Local-first persistent memory for learned runtime artifacts.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class VectorMemory:
    def __init__(self, storage_path: Optional[str] = None):
        base = Path(storage_path) if storage_path else Path(__file__).resolve().parent / "data" / "mecos_memory"
        self.storage_path = base
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.index_file = self.storage_path / "index.json"
        self.memory_store: List[Dict[str, Any]] = self._load_index()

    def _load_index(self) -> List[Dict[str, Any]]:
        if not self.index_file.exists():
            return []
        try:
            return json.loads(self.index_file.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save_index(self):
        self.index_file.write_text(json.dumps(self.memory_store, indent=2), encoding="utf-8")

    def store(self, content: str, metadata: Dict[str, Any], embedding: Optional[List[float]] = None):
        entry = {
            "content": content,
            "metadata": metadata,
            "embedding": embedding,
            "timestamp": time.time(),
        }
        self.memory_store.append(entry)
        self._save_index()

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        token = query.lower()
        matches = []
        for item in self.memory_store:
            if token in str(item.get("content", "")).lower():
                matches.append(item)
                continue
            if any(token in str(v).lower() for v in item.get("metadata", {}).values()):
                matches.append(item)
        return matches[:limit]

