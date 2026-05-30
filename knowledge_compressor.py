"""
knowledge_compressor.py
Distills raw memory content into structured, reusable knowledge concepts.

Instead of storing "WEB CONTENT from duckduckgo..." verbatim,
this compresses discoveries into:
    - Named concepts with definitions
    - Relationships between concepts
    - Reusable strategy patterns
    - Contradiction detection

Feeds compressed knowledge into KnowledgeGraph and back into MemorySystem
with higher quality scores.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from loguru import logger

from knowledge_graph import KnowledgeGraph
from memory_system import MemorySystem


COMPRESSION_PROMPT = """You are a knowledge distillation engine.

Given raw research content, extract structured knowledge.
Respond ONLY with valid JSON, no other text.

Format:
{{
  "concepts": [
    {{"name": "concept name", "definition": "one sentence", "domain": "trading|coding|systems|research"}}
  ],
  "relationships": [
    {{"from": "concept A", "to": "concept B", "relation": "enables|contradicts|extends|requires"}}
  ],
  "patterns": [
    {{"name": "pattern name", "description": "reusable insight", "applicability": "when to use"}}
  ],
  "quality_score": 0.0
}}

quality_score: 0.0-1.0 based on information density. Raw search results = 0.1-0.2. 
Novel insights = 0.6-0.9.

