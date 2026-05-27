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

    def record_trading_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        sharpe = float(metrics.get("sharpe_ratio", 0.0))
        drawdown = float(metrics.get("max_drawdown", 0.0))
        total_trades = int(metrics.get("total_trades", 0))
        normalized = {
            "sharpe_ratio": sharpe,
            "max_drawdown": drawdown,
            "total_trades": total_trades,
            "win_rate": float(metrics.get("win_rate", 0.0)),
            "profit_factor": float(metrics.get("profit_factor", 0.0)),
        }
        return self.record({"domain": "trading", "trading": normalized})

    def latest_trading_metrics(self) -> Optional[Dict[str, Any]]:
        for entry in reversed(self.history):
            metrics = entry.get("metrics", {})
            if isinstance(metrics, dict) and metrics.get("domain") == "trading":
                trading = metrics.get("trading")
                if isinstance(trading, dict):
                    return trading
        return None

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

