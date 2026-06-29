"""
MECOS Requirement Engine - Phase 6
Detects missing capability gaps and proposes new tools/integrations.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from memory_system import MemorySystem
from config import settings


class RequirementEngine:
    def __init__(self, memory: MemorySystem):
        self.memory = memory
        self.proposals_dir = settings.DATA_DIR / "assistant" / "proposals"
        self.proposals_dir.mkdir(parents=True, exist_ok=True)
        self.failure_patterns: Dict[str, int] = {}

    def log_failure(self, domain: str, error: str):
        key = f"{domain}:{error[:50]}"
        self.failure_patterns[key] = self.failure_patterns.get(key, 0) + 1

    async def detect_gaps(self, threshold: int = 3) -> List[Dict[str, Any]]:
        gaps = []
        for key, count in self.failure_patterns.items():
            if count >= threshold:
                domain, error = key.split(":", 1)
                gaps.append({
                    "domain": domain,
                    "error": error,
                    "frequency": count,
                    "detected_at": datetime.utcnow().isoformat(),
                })
        return gaps

    async def propose_tool(self, gap: Dict, llm_client=None) -> Optional[Dict[str, Any]]:
        if not llm_client:
            return None

        prompt = f"""A capability gap was detected in MECOS:
Domain: {gap['domain']}
Error: {gap['error']} (occurred {gap['frequency']} times)

Propose a new tool or integration to fill this gap.
Include:
1. Tool name and purpose
2. Parameters it should accept
3. Implementation approach (reuse existing or new)

Return JSON:
{{
    "tool_name": "name",
    "purpose": "what it does",
    "parameters": ["param1", "param2"],
    "implementation": "how to build it"
}}"""

        try:
            response = llm_client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            data = json.loads(response.choices[0].message.content)
            self._save_proposal(data, gap)
            return data
        except Exception as e:
            logger.error(f"Proposal generation failed: {e}")
            return None

    def _save_proposal(self, proposal: Dict, gap: Dict):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.proposals_dir / f"{ts}_{proposal.get('tool_name', 'proposal')}.json"
        payload = {
            "proposal": proposal,
            "gap": gap,
            "created_at": datetime.utcnow().isoformat(),
            "status": "pending_review",
        }
        path.write_text(json.dumps(payload, indent=2))
        logger.info(f"Proposal saved for review: {path.name}")

    def list_pending_proposals(self) -> List[Dict]:
        proposals = []
        for f in sorted(self.proposals_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                if data.get("status") == "pending_review":
                    proposals.append(data)
            except Exception:
                continue
        return proposals

    def approve_proposal(self, filename: str) -> bool:
        path = self.proposals_dir / filename
        if not path.exists():
            return False
        data = json.loads(path.read_text())
        data["status"] = "approved"
        data["approved_at"] = datetime.utcnow().isoformat()
        path.write_text(json.dumps(data, indent=2))
        return True