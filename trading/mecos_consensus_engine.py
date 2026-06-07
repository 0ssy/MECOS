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
            if edge > 0.0 and trend > -0.01:
                return {"signal": "BUY", "reasoning": "Value + positive trend alignment."}
            if edge < -0.1:
                return {"signal": "SELL", "reasoning": "Negative valuation edge."}
            return {"signal": base_decision if base_decision in {"BUY", "SELL"} else "HOLD", "reasoning": "No clear value advantage."}

        if name == "Simons":
            if momentum > 0.01 and volatility < 0.15:
                return {"signal": "BUY", "reasoning": "Momentum and volatility profile favorable."}
            if momentum < -0.01 and volatility < 0.15:
                return {"signal": "SELL", "reasoning": "Negative momentum with controlled volatility."}
            return {"signal": "HOLD", "reasoning": "Quant setup is neutral."}

        if name == "Dalio":
            if edge > 0 and regime not in {"panic"}:
                return {"signal": "BUY", "reasoning": "Macro regime supports risk-on exposure."}
            if regime == "panic" and edge < 0:
                return {"signal": "SELL", "reasoning": "Macro regime is risk-off."}
            return {"signal": "HOLD", "reasoning": "Macro allocation remains balanced."}

        if name == "Soros":
            # Soros trades reflexivity; strongest in FX and crypto momentum dislocations.
            if asset_type == "forex":
                if momentum > 0.01 or base_decision == "BUY":
                    return {"signal": "BUY", "reasoning": "FX reflexivity aligned."}
                if momentum < -0.01 or base_decision == "SELL":
                    return {"signal": "SELL", "reasoning": "FX reflexivity downside."}
            elif asset_type == "crypto":
                if momentum > 0.01 or base_decision == "BUY":
                    return {"signal": "BUY", "reasoning": "Crypto momentum reflexivity."}
                if momentum < -0.01 or base_decision == "SELL":
                    return {"signal": "SELL", "reasoning": "Crypto downside reflexivity."}
            else:
                if momentum > 0.015:
                    return {"signal": "BUY", "reasoning": "Reflexive upside pressure detected."}
                if momentum < -0.015:
                    return {"signal": "SELL", "reasoning": "Reflexive downside pressure detected."}
            return {"signal": "HOLD", "reasoning": "No reflexive dislocation detected."}

        if name == "Nakamoto":
            # Crypto specialist — trades momentum, volatility clustering, and on-chain signals
            vol_clustering = float(context.get("features", {}).get("volatility_clustering", 0.0) or 0.0)
            order_flow = float(context.get("features", {}).get("order_flow_imbalance", 0.0) or 0.0)
            if asset_type == "crypto":
                if momentum > 0.005 and vol_clustering > 0.5:
                    return {"signal": "BUY", "reasoning": "Crypto momentum with persistent volatility clustering."}
                if momentum < -0.005 and vol_clustering > 0.5:
                    return {"signal": "SELL", "reasoning": "Crypto downside momentum with clustering."}
                if order_flow > 0.1 and base_decision == "BUY":
                    return {"signal": "BUY", "reasoning": "Order flow imbalance supports crypto entry."}
                if order_flow < -0.1 and base_decision == "SELL":
                    return {"signal": "SELL", "reasoning": "Order flow imbalance supports crypto exit."}
                return {"signal": base_decision if base_decision in {"BUY", "SELL"} else "HOLD", "reasoning": "Crypto signal follows base."}
            return {"signal": "HOLD", "reasoning": "Nakamoto only trades crypto."}

        if name == "Wood":
            # Cathie Wood — disruptive tech and crypto, high conviction growth
            if asset_type in {"crypto", "equity"}:
                if momentum > 0.0 and edge > 0.0:
                    return {"signal": "BUY", "reasoning": "Disruptive asset with positive momentum."}
                if momentum < -0.02 and edge < -0.05:
                    return {"signal": "SELL", "reasoning": "Momentum breakdown in disruptive asset."}
                return {"signal": base_decision if base_decision in {"BUY", "SELL"} else "HOLD", "reasoning": "High conviction hold."}
            return {"signal": "HOLD", "reasoning": "Wood focuses on disruptive assets only."}

        return {"signal": "HOLD", "reasoning": "No clear persona edge."}

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












