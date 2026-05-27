from __future__ import annotations

from typing import Any, Dict


class ResearchGovernor:
    def __init__(self):
        self.last_metrics: Dict[str, Any] = {}

    def evaluate(self, research_metrics: Dict[str, Any]) -> Dict[str, Any]:
        useful_per_hour = float(research_metrics.get("useful_discoveries_per_hour", 0.0))
        usefulness_ratio = float(research_metrics.get("usefulness_ratio", 0.0))
        quality_index = (0.65 * usefulness_ratio) + (0.35 * min(useful_per_hour / 12.0, 1.0))
        self.last_metrics = {
            "useful_discoveries_per_hour": useful_per_hour,
            "usefulness_ratio": usefulness_ratio,
            "research_quality_index": quality_index,
            "research_priority": "high" if quality_index >= 0.45 else "critical",
        }
        return dict(self.last_metrics)

