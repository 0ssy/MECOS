from __future__ import annotations

import math
import re
import time
from typing import Any, Dict, List, Optional, Sequence


class MemoryQualityGate:
    def __init__(self):
        self.source_weights: Dict[str, float] = {
            "reasoner": 0.95,
            "research_agent": 0.9,
            "action_execution": 0.85,
            "coding_agent": 0.85,
            "perception": 0.75,
            "web_perception": 0.7,
            "general": 0.6,
        }
        self.decay_half_life_seconds = 7 * 24 * 60 * 60  # 7 days
        self.min_promotion_score = 0.45
        self.min_retrieval_score = 0.20

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return re.findall(r"[a-zA-Z0-9_]+", (text or "").lower())

    @staticmethod
    def _has_negation(text: str) -> bool:
        lowered = (text or "").lower()
        neg_terms = (" not ", " never ", " cannot ", " can't ", " no ", " false ", " wrong ")
        padded = f" {lowered} "
        return any(term in padded for term in neg_terms)

    def _source_weight(self, source: str) -> float:
        return float(self.source_weights.get((source or "general").lower(), 0.6))

    def _base_content_score(self, content: str) -> float:
        text = (content or "").strip()
        if not text:
            return 0.0
        if len(text) < 12:
            return 0.2
        tokens = self._tokenize(text)
        unique_ratio = len(set(tokens)) / max(1, len(tokens))
        repetition_penalty = 0.25 if unique_ratio < 0.3 else 0.0
        return max(0.0, min(1.0, 0.7 + (0.2 * unique_ratio) - repetition_penalty))

    def _contradiction_penalty(
        self,
        content: str,
        source: str,
        metadata: Dict[str, Any],
        short_term_buffer: Sequence[Dict[str, Any]],
    ) -> float:
        topic = str(metadata.get("topic", "")).lower()
        tokens = set(self._tokenize(content))
        if not tokens:
            return 0.0

        contradiction_hits = 0
        window = list(short_term_buffer)[-40:]
        for item in window:
            if str(item.get("source", "")).lower() != str(source or "").lower():
                continue
            prior_topic = str(item.get("metadata", {}).get("topic", "")).lower()
            if topic and prior_topic and topic != prior_topic:
                continue

            prior_content = str(item.get("content", ""))
            prior_tokens = set(self._tokenize(prior_content))
            overlap = len(tokens & prior_tokens) / max(1, len(tokens | prior_tokens))
            if overlap < 0.35:
                continue
            if self._has_negation(content) != self._has_negation(prior_content):
                contradiction_hits += 1

        return min(0.45, contradiction_hits * 0.15)

    def assess(
        self,
        content: str,
        source: str,
        metadata: Optional[Dict[str, Any]],
        short_term_buffer: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        md = dict(metadata or {})
        source_weight = self._source_weight(source)
        base_confidence = float(md.get("confidence", 0.65))
        base_confidence = max(0.0, min(1.0, base_confidence))
        content_score = self._base_content_score(content)
        contradiction_penalty = self._contradiction_penalty(content, source, md, short_term_buffer)

        score = (0.45 * base_confidence) + (0.35 * source_weight) + (0.20 * content_score) - contradiction_penalty
        quality_score = max(0.0, min(1.0, score))
        promote = quality_score >= self.min_promotion_score

        return {
            "source_weight": source_weight,
            "base_confidence": base_confidence,
            "content_score": content_score,
            "contradiction_penalty": contradiction_penalty,
            "quality_score": quality_score,
            "promote": promote,
        }

    def decay_factor(self, timestamp: float) -> float:
        age = max(0.0, time.time() - float(timestamp or time.time()))
        if self.decay_half_life_seconds <= 0:
            return 1.0
        return 0.5 ** (age / self.decay_half_life_seconds)

    def retrieval_score(self, content: str, query: str, metadata: Optional[Dict[str, Any]]) -> float:
        md = metadata or {}
        quality = float(md.get("quality_score", 0.5))
        timestamp = float(md.get("timestamp_unix", time.time()))
        decay = self.decay_factor(timestamp)

        q_tokens = set(self._tokenize(query))
        c_tokens = set(self._tokenize(content))
        relevance = 1.0
        if q_tokens:
            relevance = len(q_tokens & c_tokens) / max(1, len(q_tokens))

        score = (0.55 * quality) + (0.30 * relevance) + (0.15 * decay)
        return max(0.0, min(1.0, score))

