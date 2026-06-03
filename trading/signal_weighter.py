from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


DEFAULT_WEIGHTS = {
    "rsi": 0.20,
    "regime": 0.25,
    "sentiment": 0.15,
    "macro": 0.20,
    "pattern": 0.10,
    "timeframe": 0.10,
}


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


class SignalWeighter:
    def __init__(self, weights_file: str = "data/signal_weights.json"):
        self.path = Path(weights_file)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.weights = self._load()

    def _load(self) -> Dict[str, float]:
        if self.path.exists():
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                merged = DEFAULT_WEIGHTS.copy()
                for key, value in payload.items():
                    try:
                        merged[str(key)] = float(value)
                    except (TypeError, ValueError):
                        continue
                return self._normalize(merged)
        return self._normalize(DEFAULT_WEIGHTS.copy())

    def _save(self) -> None:
        self.path.write_text(json.dumps(self.weights, indent=2), encoding="utf-8")

    @staticmethod
    def _normalize(weights: Dict[str, float]) -> Dict[str, float]:
        cleaned: Dict[str, float] = {}
        for key, value in weights.items():
            try:
                numeric = max(0.0, float(value))
            except (TypeError, ValueError):
                continue
            cleaned[str(key)] = numeric
        total = sum(cleaned.values())
        if total <= 0.0:
            return DEFAULT_WEIGHTS.copy()
        return {k: v / total for k, v in cleaned.items()}

    def update_from_postmortem(self, signal_accuracy: Dict[str, Dict[str, Any]], min_samples: int = 10) -> None:
        for signal, stats in (signal_accuracy or {}).items():
            key = str(signal).strip().lower()
            if key not in self.weights or not isinstance(stats, dict):
                continue
            sample_size = int(stats.get("sample_size", 0) or 0)
            if sample_size < int(min_samples):
                continue
            win_rate = float(stats.get("win_rate", 0.0) or 0.0)
            current = float(self.weights.get(key, 0.0))
            if win_rate > 0.60:
                self.weights[key] = min(0.40, current * 1.10)
            elif win_rate < 0.45:
                self.weights[key] = max(0.05, current * 0.90)
        self.weights = self._normalize(self.weights)
        self._save()

    def score_opportunity(self, signals: Dict[str, Any]) -> float:
        if not isinstance(signals, dict):
            return 0.0
        total_weight = 0.0
        weighted_sum = 0.0
        for key, weight in self.weights.items():
            if key not in signals:
                continue
            normalized = self._normalize_signal(key, signals.get(key))
            weighted_sum += float(weight) * normalized
            total_weight += float(weight)
        if total_weight <= 0.0:
            return 0.0
        return _clip01(weighted_sum / total_weight)

    def _normalize_signal(self, key: str, value: Any) -> float:
        token = str(key or "").strip().lower()
        if token == "regime":
            mapping = {
                "bull": 0.85,
                "trending": 0.80,
                "sideways": 0.55,
                "ranging": 0.50,
                "bear": 0.25,
                "panic": 0.10,
            }
            return mapping.get(str(value).strip().lower(), 0.50)

        if token == "rsi":
            try:
                rsi = float(value)
            except (TypeError, ValueError):
                return 0.50
            # Centered confidence: values around 50 are neutral.
            score = 1.0 - abs(rsi - 50.0) / 50.0
            return _clip01(score)

        if token in {"sentiment", "pattern", "timeframe", "macro"}:
            if isinstance(value, str):
                txt = value.strip().lower()
                str_map = {
                    "risk_on": 0.75,
                    "risk_off": 0.25,
                    "positive": 0.75,
                    "neutral": 0.50,
                    "negative": 0.25,
                    "bullish": 0.75,
                    "bearish": 0.25,
                }
                if txt in str_map:
                    return str_map[txt]
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                return 0.50
            # Supports either [-1, 1] or [0, 1] ranges.
            if -1.0 <= numeric <= 1.0:
                return _clip01((numeric + 1.0) / 2.0)
            return _clip01(numeric)

        try:
            return _clip01(float(value))
        except (TypeError, ValueError):
            return 0.50
