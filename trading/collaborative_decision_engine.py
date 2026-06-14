"""
trading/collaborative_decision_engine.py
=========================================
Replaces the four-layer sequential decision chain:
    MetaOrchestrator → ConsensusEngine → TradingAgent → QuantSignalFusion

With one unified collaborative process where ALL participants — quantitative
agents (TrendAgent, MeanReversionAgent, etc.) AND investment personas
(Nakamoto, Buffett, Simons, etc.) — share the same full market context
simultaneously, contribute a signal + confidence + reasoning, and are
fused in a single weighted vote.

No more base_decision inheritance. No more sequential overrides.
No more HOLD bias from diluted confidence across abstaining agents.

Architecture:
    1. All agents run in parallel (asyncio.gather)
    2. All personas run synchronously on same features
    3. Signals are pooled and regime-weighted
    4. Single Bayesian fusion produces final decision
    5. Full reasoning trace attached for audit/RL feedback

The TradingAgent calls decide() once and gets one answer.
"""

import asyncio
import inspect
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from loguru import logger

from trading.config import TradingConfig


# Regime-aware weight multipliers per agent/persona type
REGIME_WEIGHTS: Dict[str, Dict[str, float]] = {
    "trending": {
        "trend": 1.40, "mean_reversion": 0.70, "volatility": 1.00,
        "order_flow": 1.10, "sentiment": 0.80, "market_making": 0.85,
        "options_pricing": 0.85, "liquidity_hunter": 1.00,
        "statistical_arbitrage": 0.90, "reinforcement_learning": 0.50,
        # Personas
        "Wood": 1.20, "Soros": 1.20, "Simons": 1.10,
        "Nakamoto": 1.10, "Buffett": 0.90, "Dalio": 0.95,
    },
    "ranging": {
        "trend": 0.70, "mean_reversion": 1.40, "volatility": 0.90,
        "order_flow": 1.10, "sentiment": 1.00, "market_making": 1.25,
        "options_pricing": 0.90, "liquidity_hunter": 1.10,
        "statistical_arbitrage": 1.10, "reinforcement_learning": 0.50,
        "Wood": 0.80, "Soros": 1.00, "Simons": 1.30,
        "Nakamoto": 0.90, "Buffett": 1.10, "Dalio": 1.00,
    },
    "low_volatility": {
        "trend": 0.95, "mean_reversion": 1.20, "volatility": 0.70,
        "order_flow": 1.15, "sentiment": 1.00, "market_making": 1.20,
        "options_pricing": 0.85, "liquidity_hunter": 1.20,
        "statistical_arbitrage": 1.00, "reinforcement_learning": 0.50,
        "Wood": 1.00, "Soros": 0.95, "Simons": 1.15,
        "Nakamoto": 0.95, "Buffett": 1.05, "Dalio": 1.05,
    },
    "volatile_trend": {
        "trend": 1.15, "mean_reversion": 0.85, "volatility": 1.30,
        "order_flow": 1.05, "sentiment": 0.85, "market_making": 0.85,
        "options_pricing": 1.05, "liquidity_hunter": 1.00,
        "statistical_arbitrage": 0.85, "reinforcement_learning": 0.50,
        "Wood": 1.10, "Soros": 1.15, "Simons": 1.05,
        "Nakamoto": 1.10, "Buffett": 0.85, "Dalio": 1.10,
    },
    "panic": {
        "trend": 0.80, "mean_reversion": 1.10, "volatility": 1.30,
        "order_flow": 0.90, "sentiment": 0.75, "market_making": 0.70,
        "options_pricing": 1.20, "liquidity_hunter": 0.90,
        "statistical_arbitrage": 0.80, "reinforcement_learning": 0.40,
        "Wood": 0.80, "Soros": 1.20, "Simons": 1.10,
        "Nakamoto": 0.85, "Buffett": 0.90, "Dalio": 1.25,
    },
}

# Base weights from config (used when regime not in REGIME_WEIGHTS)
BASE_AGENT_WEIGHTS: Dict[str, float] = TradingConfig.SIGNAL_WEIGHTS

# Persona base weights — balanced so personas don't dominate quant agents
BASE_PERSONA_WEIGHTS: Dict[str, float] = {
    "Nakamoto": 0.80,
    "Wood":     0.75,
    "Buffett":  0.75,
    "Simons":   0.85,
    "Dalio":    0.75,
    "Soros":    0.75,
}

# Minimum weighted directional score to issue BUY or SELL
# Lower than old MIN_CONFIDENCE (0.30) because we no longer dilute
# by abstaining-agent weight — only active signal weights count.
MIN_DIRECTIONAL_SCORE = 0.18


