"""
Institutional-style signal fusion:
- Regime-aware ensemble voting
- Bayesian confidence weighting
- Dynamic sizing multipliers
"""
from typing import Dict, Any, Tuple
import numpy as np


EDGE_DECISION_THRESHOLD = 0.35

REGIME_AGENT_WEIGHTS = {
    "trending": {
        "trend": 1.25,
        "mean_reversion": 0.75,
        "volatility": 1.00,
        "liquidity": 1.00,
        "sentiment": 0.95,
        "market_making": 0.90,
        "options": 0.85,
    },
    "volatile_trend": {
        "trend": 1.15,
        "mean_reversion": 0.85,
        "volatility": 1.25,
        "liquidity": 1.05,
        "sentiment": 0.90,
        "market_making": 0.90,
        "options": 1.00,
    },
    "ranging": {
        "trend": 0.75,
        "mean_reversion": 1.30,
        "volatility": 0.95,
        "liquidity": 1.10,
        "sentiment": 1.00,
        "market_making": 1.20,
        "options": 0.90,
    },
    "low_volatility": {
        "trend": 0.95,
        "mean_reversion": 1.15,
        "volatility": 0.70,
        "liquidity": 1.20,
        "sentiment": 1.00,
        "market_making": 1.25,
        "options": 0.85,
    },
    "panic": {
        "trend": 0.80,
        "mean_reversion": 1.10,
        "volatility": 1.30,
        "liquidity": 0.85,
        "sentiment": 0.80,
        "market_making": 0.70,
        "options": 1.20,
    },
    "unknown": {},
}


class QuantSignalFusion:
    def _base_weight(self, regime: str, agent_name: str) -> float:
        normalized_regime = str(regime or "unknown").strip().lower()
        normalized_regime = {
            "trend": "trending",
            "high_volatility": "volatile_trend",
            "range": "ranging",
        }.get(normalized_regime, normalized_regime)
        regime_weights = REGIME_AGENT_WEIGHTS.get(normalized_regime, REGIME_AGENT_WEIGHTS["unknown"])
        return float(regime_weights.get(agent_name, 1.0))

    @staticmethod
    def _normalize_signal(signal: str) -> str:
        token = str(signal or "HOLD").upper()
        if token in {"BUY", "BUY_VOL", "BUY_SPREAD", "FAVORABLE"}:
            return "BUY"
        if token in {"SELL", "SELL_VOL", "SELL_SPREAD", "AVOID"}:
            return "SELL"
        return "HOLD"

    @staticmethod
    def _bayesian_confidence(prior: float, agreement: float, edge: float) -> float:
        # Posterior-like confidence update with agreement and directional edge.
        likelihood = np.clip(0.50 + 0.35 * agreement + 0.15 * edge, 0.02, 0.98)
        denominator = likelihood * prior + (1.0 - likelihood) * (1.0 - prior)
        if denominator <= 1e-9:
            return float(prior)
        posterior = (likelihood * prior) / denominator
        return float(np.clip(posterior, 0.0, 1.0))

    def fuse(
        self,
        orchestrated_signals: Dict[str, Any],
        features: Dict[str, Any],
        regime: str,
    ) -> Dict[str, Any]:
        agent_signals = orchestrated_signals.get("agent_signals", {})
        if not agent_signals:
            return {
                "decision": "HOLD",
                "confidence": 0.0,
                "buy_score": 0.0,
                "sell_score": 0.0,
                "hold_score": 1.0,
                "agreement": 0.0,
                "sizing_multipliers": self._sizing_multipliers(features, regime, 0.0),
            }

        buy_score = 0.0
        sell_score = 0.0
        hold_score = 0.0
        votes = {"BUY": 0, "SELL": 0, "HOLD": 0}

        for name, result in agent_signals.items():
            side = self._normalize_signal(result.get("signal", "HOLD"))
            confidence = float(np.clip(result.get("confidence", 0.0), 0.0, 1.0))
            weight = self._base_weight(regime, name)
            weighted_conf = confidence * weight
            votes[side] += 1

            if side == "BUY":
                buy_score += weighted_conf
            elif side == "SELL":
                sell_score += weighted_conf
            else:
                hold_score += weighted_conf

        total_score = buy_score + sell_score + hold_score
        buy_norm = buy_score / total_score if total_score > 1e-9 else 0.0
        sell_norm = sell_score / total_score if total_score > 1e-9 else 0.0
        hold_norm = hold_score / total_score if total_score > 1e-9 else 1.0
        edge = buy_norm - sell_norm
        if total_score <= 1e-9:
            decision = "HOLD"
            raw_confidence = 0.0
        elif edge > EDGE_DECISION_THRESHOLD:
            decision = "BUY"
            raw_confidence = buy_norm
        elif edge < -EDGE_DECISION_THRESHOLD:
            decision = "SELL"
            raw_confidence = sell_norm
        else:
            decision = "HOLD"
            raw_confidence = hold_norm

        num_agents = max(len(agent_signals), 1)
        agreement = max(votes.values()) / num_agents
        directional_edge = abs(edge)
        bayes_confidence = self._bayesian_confidence(raw_confidence, agreement, directional_edge)
        sizing = self._sizing_multipliers(features, regime, bayes_confidence)

        return {
            "decision": decision,
            "confidence": bayes_confidence,
            "buy_score": float(buy_score),
            "sell_score": float(sell_score),
            "hold_score": float(hold_score),
            "edge": float(edge),
            "raw_confidence": float(raw_confidence),
            "agreement": float(agreement),
            "directional_edge": float(directional_edge),
            "votes": votes,
            "sizing_multipliers": sizing,
        }

    def _sizing_multipliers(self, features: Dict[str, Any], regime: str, confidence: float) -> Dict[str, float]:
        realized_vol = float(features.get("realized_volatility", 0.0))
        vol_multiplier = float(np.clip(1.0 - realized_vol, 0.40, 1.25))

        ofi = float(features.get("order_flow_imbalance", 0.0))
        microstructure_multiplier = float(np.clip(1.0 + 0.4 * abs(ofi), 0.80, 1.20))

        # Penalize size if cross-series behavior looks trendless/noisy (proxied by weak autocorr).
        autocorr = float(features.get("autocorr_1", 0.0))
        correlation_penalty = float(np.clip(1.0 - max(0.0, 0.2 - abs(autocorr)), 0.75, 1.0))

        regime_multiplier = {
            "trending": 1.10,
            "volatile_trend": 1.00,
            "ranging": 0.95,
            "low_volatility": 1.05,
            "panic": 0.70,
        }.get(regime, 1.0)

        confidence_multiplier = float(np.clip(0.60 + confidence, 0.60, 1.40))

        return {
            "volatility_multiplier": vol_multiplier,
            "microstructure_multiplier": microstructure_multiplier,
            "correlation_penalty": correlation_penalty,
            "regime_multiplier": float(regime_multiplier),
            "confidence_multiplier": confidence_multiplier,
            "combined_multiplier": float(
                vol_multiplier
                * microstructure_multiplier
                * correlation_penalty
                * regime_multiplier
                * confidence_multiplier
            ),
        }