Raw content to distill:
{content}"""


@dataclass
class CompressedKnowledge:
    concepts:      List[Dict]
    relationships: List[Dict]
    patterns:      List[Dict]
    quality_score: float
    source_hash:   str
    compressed_at: float = 0.0

    def __post_init__(self):
        if not self.compressed_at:
            self.compressed_at = time.time()


class KnowledgeCompressor:
    """
    Reads raw memories, compresses them into structured knowledge,
    stores concepts in KnowledgeGraph, and promotes high-quality
    compressed knowledge back into MemorySystem.
    """

    MIN_CONTENT_LENGTH = 100    # Skip very short content
    MIN_QUALITY_SCORE  = 0.35   # Only store if quality passes threshold
    BATCH_SIZE         = 10     # Process N memories per cycle
    SEEN_PATH          = Path("data/compressor_seen.json")

    def __init__(self, memory: MemorySystem, knowledge_graph: KnowledgeGraph, llm=None):
        self.memory  = memory
        self.graph   = knowledge_graph
        self.llm     = llm
        self._seen:  set = self._load_seen()
        self._stats  = {"compressed": 0, "skipped": 0, "errors": 0, "promoted": 0}
        logger.info("KnowledgeCompressor initialized")

    def _load_seen(self) -> set:
        if self.SEEN_PATH.exists():
            try:
                return set(json.loads(self.SEEN_PATH.read_text()))
            except Exception:
                pass
        return set()

    def _save_seen(self):
        try:
            self.SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
            # Keep only last 5000 hashes
            seen_list = list(self._seen)[-5000:]
            self.SEEN_PATH.write_text(json.dumps(seen_list))
        except Exception as e:
            logger.error(f"KnowledgeCompressor: failed to save seen hashes: {e}")

    def _hash(self, content: str) -> str:
        return hashlib.md5(content.encode()).hexdigest()[:16]

    async def compress_cycle(self) -> Dict[str, Any]:
        """
        One compression cycle:
        1. Retrieve recent raw memories
        2. Filter already-compressed ones
        3. Compress via LLM
        4. Store concepts in KnowledgeGraph
        5. Promote high-quality summaries to MemorySystem
        """
        try:
            raw = await self.memory.retrieve_context(
                "recent research discoveries",
                n_results=self.BATCH_SIZE
            )
        except Exception as e:
            logger.error(f"KnowledgeCompressor: retrieval failed: {e}")
            return self._stats.copy()

        documents = []
        if isinstance(raw, dict):
            documents = raw.get("documents", [[]])[0]
        elif isinstance(raw, list):
            documents = raw

        for doc in documents:
            if not isinstance(doc, str) or len(doc) < self.MIN_CONTENT_LENGTH:
                self._stats["skipped"] += 1
                continue

            h = self._hash(doc)
            if h in self._seen:
                self._stats["skipped"] += 1
                continue

            compressed = await self._compress(doc)
            if compressed is None:
                self._stats["errors"] += 1
                self._seen.add(h)
                continue

            if compressed.quality_score < self.MIN_QUALITY_SCORE:
                self._stats["skipped"] += 1
                self._seen.add(h)
                continue

            # Store concepts in KnowledgeGraph
            self._store_in_graph(compressed)

            # Promote compressed summary to MemorySystem
            summary = self._build_summary(compressed)
            try:
                await self.memory.add_experience(
                    summary,
                    source="knowledge_compressor",
                    metadata={
                        "quality_score": compressed.quality_score,
                        "compressed": True,
                        "concepts": len(compressed.concepts),
                        "patterns": len(compressed.patterns),
                    }
                )
                self._stats["promoted"] += 1
            except Exception as e:
                logger.error(f"KnowledgeCompressor: promote failed: {e}")

            self._stats["compressed"] += 1
            self._seen.add(h)

        self._save_seen()
        logger.info(
            f"KnowledgeCompressor cycle: compressed={self._stats['compressed']} "
            f"promoted={self._stats['promoted']} skipped={self._stats['skipped']}"
        )
        return self._stats.copy()

    async def _compress(self, content: str) -> Optional[CompressedKnowledge]:
        """Call LLM to compress raw content into structured knowledge."""
        if self.llm is None:
            # No LLM available — create minimal structure from content
            return CompressedKnowledge(
                concepts=[],
                relationships=[],
                patterns=[{"name": "raw_insight", "description": content[:200], "applicability": "general"}],
                quality_score=0.2,
                source_hash=self._hash(content),
            )

        prompt = COMPRESSION_PROMPT.format(content=content[:2000])
        try:
            result = await self.llm.think_and_act(prompt, system_prompt="Knowledge distillation engine. JSON only.")
            response = result.get("response", "") if isinstance(result, dict) else str(result)

            # Extract JSON
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                return None
            data = json.loads(json_match.group())

            return CompressedKnowledge(
                concepts=data.get("concepts", []),
                relationships=data.get("relationships", []),
                patterns=data.get("patterns", []),
                quality_score=float(data.get("quality_score", 0.2)),
                source_hash=self._hash(content),
            )
        except Exception as e:
            logger.debug(f"KnowledgeCompressor LLM error: {e}")
            return None

    def _store_in_graph(self, ck: CompressedKnowledge):
        """Store concepts and relationships in KnowledgeGraph."""
        for concept in ck.concepts:
            name   = str(concept.get("name", ""))
            domain = str(concept.get("domain", "general"))
            defn   = str(concept.get("definition", ""))
            if name:
                self.graph.add_node(
                    node_id=f"concept:{name.lower().replace(' ', '_')}",
                    node_type="concept",
                    properties={"definition": defn, "domain": domain, "compressed_at": ck.compressed_at},
                )

        for rel in ck.relationships:
            frm      = f"concept:{str(rel.get('from', '')).lower().replace(' ', '_')}"
            to       = f"concept:{str(rel.get('to', '')).lower().replace(' ', '_')}"
            relation = str(rel.get("relation", "related"))
            if frm and to:
                self.graph.add_edge(frm, to, relation)

        for pattern in ck.patterns:
            name = str(pattern.get("name", ""))
            if name:
                self.graph.add_node(
                    node_id=f"pattern:{name.lower().replace(' ', '_')}",
                    node_type="pattern",
                    properties={
                        "description":     str(pattern.get("description", "")),
                        "applicability":   str(pattern.get("applicability", "")),
                        "compressed_at":   ck.compressed_at,
                        "quality":         ck.quality_score,
                    }
                )

    def _build_summary(self, ck: CompressedKnowledge) -> str:
        parts = []
        if ck.concepts:
            parts.append("CONCEPTS: " + "; ".join(
                f"{c.get('name','')}: {c.get('definition','')}"
                for c in ck.concepts[:5]
            ))
        if ck.patterns:
            parts.append("PATTERNS: " + "; ".join(
                f"{p.get('name','')}: {p.get('description','')}"
                for p in ck.patterns[:3]
            ))
        return " | ".join(parts) if parts else "Compressed knowledge entry"

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "graph_nodes": len(self.graph.nodes),
            "graph_edges": len(self.graph.edges),
            "seen_hashes": len(self._seen),
        }
