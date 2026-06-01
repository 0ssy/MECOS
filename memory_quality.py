"""
MECOS Memory Quality Gate
Filters and scores memories before they enter long-term storage.
Prevents noise, duplicates, and low-value experiences from polluting the vector DB.
"""
import re
from typing import List, Dict, Any


class MemoryQualityGate:
    """
    Assesses whether a memory is worth storing in long-term vector memory.

    Scoring factors:
      - Source weight   (trading/reflection/benchmarking = high; general = low)
      - Content length  (too short = noise; too long = chunking needed)
      - Duplication     (near-duplicate of recent short-term buffer entry)
      - Contradiction   (explicit negation of a recent stored fact)
    """

    SOURCE_WEIGHTS: Dict[str, float] = {
        "trading": 1.0,
        "reflection": 0.9,
        "benchmarking": 0.85,
        "research": 0.8,
        "coding": 0.75,
        "general": 0.5,
        "system": 0.4,
    }

    MIN_QUALITY_SCORE: float = 0.35
    min_retrieval_score: float = 0.2

    # ── Public API ────────────────────────────────────────────────────────

    def assess(
        self,
        content: str,
        source: str,
        metadata: Dict[str, Any],
        short_term_buffer: List[Dict],
    ) -> Dict[str, Any]:
        """Return a quality dict; 'promote' key signals whether to persist."""
        source_weight = self.SOURCE_WEIGHTS.get(source, 0.5)

        length_score = self._length_score(content)
        dup_penalty = self._duplication_penalty(content, short_term_buffer)
        contra_penalty = self._contradiction_penalty(content, short_term_buffer)

        quality_score = (
            source_weight * 0.4
            + length_score * 0.4
            - dup_penalty * 0.15
            - contra_penalty * 0.05
        )
        quality_score = max(0.0, min(1.0, quality_score))

        return {
            "quality_score": quality_score,
            "source_weight": source_weight,
            "length_score": length_score,
            "duplication_penalty": dup_penalty,
            "contradiction_penalty": contra_penalty,
            "promote": quality_score >= self.MIN_QUALITY_SCORE,
        }

    def retrieval_score(
        self,
        content: str,
        query: str,
        metadata: Dict[str, Any],
    ) -> float:
        """Score a retrieved memory for relevance at query time."""
        base = metadata.get("quality_score", 0.5)
        source_w = metadata.get("source_weight", 0.5)
        # Recency boost: newer memories score slightly higher
        age_boost = 0.0
        ts = metadata.get("timestamp_unix")
        if ts:
            import time
            age_hours = (time.time() - float(ts)) / 3600
            age_boost = max(0.0, 0.1 - age_hours * 0.001)

        score = base * 0.5 + source_w * 0.4 + age_boost
        return min(1.0, score)

    # ── Private helpers ───────────────────────────────────────────────────

    @staticmethod
    def _length_score(content: str) -> float:
        n = len(content.strip())
        if n < 20:
            return 0.1
        if n < 60:
            return 0.5
        if n <= 2000:
            return 1.0
        # Very long; still store but with mild penalty
        return 0.7

    @staticmethod
    def _duplication_penalty(content: str, buffer: List[Dict]) -> float:
        """Simple token-overlap check against the last 20 buffer entries."""
        if not buffer:
            return 0.0
        tokens = set(re.findall(r"\w+", content.lower()))
        if not tokens:
            return 0.0
        recent = buffer[-20:]
        max_overlap = 0.0
        for entry in recent:
            other_tokens = set(re.findall(r"\w+", entry.get("content", "").lower()))
            if not other_tokens:
                continue
            overlap = len(tokens & other_tokens) / len(tokens | other_tokens)
            if overlap > max_overlap:
                max_overlap = overlap
        # Only penalise if very similar (>80% overlap)
        return max_overlap if max_overlap > 0.8 else 0.0

    @staticmethod
    def _contradiction_penalty(content: str, buffer: List[Dict]) -> float:
        """Detect simple explicit negations (e.g. 'NOT' flipping a recent fact)."""
        negation_words = {"not", "never", "false", "incorrect", "wrong", "no longer"}
        tokens = set(re.findall(r"\w+", content.lower()))
        if not (tokens & negation_words):
            return 0.0
        # A negation word is present — mild penalty to flag for review
        return 0.5

