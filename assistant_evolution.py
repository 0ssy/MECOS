"""
MECOS Assistant Evolution - Phase 6
Logs interaction patterns and enables autonomous prompt/strategy evolution.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from loguru import logger

from memory_system import MemorySystem
from config import settings


class AssistantEvolution:
    def __init__(self, memory: MemorySystem):
        self.memory = memory
        self.drafts_dir = settings.DATA_DIR / "assistant" / "prompt_drafts"
        self.drafts_dir.mkdir(parents=True, exist_ok=True)
        self.patterns: Dict[str, Any] = {
            "frequent_questions": {},
            "referenced_files": {},
            "contacts": {},
            "code_topics": {},
        }

    def log_interaction(self, interaction_type: str, content: str, metadata: Dict = None):
        if interaction_type not in self.patterns:
            return
        key = content[:100].lower()
        self.patterns[interaction_type][key] = self.patterns[interaction_type].get(key, 0) + 1

    def get_usage_profile(self) -> Dict[str, Any]:
        return {
            "top_questions": sorted(self.patterns["frequent_questions"].items(), key=lambda x: -x[1])[:10],
            "top_files": sorted(self.patterns["referenced_files"].items(), key=lambda x: -x[1])[:10],
            "top_contacts": sorted(self.patterns["contacts"].items(), key=lambda x: -x[1])[:10],
            "top_code_topics": sorted(self.patterns["code_topics"].items(), key=lambda x: -x[1])[:10],
        }

    async def generate_prompt_tuning(self, llm_client=None) -> Dict[str, Any]:
        if not llm_client:
            return {"status": "no_llm"}

        profile = self.get_usage_profile()
        prompt = f"""Analyze assistant usage patterns and suggest system prompt refinements.

Usage profile:
{json.dumps(profile, indent=2)}

Create improved system prompt focusing on:
1. Common question types and expected answer formats
2. Domain expertise based on code topics
3. Contact handling patterns

Return JSON:
{{
    "system_prompt_variation": "improved system prompt text",
    "rationale": "why this change improves performance"
}}"""

        try:
            response = llm_client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            data = json.loads(response.choices[0].message.content)
            self._save_prompt_draft(data)
            return data
        except Exception as e:
            logger.error(f"Prompt tuning failed: {e}")
            return {"status": "error", "error": str(e)}

    def _save_prompt_draft(self, draft: Dict):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.drafts_dir / f"{ts}_prompt_draft.json"
        path.write_text(json.dumps(draft, indent=2, default=str))
        logger.info(f"Prompt draft saved: {path.name}")