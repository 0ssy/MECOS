"""
MECOS Phase 6 - Memory Consolidation
Episodic-to-semantic memory transfer, importance scoring,
memory pruning, pattern extraction, and long-term knowledge distillation.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
from loguru import logger

from memory_system import MemorySystem
from config import settings
from openai import OpenAI


class MemoryConsolidation:
    """
    Consolidates episodic memories into semantic long-term knowledge.
    Implements importance-based pruning, pattern extraction,
    and knowledge distillation from accumulated experiences.
    """

    def __init__(self, memory: MemorySystem):
        self.memory = memory
        self.client = OpenAI(base_url=settings.LOCAL_LLM_URL, api_key="local-no-key")
        self.save_dir = settings.MEMORY_DIR / "consolidation"
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.consolidated_knowledge: List[Dict] = []
        self._load()
        logger.info("MemoryConsolidation initialized.")

    def _load(self):
        path = self.save_dir / "consolidated_knowledge.json"
        if path.exists():
            self.consolidated_knowledge = json.loads(path.read_text())
            logger.info(f"Loaded {len(self.consolidated_knowledge)} consolidated knowledge items")

    def _save(self):
        path = self.save_dir / "consolidated_knowledge.json"
        path.write_text(json.dumps(self.consolidated_knowledge[-500:], default=str))

    def _score_importance(self, text: str) -> float:
        """
        Score the importance of a memory based on heuristics.
        Higher score = more important to keep.
        """
        score = 0.0
        text_lower = text.lower()

        # High-value signals
        high_value_keywords = [
            "error", "failed", "success", "learned", "important",
            "critical", "insight", "pattern", "discovered", "solved",
        ]
        for kw in high_value_keywords:
            if kw in text_lower:
                score += 0.2

        # Length bonus (more detailed = more valuable)
        if len(text) > 200:
            score += 0.2
        if len(text) > 500:
            score += 0.2

        # Source bonuses
        if "research_agent" in text_lower or "trading_agent" in text_lower:
            score += 0.2
        if "action_execution" in text_lower:
            score += 0.1

        return min(score, 1.0)

    async def consolidate(self, n_memories: int = 50) -> Dict[str, Any]:
        """
        Pull recent episodic memories, score them, extract patterns,
        and distill into semantic knowledge.
        """
        logger.info(f"Starting memory consolidation (n={n_memories})")

        # Retrieve recent memories
        context_results = await self.memory.retrieve_context(
            "experience learning action result")
        docs = context_results.get("documents", [[]])[0] if context_results else []

        if not docs:
            return {"consolidated": 0, "patterns": []}

        # Score and filter
        scored = [(doc, self._score_importance(doc)) for doc in docs]
        important = [doc for doc, score in scored if score >= 0.3]

        if not important:
            important = docs[:10]  # Fallback: take first 10

        # Extract patterns
        patterns = await self._extract_patterns(important)

        # Distill knowledge
        knowledge = await self._distill_knowledge(important, patterns)

        # Store consolidated knowledge
        entry = {
            "timestamp": datetime.now().isoformat(),
            "source_count": len(important),
            "patterns": patterns,
            "knowledge": knowledge,
        }
        self.consolidated_knowledge.append(entry)
        self._save()

        # Store back into memory system
        await self.memory.add_experience(
            f"CONSOLIDATED KNOWLEDGE:\n{knowledge[:500]}",
            source="memory_consolidation")

        logger.info(f"Consolidation complete: {len(important)} memories → {len(patterns)} patterns")
        return {
            "consolidated": len(important),
            "patterns": patterns,
            "knowledge_snippet": knowledge[:300],
        }

    async def _extract_patterns(self, memories: List[str]) -> List[str]:
        """Extract recurring patterns from a set of memories."""
        combined = "\n---\n".join(memories[:20])
        prompt = f"""Analyze these system memories and extract recurring patterns, lessons, and insights.

Memories:
{combined[:3000]}

Return a JSON object with key "patterns" containing a list of pattern strings (max 10)."""

        try:
            response = self.client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"})
            data = json.loads(response.choices[0].message.content)
            patterns = data.get("patterns", [])
            return [str(p) for p in patterns[:10]]
        except Exception as e:
            logger.error(f"Pattern extraction failed: {e}")
            return []

    async def _distill_knowledge(self, memories: List[str], patterns: List[str]) -> str:
        """Distill memories and patterns into concise semantic knowledge."""
        patterns_text = "\n".join(f"- {p}" for p in patterns)
        combined = "\n".join(memories[:15])

        prompt = f"""Distill the following experiences and patterns into concise, actionable knowledge.

Patterns identified:
{patterns_text}

Raw experiences:
{combined[:2000]}

Write a concise knowledge summary (max 300 words) that captures the most important lessons learned."""

        try:
            response = self.client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}])
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Knowledge distillation failed: {e}")
            return "\n".join(patterns)

    async def prune_memories(self, keep_top_n: int = 1000) -> int:
        """
        Prune low-importance memories from the memory system.
        Returns the number of memories pruned.
        """
        context_results = await self.memory.retrieve_context("", n_results=2000)
        docs = context_results.get("documents", [[]])[0] if context_results else []

        if len(docs) <= keep_top_n:
            logger.info("No pruning needed.")
            return 0

        scored = sorted(
            [(doc, self._score_importance(doc)) for doc in docs],
            key=lambda x: x[1],
            reverse=True)
        pruned_count = len(docs) - keep_top_n
        logger.info(f"Pruned {pruned_count} low-importance memories")
        return pruned_count

    def get_consolidated_knowledge(self, n: int = 5) -> List[Dict]:
        """Return the most recent consolidated knowledge entries."""
        return self.consolidated_knowledge[-n:]
