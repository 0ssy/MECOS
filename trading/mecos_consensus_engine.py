from __future__ import annotations

from typing import Any, Dict, Iterable

from loguru import logger


class ConsensusEngine:
    """Multi-agent debate loop for final trade signal gating."""

    def __init__(
        self,
        personas: Dict[str, str],
        minimum_support_ratio: float = 1.0,
        require_unanimous: bool = True,
    ):
        self.personas = dict(personas or {})
        self.minimum_support_ratio = float(minimum_support_ratio)
        self.require_unanimous = bool(require_unanimous)

    def coordinate_debate(self, topic: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        context = dict(context or {})
        logger.debug(f"[Consensus] Debate start: topic={topic}")

        active_personas = context.get("active_personas")
        if isinstance(active_personas, str):
            active_personas = [active_personas]
        if not isinstance(active_personas, list) or not active_personas:
            selected = list(self.personas.keys())
        else:
            selected = [name for name in active_personas if name in self.personas]
            if not selected:
                selected = list(self.personas.keys())

        perspectives: Dict[str, Dict[str, str]] = {}
        for name in selected:
            perspectives[name] = self._simulate_persona_analysis(name, context)

        conclusion = self._reach_consensus(perspectives)
        logger.debug(
            f"[Consensus] Debate complete: topic={topic} decision={conclusion['final_decision']} "
            f"support={conclusion['support_ratio']:.2f}"
        )
        return conclusion

    def _simulate_persona_analysis(self, name: str, context: Dict[str, Any]) -> Dict[str, str]:
        asset_type = str(context.get("asset_type", "equity")).strip().lower()
        regime = str(context.get("regime", "unknown")).strip().lower()
        base_decision = str(context.get("base_decision", "HOLD")).strip().upper()
        edge = float(context.get("edge", 0.0) or 0.0)
        momentum = float(context.get("features", {}).get("roc_20", 0.0) or 0.0)
        trend = float(context.get("features", {}).get("trend_strength", 0.0) or 0.0)
        volatility = float(context.get("features", {}).get("realized_volatility", 0.0) or 0.0)

        if name == "Buffett":
            if asset_type == "equity" and edge > 0.0 and trend > -0.01:
                return {"signal": "BUY", "reasoning": "Value + positive trend alignment."}
            if asset_type == "equity" and edge < -0.1:
                return {"signal": "SELL", "reasoning": "Negative valuation edge."}
            return {"signal": "HOLD", "reasoning": "No equity value advantage."}

        if name == "Simons":
            if momentum > 0.015 and volatility < 0.06:
                return {"signal": "BUY", "reasoning": "Momentum and volatility profile favorable."}
            if momentum < -0.015 and volatility < 0.06:
                return {"signal": "SELL", "reasoning": "Negative momentum with controlled volatility."}
            return {"signal": "HOLD", "reasoning": "Quant setup is neutral."}

        if name == "Dalio":
            if regime in {"trending", "volatile_trend"} and edge > 0:
                return {"signal": "BUY", "reasoning": "Macro regime supports risk-on exposure."}
            if regime == "panic" and edge < 0:
                return {"signal": "SELL", "reasoning": "Macro regime is risk-off."}
            return {"signal": "HOLD", "reasoning": "Macro allocation remains balanced."}

        if name == "Soros":
            if asset_type == "forex":
                if momentum > 0.01 or base_decision == "BUY":
                    return {"signal": "BUY", "reasoning": "FX reflexivity and directional pressure are aligned."}
                if momentum < -0.01 or base_decision == "SELL":
                    return {"signal": "SELL", "reasoning": "FX reflexivity points to downside momentum."}
            return {"signal": "HOLD", "reasoning": "No reflexive dislocation detected."}

        return {"signal": base_decision if base_decision in {"BUY", "SELL"} else "HOLD", "reasoning": "Fallback"}

    def _reach_consensus(self, perspectives: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
        signals = [str(p.get("signal", "HOLD")).upper() for p in perspectives.values()]
        total_votes = max(1, len(signals))
        counts = {
            "BUY": signals.count("BUY"),
            "SELL": signals.count("SELL"),
            "HOLD": signals.count("HOLD"),
        }

        majority_signal = max(counts, key=counts.get)
        support_ratio = float(counts[majority_signal]) / float(total_votes)
        is_supported = support_ratio >= self.minimum_support_ratio
        if self.require_unanimous:
            is_supported = support_ratio >= 1.0

        if majority_signal in {"BUY", "SELL"} and is_supported:
            final_decision = majority_signal
        else:
            final_decision = "HOLD"

        dissenting = self._dissenting_personas(perspectives, final_decision)
        return {
            "final_decision": final_decision,
            "headline_decision": f"STRONG {final_decision}" if final_decision in {"BUY", "SELL"} else "WAIT / HOLD",
            "confidence_score": round(support_ratio, 4),
            "support_ratio": round(support_ratio, 4),
            "vote_counts": counts,
            "dissenting_opinions": dissenting,
            "perspectives": perspectives,
        }

    @staticmethod
    def _dissenting_personas(
        perspectives: Dict[str, Dict[str, str]],
        final_decision: str,
    ) -> Iterable[str]:
        if final_decision == "HOLD":
            return [name for name, p in perspectives.items() if str(p.get("signal", "HOLD")).upper() != "HOLD"]
        return [name for name, p in perspectives.items() if str(p.get("signal", "HOLD")).upper() != final_decision]

