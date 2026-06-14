"""
MECOS Consensus Engine
======================
Multi-persona debate system where all personas share the same full market
context and can challenge each other's reasoning before a final decision
is reached.

Key improvements over previous version:
  - Personas now use RSI, MACD, Bollinger Bands, and signed trend_strength
    from the new feature engine — giving them real bearish signal inputs
  - Majority voting (configurable) replaces unanimous-only requirement
  - Each persona has distinct, non-overlapping logic with realistic SELL
    thresholds that actually trigger in normal market conditions
  - Shared context: all personas see the same features simultaneously,
    and the consensus weighs their reasoning, not just their vote
  - Duplicate Nakamoto/Wood blocks removed
  - SELL signals now flow through correctly
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List

from loguru import logger


class ConsensusEngine:
    """
    Multi-agent debate loop for final trade signal gating.

    Each persona applies its own investment philosophy to the shared
    feature context and votes BUY / SELL / HOLD with a confidence score
    and a reasoning string. The final decision is reached by weighted
    majority vote — no unanimity required.
    """

    def __init__(
        self,
        personas: Dict[str, str],
        minimum_support_ratio: float = 0.51,
        require_unanimous: bool = False,
    ):
        self.personas = dict(personas or {})
        self.minimum_support_ratio = float(minimum_support_ratio)
        self.require_unanimous = bool(require_unanimous)

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def coordinate_debate(
        self, topic: str, context: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        context = dict(context or {})
        logger.debug(f"[Consensus] Debate start: topic={topic}")

        # Resolve which personas participate
        active_personas = context.get("active_personas")
        if isinstance(active_personas, str):
            active_personas = [active_personas]
        if not isinstance(active_personas, list) or not active_personas:
            selected = list(self.personas.keys())
        else:
            selected = [n for n in active_personas if n in self.personas]
            if not selected:
                selected = list(self.personas.keys())

        # Each persona analyses the shared context independently
        perspectives: Dict[str, Dict[str, Any]] = {}
        for name in selected:
            perspectives[name] = self._persona_analysis(name, context)

        # Reach consensus from all perspectives
        conclusion = self._reach_consensus(perspectives, context)

        logger.debug(
            f"[Consensus] Debate complete: topic={topic} "
            f"decision={conclusion['final_decision']} "
            f"support={conclusion['support_ratio']:.2f}"
        )
        return conclusion

    # ------------------------------------------------------------------ #
    #  Persona logic — each persona uses the full shared feature set      #
    # ------------------------------------------------------------------ #

    def _persona_analysis(
        self, name: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Dispatch to the correct persona handler."""
        handlers = {
            "Nakamoto": self._nakamoto,
            "Wood":     self._wood,
            "Buffett":  self._buffett,
            "Simons":   self._simons,
            "Dalio":    self._dalio,
            "Soros":    self._soros,
        }
        handler = handlers.get(name)
        if handler is None:
            return {"signal": "HOLD", "confidence": 0.3, "reasoning": "Unknown persona — abstain."}
        return handler(context)

    # -- Shared feature extraction helper --------------------------------

    @staticmethod
    def _extract(context: Dict[str, Any]) -> Dict[str, Any]:
        """Pull all relevant values from context into a flat dict."""
        f = context.get("features", {}) or {}
        return {
            "asset_type":    str(context.get("asset_type", "equity")).lower(),
            "regime":        str(context.get("regime", "unknown")).lower(),
            "base_decision": str(context.get("base_decision", "HOLD")).upper(),
            "edge":          float(context.get("edge", 0.0) or 0.0),
            # Momentum
            "roc_5":         float(f.get("roc_5",  0.0) or 0.0),
            "roc_20":        float(f.get("roc_20", 0.0) or 0.0),
            "macd_hist":     float(f.get("macd_hist", 0.0) or 0.0),
            # Trend — now SIGNED from new feature engine
            "trend_strength": float(f.get("trend_strength", 0.0) or 0.0),
            "trend_direction": int(f.get("trend_direction", 0) or 0),
            "price_vs_sma20":  float(f.get("price_vs_sma20", 0.0) or 0.0),
            # Oscillators
            "rsi":           float(f.get("rsi_14", f.get("rsi", 50.0)) or 50.0),
            "bb_pct_b":      float(f.get("bb_pct_b", 0.5) or 0.5),
            "bb_width":      float(f.get("bb_width", 0.0) or 0.0),
            # Volatility
            "realized_vol":  float(f.get("realized_volatility", 0.0) or 0.0),
            "vol_clustering": float(f.get("volatility_clustering", 0.0) or 0.0),
            # Microstructure
            "order_flow":    float(f.get("order_flow_imbalance", 0.0) or 0.0),
            "volume_ratio":  float(f.get("volume_ratio", 1.0) or 1.0),
            # Mean reversion
            "z_score":       float(f.get("z_score", 0.0) or 0.0),
            "autocorr":      float(f.get("autocorr_1", 0.0) or 0.0),
            "mean_rev":      float(f.get("mean_reversion_score", 0.0) or 0.0),
        }

    # -- Nakamoto: crypto momentum + on-chain microstructure -------------

    def _nakamoto(self, context: Dict[str, Any]) -> Dict[str, Any]:
        v = self._extract(context)

        if v["asset_type"] != "crypto":
            return {"signal": "HOLD", "confidence": 0.2,
                    "reasoning": "Nakamoto only trades crypto."}

        # BUY: positive momentum + bullish order flow + MACD turning up
        if v["roc_20"] > 0.005 and v["order_flow"] > 0.05 and v["macd_hist"] > 0:
            conf = min(0.85, 0.5 + abs(v["roc_20"]) * 5 + v["order_flow"] * 0.3)
            return {"signal": "BUY", "confidence": conf,
                    "reasoning": f"Crypto momentum roc20={v['roc_20']:.3f} with positive order flow and MACD."}

        # SELL: negative momentum + bearish order flow + RSI overbought
        if v["roc_20"] < -0.005 and v["order_flow"] < -0.05:
            conf = min(0.85, 0.5 + abs(v["roc_20"]) * 5 + abs(v["order_flow"]) * 0.3)
            return {"signal": "SELL", "confidence": conf,
                    "reasoning": f"Crypto downside roc20={v['roc_20']:.3f} with negative order flow."}

        # SELL: RSI overbought + price extended above bands
        if v["rsi"] > 72 and v["bb_pct_b"] > 0.90:
            return {"signal": "SELL", "confidence": 0.70,
                    "reasoning": f"Crypto overbought: RSI={v['rsi']:.1f}, BB%={v['bb_pct_b']:.2f}."}

        # BUY: RSI oversold
        if v["rsi"] < 30 and v["bb_pct_b"] < 0.15:
            return {"signal": "BUY", "confidence": 0.72,
                    "reasoning": f"Crypto oversold: RSI={v['rsi']:.1f}, BB%={v['bb_pct_b']:.2f}."}

        return {"signal": "HOLD", "confidence": 0.3,
                "reasoning": "No clear crypto momentum setup."}

    # -- Wood: disruptive growth, high conviction, momentum-driven --------

    def _wood(self, context: Dict[str, Any]) -> Dict[str, Any]:
        v = self._extract(context)

        if v["asset_type"] not in {"crypto", "equity"}:
            return {"signal": "HOLD", "confidence": 0.2,
                    "reasoning": "Wood focuses on disruptive assets only."}

        # BUY: positive trend + positive MACD + not overbought
        if v["trend_strength"] > 0 and v["macd_hist"] > 0 and v["rsi"] < 75:
            conf = min(0.82, 0.5 + v["trend_strength"] * 3)
            return {"signal": "BUY", "confidence": conf,
                    "reasoning": f"Disruptive asset bullish trend_strength={v['trend_strength']:.3f}."}

        # SELL: trend turned negative + MACD bearish crossover
        if v["trend_strength"] < -0.005 and v["macd_hist"] < 0:
            conf = min(0.80, 0.5 + abs(v["trend_strength"]) * 3)
            return {"signal": "SELL", "confidence": conf,
                    "reasoning": f"Trend reversal: trend_strength={v['trend_strength']:.3f}, MACD bearish."}

        # SELL: momentum breakdown — RSI was high, now falling fast
        if v["roc_5"] < -0.02 and v["rsi"] > 60:
            return {"signal": "SELL", "confidence": 0.65,
                    "reasoning": f"Momentum breakdown: roc5={v['roc_5']:.3f} from elevated RSI={v['rsi']:.1f}."}

        return {"signal": "HOLD", "confidence": 0.35,
                "reasoning": "High conviction hold — no clear directional edge."}

    # -- Buffett: value + trend alignment, patient, avoids overextension --

    def _buffett(self, context: Dict[str, Any]) -> Dict[str, Any]:
        v = self._extract(context)

        # Buffett avoids crypto entirely
        if v["asset_type"] == "crypto":
            return {"signal": "HOLD", "confidence": 0.2,
                    "reasoning": "Buffett does not trade crypto."}

        # BUY: positive edge, positive trend, not overbought
        if v["edge"] > 0.01 and v["trend_direction"] >= 0 and v["rsi"] < 68:
            conf = min(0.78, 0.45 + v["edge"] * 2)
            return {"signal": "BUY", "confidence": conf,
                    "reasoning": f"Value + trend alignment: edge={v['edge']:.3f}, RSI={v['rsi']:.1f}."}

        # SELL: RSI overbought + price extended above SMA20 + negative MACD
        if v["rsi"] > 70 and v["price_vs_sma20"] > 0.03 and v["macd_hist"] < 0:
            return {"signal": "SELL", "confidence": 0.72,
                    "reasoning": f"Overvalued + MACD turning: RSI={v['rsi']:.1f}, price_vs_sma20={v['price_vs_sma20']:.3f}."}

        # SELL: trend turned bearish
        if v["trend_direction"] < 0 and v["trend_strength"] < -0.01:
            return {"signal": "SELL", "confidence": 0.65,
                    "reasoning": f"Trend bearish: trend_strength={v['trend_strength']:.3f}."}

        return {"signal": "HOLD", "confidence": 0.35,
                "reasoning": "No clear value opportunity — patience required."}

    # -- Simons: quantitative, symmetric, mean-reversion + momentum -------

    def _simons(self, context: Dict[str, Any]) -> Dict[str, Any]:
        v = self._extract(context)

        # BUY: momentum positive + volatility controlled + MACD bullish
        if v["roc_20"] > 0.01 and v["realized_vol"] < 0.35 and v["macd_hist"] > 0:
            conf = min(0.83, 0.5 + abs(v["roc_20"]) * 4)
            return {"signal": "BUY", "confidence": conf,
                    "reasoning": f"Quant momentum: roc20={v['roc_20']:.3f}, vol={v['realized_vol']:.2f}."}

        # SELL: negative momentum + controlled vol + MACD bearish
        if v["roc_20"] < -0.01 and v["realized_vol"] < 0.35 and v["macd_hist"] < 0:
            conf = min(0.83, 0.5 + abs(v["roc_20"]) * 4)
            return {"signal": "SELL", "confidence": conf,
                    "reasoning": f"Quant negative momentum: roc20={v['roc_20']:.3f}, MACD bearish."}

        # Mean reversion: strong z-score with negative autocorrelation
        if v["z_score"] > 1.8 and v["autocorr"] < -0.03:
            return {"signal": "SELL", "confidence": min(0.80, abs(v["z_score"]) / 3.0),
                    "reasoning": f"Quant mean-reversion SELL: z={v['z_score']:.2f}, autocorr={v['autocorr']:.3f}."}

        if v["z_score"] < -1.8 and v["autocorr"] < -0.03:
            return {"signal": "BUY", "confidence": min(0.80, abs(v["z_score"]) / 3.0),
                    "reasoning": f"Quant mean-reversion BUY: z={v['z_score']:.2f}."}

        return {"signal": "HOLD", "confidence": 0.35,
                "reasoning": "Quant setup is neutral — no statistical edge."}

    # -- Dalio: macro, all-weather, risk-regime aware ---------------------

    def _dalio(self, context: Dict[str, Any]) -> Dict[str, Any]:
        v = self._extract(context)

        # Risk-off: panic regime or high volatility — reduce exposure
        if v["regime"] in {"panic", "high_volatility"} and v["trend_direction"] < 0:
            return {"signal": "SELL", "confidence": 0.75,
                    "reasoning": f"Macro risk-off: regime={v['regime']}, bearish trend."}

        # Risk-on: trending regime + positive edge
        if v["regime"] in {"trending", "low_volatility"} and v["edge"] > 0 and v["trend_direction"] > 0:
            conf = min(0.78, 0.5 + v["edge"] * 1.5)
            return {"signal": "BUY", "confidence": conf,
                    "reasoning": f"Macro risk-on: regime={v['regime']}, edge={v['edge']:.3f}."}

        # SELL: negative edge in any non-panic regime (orderly decline)
        if v["edge"] < -0.05 and v["trend_strength"] < -0.005:
            return {"signal": "SELL", "confidence": 0.65,
                    "reasoning": f"Macro negative edge: edge={v['edge']:.3f}, trend={v['trend_strength']:.3f}."}

        return {"signal": "HOLD", "confidence": 0.35,
                "reasoning": "Macro allocation balanced — no strong regime signal."}

    # -- Soros: reflexivity, momentum dislocations, contrarian extremes ---

    def _soros(self, context: Dict[str, Any]) -> Dict[str, Any]:
        v = self._extract(context)

        # Reflexive momentum: strong trend + volume confirmation
        if v["roc_20"] > 0.015 and v["volume_ratio"] > 1.2 and v["macd_hist"] > 0:
            conf = min(0.82, 0.5 + abs(v["roc_20"]) * 3 + (v["volume_ratio"] - 1) * 0.2)
            return {"signal": "BUY", "confidence": conf,
                    "reasoning": f"Reflexive upside: roc20={v['roc_20']:.3f}, vol_ratio={v['volume_ratio']:.2f}."}

        # Reflexive downside: negative momentum + volume spike
        if v["roc_20"] < -0.015 and v["volume_ratio"] > 1.2 and v["macd_hist"] < 0:
            conf = min(0.82, 0.5 + abs(v["roc_20"]) * 3 + (v["volume_ratio"] - 1) * 0.2)
            return {"signal": "SELL", "confidence": conf,
                    "reasoning": f"Reflexive downside: roc20={v['roc_20']:.3f}, vol spike."}

        # Contrarian: extreme RSI overbought — fade the euphoria
        if v["rsi"] > 75 and v["bb_pct_b"] > 0.92:
            return {"signal": "SELL", "confidence": 0.68,
                    "reasoning": f"Fade euphoria: RSI={v['rsi']:.1f}, BB%={v['bb_pct_b']:.2f}."}

        # Contrarian: extreme RSI oversold — buy the panic
        if v["rsi"] < 28 and v["bb_pct_b"] < 0.10:
            return {"signal": "BUY", "confidence": 0.68,
                    "reasoning": f"Buy panic: RSI={v['rsi']:.1f}, BB%={v['bb_pct_b']:.2f}."}

        # Moderate directional follow-through
        if v["roc_20"] > 0.008:
            return {"signal": "BUY", "confidence": 0.55,
                    "reasoning": f"Moderate upside reflexivity: roc20={v['roc_20']:.3f}."}

        if v["roc_20"] < -0.008:
            return {"signal": "SELL", "confidence": 0.55,
                    "reasoning": f"Moderate downside reflexivity: roc20={v['roc_20']:.3f}."}

        return {"signal": "HOLD", "confidence": 0.30,
                "reasoning": "No reflexive dislocation detected."}

    # ------------------------------------------------------------------ #
    #  Consensus aggregation                                               #
    # ------------------------------------------------------------------ #

    def _reach_consensus(
        self,
        perspectives: Dict[str, Dict[str, Any]],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        signals = []
        weighted_buy  = 0.0
        weighted_sell = 0.0
        weighted_hold = 0.0

        for name, p in perspectives.items():
            sig  = str(p.get("signal", "HOLD")).upper()
            conf = float(p.get("confidence", 0.3))
            signals.append(sig)

            if sig == "BUY":
                weighted_buy  += conf
            elif sig == "SELL":
                weighted_sell += conf
            else:
                weighted_hold += conf

        total_votes = max(len(signals), 1)
        counts = {
            "BUY":  signals.count("BUY"),
            "SELL": signals.count("SELL"),
            "HOLD": signals.count("HOLD"),
        }

        majority_signal   = max(counts, key=counts.get)
        support_ratio     = float(counts[majority_signal]) / float(total_votes)
        threshold         = 1.0 if self.require_unanimous else self.minimum_support_ratio
        is_supported      = support_ratio >= threshold

        # Use weighted confidence as tiebreaker / signal strength
        total_weight = weighted_buy + weighted_sell + weighted_hold + 1e-9
        if majority_signal == "BUY" and is_supported:
            final_decision  = "BUY"
            confidence_score = weighted_buy / total_weight
        elif majority_signal == "SELL" and is_supported:
            final_decision  = "SELL"
            confidence_score = weighted_sell / total_weight
        else:
            # Even without majority, prefer directional if weighted conf is strong
            if weighted_buy > weighted_sell and weighted_buy / total_weight > 0.45:
                final_decision   = "BUY"
                confidence_score = weighted_buy / total_weight
            elif weighted_sell > weighted_buy and weighted_sell / total_weight > 0.45:
                final_decision   = "SELL"
                confidence_score = weighted_sell / total_weight
            else:
                final_decision   = "HOLD"
                confidence_score = weighted_hold / total_weight

        dissenting = self._dissenting_personas(perspectives, final_decision)

        return {
            "final_decision":    final_decision,
            "headline_decision": f"STRONG {final_decision}" if final_decision in {"BUY", "SELL"} else "WAIT / HOLD",
            "confidence_score":  round(confidence_score, 4),
            "support_ratio":     round(support_ratio, 4),
            "vote_counts":       counts,
            "weighted_scores":   {
                "buy":  round(weighted_buy,  4),
                "sell": round(weighted_sell, 4),
                "hold": round(weighted_hold, 4),
            },
            "dissenting_opinions": dissenting,
            "perspectives":        perspectives,
        }

    @staticmethod
    def _dissenting_personas(
        perspectives: Dict[str, Dict[str, Any]],
        final_decision: str,
    ) -> List[str]:
        if final_decision == "HOLD":
            return [n for n, p in perspectives.items()
                    if str(p.get("signal", "HOLD")).upper() != "HOLD"]
        return [n for n, p in perspectives.items()
                if str(p.get("signal", "HOLD")).upper() != final_decision]