class CollaborativeDecisionEngine:
    """
    Single unified decision engine that replaces the four-layer chain.

    Usage:
        engine = CollaborativeDecisionEngine(agents, personas)
        result = await engine.decide(symbol, data, features, regime, physics)
    """

    def __init__(
        self,
        agents: Dict[str, Any],
        personas: Dict[str, Any],
    ):
        """
        agents:  dict of name → agent instance (must have .analyze())
        personas: dict of name → persona instance (must have .analyze_persona())
                  OR a ConsensusEngine-compatible personas dict (name → description)
                  In that case, pass the ConsensusEngine's _persona_analysis method
                  as persona_analyzer.
        """
        self.agents  = agents
        self.personas = personas
        logger.info(
            f"CollaborativeDecisionEngine initialized | "
            f"{len(agents)} agents, {len(personas)} personas"
        )

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    async def decide(
        self,
        symbol: str,
        data: Any,
        features: Dict[str, Any],
        regime: str,
        physics: Optional[Dict[str, Any]] = None,
        asset_type: str = "equity",
        news_score: float = 0.0,
        macro_snapshot: Optional[Dict[str, Any]] = None,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Run all agents and personas in parallel on the same shared context.
        Return a single fused decision with full reasoning trace.
        """
        physics = physics or {}
        macro_snapshot = macro_snapshot or {}
        extra_context = extra_context or {}

        # Shared context — everyone sees the same thing
        shared_context = {
            "symbol":        symbol,
            "asset_type":    asset_type,
            "regime":        regime,
            "features":      features,
            "news_score":    news_score,
            "macro":         macro_snapshot,
            **extra_context,
        }

        # Run quant agents and personas concurrently
        agent_task   = asyncio.create_task(
            self._run_all_agents(data, features, physics, symbol)
        )
        persona_task = asyncio.create_task(
            self._run_all_personas(shared_context)
        )

        agent_signals, persona_signals = await asyncio.gather(
            agent_task, persona_task, return_exceptions=False
        )

        # Pool all signals together
        all_signals: Dict[str, Dict[str, Any]] = {
            **{f"agent:{k}": v for k, v in agent_signals.items()},
            **{f"persona:{k}": v for k, v in persona_signals.items()},
        }

        # Fuse into one decision
        result = self._fuse(all_signals, regime, features)
        result["symbol"]         = symbol
        result["regime"]         = regime
        result["agent_signals"]  = agent_signals
        result["persona_signals"] = persona_signals
        result["all_signals"]    = all_signals

        logger.info(
            f"[Collaborative] {symbol} → {result['decision']} "
            f"conf={result['confidence']:.3f} "
            f"buy_w={result['buy_weight']:.3f} sell_w={result['sell_weight']:.3f} "
            f"({result['buy_votes']}B/{result['sell_votes']}S/{result['hold_votes']}H "
            f"from {result['total_participants']} participants)"
        )
        return result

    # ------------------------------------------------------------------ #
    #  Agent runner                                                        #
    # ------------------------------------------------------------------ #

    async def _run_all_agents(
        self,
        data: Any,
        features: Dict[str, Any],
        physics: Dict[str, Any],
        symbol: str,
    ) -> Dict[str, Dict[str, Any]]:
        tasks = []
        names = []
        for name, agent in self.agents.items():
            if not hasattr(agent, "analyze"):
                continue
            tasks.append(self._run_agent(name, agent, data, features, physics, symbol))
            names.append(name)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        out = {}
        for name, res in zip(names, results):
            if isinstance(res, Exception):
                logger.warning(f"Agent {name} failed: {res}")
                out[name] = {"signal": "HOLD", "confidence": 0.0, "error": str(res)}
            else:
                out[name] = res
        return out

    async def _run_agent(
        self,
        name: str,
        agent: Any,
        data: Any,
        features: Dict[str, Any],
        physics: Dict[str, Any],
        symbol: str,
    ) -> Dict[str, Any]:
        try:
            sig    = inspect.signature(agent.analyze)
            params = list(sig.parameters.keys())
            kwargs = {}
            if "symbol" in sig.parameters and symbol:
                kwargs["symbol"] = symbol
            if len(params) >= 3:
                result = await agent.analyze(data, features, physics, **kwargs)
            elif len(params) == 2:
                second = params[1].lower()
                result = await agent.analyze(
                    data, features if second in {"features", "feature", "context"} else {}, **kwargs
                )
            else:
                result = await agent.analyze(data, **kwargs)
            return result if isinstance(result, dict) else {"signal": "HOLD", "confidence": 0.0}
        except Exception as exc:
            logger.error(f"Agent {name} error: {exc}")
            return {"signal": "HOLD", "confidence": 0.0, "error": str(exc)}

    # ------------------------------------------------------------------ #
    #  Persona runner                                                      #
    # ------------------------------------------------------------------ #

    async def _run_all_personas(
        self, context: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """Run persona analysis — sync but wrapped so it can be gathered."""
        out = {}
        for name, persona in self.personas.items():
            try:
                if callable(persona):
                    # persona is a bound method (e.g. ConsensusEngine._persona_analysis)
                    result = persona(name, context)
                elif hasattr(persona, "analyze_persona"):
                    result = await persona.analyze_persona(context)
                else:
                    result = {"signal": "HOLD", "confidence": 0.2,
                              "reasoning": "Persona has no callable interface."}
                out[name] = result if isinstance(result, dict) else {
                    "signal": "HOLD", "confidence": 0.2
                }
            except Exception as exc:
                logger.warning(f"Persona {name} failed: {exc}")
                out[name] = {"signal": "HOLD", "confidence": 0.2, "error": str(exc)}
        return out

    # ------------------------------------------------------------------ #
    #  Unified fusion                                                       #
    # ------------------------------------------------------------------ #

    def _fuse(
        self,
        all_signals: Dict[str, Dict[str, Any]],
        regime: str,
        features: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Weighted fusion of all signals.
        Only ACTIVE (non-HOLD) signals contribute to buy/sell weight.
        HOLD signals contribute to hold weight only.
        This prevents abstaining agents from diluting the directional score.
        """
        regime_norm = str(regime or "unknown").lower()
        regime_wts  = REGIME_WEIGHTS.get(regime_norm, {})

        buy_weight  = 0.0
        sell_weight = 0.0
        hold_weight = 0.0
        buy_votes   = 0
        sell_votes  = 0
        hold_votes  = 0
        reasoning   = {}

        for key, signal_data in all_signals.items():
            # Resolve participant name and type
            if key.startswith("agent:"):
                pname = key[6:]
                ptype = "agent"
                base_w = BASE_AGENT_WEIGHTS.get(pname.split(":")[0], 1.0)
            elif key.startswith("persona:"):
                pname = key[8:]
                ptype = "persona"
                base_w = BASE_PERSONA_WEIGHTS.get(pname, 0.75)
            else:
                pname = key
                ptype = "unknown"
                base_w = 1.0

            # Apply regime multiplier
            regime_mult = regime_wts.get(pname, 1.0)
            weight = base_w * regime_mult

            sig  = str(signal_data.get("signal", "HOLD")).upper()
            # Normalise signal aliases
            if sig in {"BUY_VOL", "BUY_SPREAD", "FAVORABLE"}:
                sig = "BUY"
            elif sig in {"SELL_VOL", "SELL_SPREAD", "AVOID", "EXIT"}:
                sig = "SELL"
            elif sig not in {"BUY", "SELL"}:
                sig = "HOLD"

            conf = float(np.clip(signal_data.get("confidence", 0.0), 0.0, 1.0))
            rsn  = signal_data.get("reasoning", signal_data.get("reason", ""))

            reasoning[key] = {
                "signal": sig, "confidence": conf,
                "weight": round(weight, 4), "reasoning": rsn,
                "type": ptype,
            }

            weighted_conf = conf * weight
            if sig == "BUY":
                buy_weight  += weighted_conf
                buy_votes   += 1
            elif sig == "SELL":
                sell_weight += weighted_conf
                sell_votes  += 1
            else:
                hold_weight += weighted_conf
                hold_votes  += 1

        total_participants = buy_votes + sell_votes + hold_votes
        active_weight = buy_weight + sell_weight
        total_weight  = active_weight + hold_weight + 1e-9

        # Directional scores — normalised only over active weight when possible
        active_norm = active_weight + 1e-9
        buy_score   = buy_weight  / active_norm
        sell_score  = sell_weight / active_norm

        # Net directional edge
        edge = buy_score - sell_score

        # Decision: use active-weight normalised score to avoid dilution
        if edge > MIN_DIRECTIONAL_SCORE and buy_weight / total_weight >= 0.12:
            decision    = "BUY"
            confidence  = float(np.clip(buy_weight / total_weight, 0.0, 1.0))
        elif edge < -MIN_DIRECTIONAL_SCORE and sell_weight / total_weight >= 0.12:
            decision    = "SELL"
            confidence  = float(np.clip(sell_weight / total_weight, 0.0, 1.0))
        else:
            decision    = "HOLD"
            confidence  = float(np.clip(hold_weight / total_weight, 0.0, 1.0))

        # Bayesian confidence update using agreement
        if total_participants > 0:
            majority_votes = max(buy_votes, sell_votes, hold_votes)
            agreement = majority_votes / total_participants
            confidence = float(np.clip(
                0.5 * confidence + 0.3 * agreement + 0.2 * abs(edge),
                0.0, 1.0
            ))

        return {
            "decision":           decision,
            "confidence":         round(confidence, 4),
            "edge":               round(edge, 4),
            "buy_weight":         round(buy_weight, 4),
            "sell_weight":        round(sell_weight, 4),
            "hold_weight":        round(hold_weight, 4),
            "buy_votes":          buy_votes,
            "sell_votes":         sell_votes,
            "hold_votes":         hold_votes,
            "total_participants": total_participants,
            "reasoning":          reasoning,
            # Legacy keys so existing code reading these fields doesn't break
            "final_decision":     decision,
            "buy_score":          round(buy_weight, 4),
            "sell_score":         round(sell_weight, 4),
            "agent_signals":      {},   # filled by decide()
        }
