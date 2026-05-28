from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import settings


class DriftGuard:
    def __init__(self):
        self.baseline_path: Path = settings.DATA_DIR / "runtime_baseline.json"
        self.anchor_path: Path = settings.DATA_DIR / "trusted_memory_anchors.json"
        self.baseline = self._load_json(self.baseline_path, default={})
        self.anchors = self._load_json(self.anchor_path, default={"anchors": []})
        if "anchors" not in self.anchors:
            self.anchors["anchors"] = []

    @staticmethod
    def _load_json(path: Path, default: Any):
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    @staticmethod
    def _save_json(path: Path, payload: Any):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")

    def set_baseline_if_missing(self, metrics: Dict[str, Any]):
        if self.baseline:
            return
        self.baseline = {"metrics": metrics}
        self._save_json(self.baseline_path, self.baseline)

    def evaluate(self, metrics: Dict[str, Any], drift_threshold: float = -0.15) -> Dict[str, Any]:
        self.set_baseline_if_missing(metrics)
        baseline_metrics = self.baseline.get("metrics", {})
        deltas: Dict[str, float] = {}
        for key, value in metrics.items():
            if not isinstance(value, (int, float)):
                continue
            b = baseline_metrics.get(key)
            if isinstance(b, (int, float)):
                denom = abs(float(b)) if abs(float(b)) > 1e-6 else 1.0
                deltas[key] = (float(value) - float(b)) / denom
        average_delta = sum(deltas.values()) / max(len(deltas), 1)
        drift_detected = average_delta < drift_threshold
        return {
            "drift_detected": drift_detected,
            "average_delta": average_delta,
            "deltas": deltas,
        }

    def add_anchor(self, content: str, source: str = "trusted_operator"):
        anchors: List[Dict[str, str]] = self.anchors.setdefault("anchors", [])
        anchors.append({"content": content, "source": source})
        self._save_json(self.anchor_path, self.anchors)

