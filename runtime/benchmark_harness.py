from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import settings


class RuntimeBenchmarkHarness:
    def __init__(self):
        self.path: Path = settings.MEMORY_DIR / "benchmarks" / "runtime_subsystem_metrics.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.history: List[Dict[str, Any]] = self._load()

    def _load(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save(self):
        self.path.write_text(json.dumps(self.history[-200:], default=str, indent=2), encoding="utf-8")

    def record(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "metrics": metrics,
        }
        self.history.append(entry)
        self._save()
        return entry

    def latest(self) -> Optional[Dict[str, Any]]:
        return self.history[-1] if self.history else None

    def previous(self) -> Optional[Dict[str, Any]]:
        return self.history[-2] if len(self.history) >= 2 else None

    @staticmethod
    def benchmark_delta(current: Dict[str, Any], previous: Optional[Dict[str, Any]]) -> Dict[str, float]:
        if not previous:
            return {"overall_delta": 0.0}
        out: Dict[str, float] = {}
        for key, value in current.items():
            if not isinstance(value, (int, float)):
                continue
            prev_val = previous.get(key)
            if isinstance(prev_val, (int, float)):
                out[f"{key}_delta"] = float(value) - float(prev_val)
        out["overall_delta"] = sum(out.values()) / max(len(out), 1)
        return out

