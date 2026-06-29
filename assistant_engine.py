"""
MECOS Assistant Engine - Phase 4
Subscribes to transcript segments and routes questions to the reasoner.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Optional

from loguru import logger

from memory_system import MemorySystem
from reasoner import Reasoner
from action_engine import ActionExecutionEngine


QUESTION_PATTERNS = [
    r"(?i)\b(what|how|why|when|where|who|can you|could you|would you)\b.*\?",
    r"(?i)\b(question|help|explain|define|describe)\b",
    r"(?i)\b(code|implement|write|fix|debug)\b.*\b(python|js|ts|code)\b",
]


class AssistantEngine:
    def __init__(
        self,
        memory: MemorySystem,
        reasoner: Reasoner,
        action_engine: Optional[ActionExecutionEngine] = None,
    ):
        self.memory = memory
        self.reasoner = reasoner
        self.action_engine = action_engine
        self.recent_segments: list[str] = []
        self._question_cache: set[str] = set()

    def detect_question(self, text: str) -> Optional[str]:
        for pattern in QUESTION_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return text[match.start():].strip().rstrip("?")
        return None

    async def process_segment(self, segment: str) -> Optional[dict]:
        if not segment:
            return None

        self.recent_segments.append(segment)
        if len(self.recent_segments) > 50:
            self.recent_segments = self.recent_segments[-50:]

        question = self.detect_question(segment)
        if not question:
            return None

        question_key = question[:60].lower()
        if question_key in self._question_cache:
            return None
        self._question_cache.add(question_key)
        if len(self._question_cache) > 100:
            self._question_cache = set(list(self._question_cache)[50:])

        logger.info(f"Assistant detected question: {question[:80]}")

        try:
            plan = await self.reasoner.generate_plan(f"Answer this question: {question}")
            if plan:
                results = await self.action_engine.execute_plan(plan) if self.action_engine else []
                answer = self._format_answer(results, question)
                await self.memory.add_experience(
                    f"ASSISTANT Q&A: Q={question[:200]}\nA={answer[:500]}",
                    source="assistant",
                )
                return {"question": question, "answer": answer, "plan": plan}
        except Exception as e:
            logger.error(f"Failed to process question: {e}")

        return None

    def _format_answer(self, results: list, question: str) -> str:
        if not results:
            return "No answer generated."
        lines = []
        for r in results:
            if r.get("status") == "ok" and r.get("result"):
                lines.append(str(r["result"])[:500])
        return "\n".join(lines) if lines else "No answer available."

    async def get_suggestion(self, context: str = "") -> Optional[str]:
        if not context:
            context = "\n".join(self.recent_segments[-10:])
        if not context:
            return None

        try:
            plan = await self.reasoner.generate_plan(
                f"Analyze this meeting context and suggest a helpful response:\n{context[:500]}",
            )
            if plan and self.action_engine:
                results = await self.action_engine.execute_plan(plan)
                return self._format_answer(results, context)
        except Exception as e:
            logger.debug(f"Suggestion generation failed: {e}")
        return None