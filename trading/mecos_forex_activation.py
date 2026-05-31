from __future__ import annotations

from typing import Any, Dict, Iterable, List

from loguru import logger


class ForexActivationEngine:
    """Activates forex support across persona, universe, and data layers."""

    DEFAULT_FOREX_PAIRS = [
        "EUR/USD",
        "GBP/USD",
        "USD/JPY",
        "AUD/USD",
        "USD/CAD",
        "USD/CHF",
        "NZD/USD",
    ]

    SOROS_PERSONA = (
        "Focus on currency reflexivity, central bank policy, and macro-economic imbalances."
    )

    def activate(
        self,
        persona_engine: Any | None = None,
        universe_manager: Any | None = None,
        openbb_adapter: Any | None = None,
        forex_pairs: Iterable[str] | None = None,
    ) -> Dict[str, Any]:
        pairs = self._normalize_pairs(forex_pairs or self.DEFAULT_FOREX_PAIRS)
        status: Dict[str, Any] = {
            "soros_persona_enabled": False,
            "forex_pairs": pairs,
            "openbb_forex_status": {"available": False},
        }

        if persona_engine is not None:
            if hasattr(persona_engine, "register_persona"):
                persona_engine.register_persona("Soros", self.SOROS_PERSONA)
                status["soros_persona_enabled"] = True
            elif hasattr(persona_engine, "PERSONAS"):
                persona_engine.PERSONAS["Soros"] = self.SOROS_PERSONA
                status["soros_persona_enabled"] = True

        if universe_manager is not None:
            universe_manager.universe.setdefault("forex", [])
            for pair in pairs:
                if pair not in universe_manager.universe["forex"]:
                    universe_manager.universe["forex"].append(pair)

        if openbb_adapter is not None:
            try:
                status["openbb_forex_status"] = openbb_adapter.safe_get_market_data(pairs[0])
            except Exception as exc:
                status["openbb_forex_status"] = {"available": False, "error": str(exc)}

        logger.info(
            "Forex activation completed | soros_persona_enabled={} forex_pairs={}".format(
                status["soros_persona_enabled"], len(pairs)
            )
        )
        return status

    @staticmethod
    def _normalize_pairs(pairs: Iterable[str]) -> List[str]:
        unique: List[str] = []
        seen = set()
        for pair in pairs:
            token = str(pair or "").strip().upper()
            if not token:
                continue
            if "/" not in token and len(token) == 6 and token.isalpha():
                token = f"{token[:3]}/{token[3:]}"
            if token in seen:
                continue
            seen.add(token)
            unique.append(token)
        return unique

