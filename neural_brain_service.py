from __future__ import annotations

import os
from typing import Any, Dict, Optional

from loguru import logger


class NeuralBrainService:
    """
    Global neural brain service for MECOS runtime.
    Provides optional, shared access to MECOSBrain across subsystems.
    """

    def __init__(self, memory_system: Any = None, enabled: Optional[bool] = None):
        env_enabled = os.getenv("MECOS_ENABLE_NEURAL_BRAIN", "false").strip().lower() == "true"
        self.enabled = bool(env_enabled if enabled is None else enabled)
        self.memory_system = memory_system
        self.brain = None
        self.last_insight: Dict[str, Any] = {}
        self.last_error: str = ""

        if not self.enabled:
            logger.info("NeuralBrainService disabled (set MECOS_ENABLE_NEURAL_BRAIN=true to enable)")
            return

        try:
            from mecos_brain import MECOSBrain

            self.brain = MECOSBrain(memory_system=memory_system)
            logger.info("NeuralBrainService initialized")
        except Exception as exc:
            self.enabled = False
            self.last_error = str(exc)
            logger.warning(f"NeuralBrainService unavailable: {exc}")

    @property
    def is_available(self) -> bool:
        return bool(self.enabled and self.brain is not None)

    def process(self, ticker: str, signals: Dict[str, Any], bars: Any) -> Dict[str, Any]:
        if not self.is_available:
            return {}
        try:
            out = self.brain.process(ticker=ticker, signals=signals, bars=bars)
            self.last_insight = dict(out)
            return out
        except Exception as exc:
            self.last_error = str(exc)
            logger.warning(f"NeuralBrainService.process failed for {ticker}: {exc}")
            return {}

    def pretrain(self, price_df, episodes: int = 200) -> Dict[str, Any]:
        if not self.is_available:
            raise RuntimeError("Neural brain service is not available")
        self.brain.pretrain_on_history(price_df=price_df, n_episodes=int(episodes))
        return {"status": "OK", "episodes": int(episodes)}

    def runtime_insight(self, runtime_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Produce cross-system runtime insight using synthetic "SYS" signal token.
        """
        if not self.is_available:
            return {}
        signals = {
            "rsi": float(runtime_metrics.get("runtime_health", 50.0) or 50.0),
            "macd": float(runtime_metrics.get("efficiency_delta", 0.0) or 0.0),
            "news_sentiment": float(runtime_metrics.get("research_quality_index", 0.0) or 0.0),
            "portfolio_heat": float(runtime_metrics.get("cpu_load", 0.0) or 0.0),
            "drawdown": float(runtime_metrics.get("staleness_score", 0.0) or 0.0),
            "win_rate": float(runtime_metrics.get("success_rate", 0.5) or 0.5),
            "regime": str(runtime_metrics.get("runtime_regime", "sideways")),
            "fed_rate": 5.0,
            "vix": 20.0,
        }
        bars = [{"close": 1.0 + i * 0.001, "high": 1.0 + i * 0.0015, "low": 1.0 + i * 0.0005, "volume": 1000 + i} for i in range(80)]
        return self.process(ticker="SYS", signals=signals, bars=bars)

    def status(self) -> Dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "available": bool(self.is_available),
            "last_error": self.last_error,
            "last_insight_action": self.last_insight.get("action"),
            "last_insight_uncertainty": self.last_insight.get("uncertainty"),
        }
