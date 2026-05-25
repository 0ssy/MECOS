from itertools import combinations
from typing import List, Dict, Any
from loguru import logger

from memory_system import MemorySystem
from trading import (
    FeatureEngine,
    MarketPhysicsEngine,
    PortfolioEngine,
    ExecutionEngine,
    RegimeDetectionAgent,
    MetaOrchestrator,
    RiskEngine,
    TrendAgent,
    OptionsPricingAgent,
    MeanReversionAgent,
    VolatilityArbitrageAgent,
    LiquidityHunterAgent,
    SentimentAgent,
    StatisticalArbitrageEngine,
    MarketMakingAgent,
    QuantSignalFusion,
)

MIN_CONFIDENCE_BY_MODE = {
    "conservative": 0.70,
    "balanced": 0.60,
    "aggressive_research": 0.50,
}


def _normalize_quant_mode(mode: str) -> str:
    normalized = (mode or "balanced").strip().lower().replace("-", "_")
    aliases = {
        "research": "aggressive_research",
        "aggressive": "aggressive_research",
        "option2": "balanced",
        "option3": "aggressive_research",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in MIN_CONFIDENCE_BY_MODE:
        return "balanced"
    return normalized


class TradingAgent:
    def __init__(self, memory: MemorySystem, quant_mode: str = "balanced"):
        self.memory = memory
        self.quant_mode = _normalize_quant_mode(quant_mode)
        self.min_confidence = MIN_CONFIDENCE_BY_MODE[self.quant_mode]

        self.feature_engine = FeatureEngine(memory)
        self.physics_engine = MarketPhysicsEngine(memory)
        self.portfolio_engine = PortfolioEngine(memory)
        self.execution_engine = ExecutionEngine(memory)

        self.regime_detector = RegimeDetectionAgent(memory)
        self.meta_orchestrator = MetaOrchestrator(memory)
        self.risk_engine = RiskEngine(memory)
        self.stat_arb_engine = StatisticalArbitrageEngine(memory)
        self.signal_fusion = QuantSignalFusion()

        self.agents = {
            "trend": TrendAgent(memory),
            "options": OptionsPricingAgent(memory),
            "mean_reversion": MeanReversionAgent(memory),
            "volatility": VolatilityArbitrageAgent(memory),
            "liquidity": LiquidityHunterAgent(memory),
            "sentiment": SentimentAgent(memory),
            "market_making": MarketMakingAgent(memory),
        }
        for name, agent in self.agents.items():
            self.meta_orchestrator.register_agent(name, agent)

        self.paper_portfolio = {
            "cash": 10000.0,
            "positions": {},
            "total_value": 10000.0,
        }
        self.stats = {
            "analyses": 0,
            "actionable_signals": 0,
            "risk_rejections": 0,
            "total_pnl": 0,
            "win_rate": 0,
        }

        logger.info("INSTITUTIONAL QUANT TRADING AGENT INITIALIZED")
        logger.info(f"    Quant mode: {self.quant_mode} | min_confidence={self.min_confidence:.2f}")
        logger.info("    Engines: Feature, Physics, Portfolio, Execution")
        logger.info(f"    Agents: {len(self.agents)} specialist strategies")
        logger.info("    Fusion: Regime-aware Bayesian ensemble")

    async def analyze_market(self, symbol: str, data: List[Dict]) -> Dict[str, Any]:
        self.stats["analyses"] += 1
        logger.info(f" Analyzing {symbol}...")

        valid_data = [bar for bar in data if isinstance(bar, dict) and "close" in bar]
        if not valid_data:
            return {"final_decision": "HOLD", "confidence": 0.0, "reason": "invalid_market_data"}
        data = valid_data

        features = await self.feature_engine.compute_features(data)
        physics = await self.physics_engine.analyze(symbol, data, features)
        regime = await self.regime_detector.detect_regime(data)
        orchestrated = await self.meta_orchestrator.orchestrate_signals(data, regime, features, physics)
        fused = self.signal_fusion.fuse(orchestrated, features, regime)
        signals = {
            **orchestrated,
            **fused,
            "regime": regime,
        }

        logger.debug(
            "   Signals: Trend={} | MeanRev={} | Sentiment={} | MM={}".format(
                signals.get("agent_signals", {}).get("trend", {}).get("signal", "N/A"),
                signals.get("agent_signals", {}).get("mean_reversion", {}).get("signal", "N/A"),
                signals.get("agent_signals", {}).get("sentiment", {}).get("sentiment", "N/A"),
                signals.get("agent_signals", {}).get("market_making", {}).get("signal", "N/A"),
            )
        )

        decision = str(signals.get("decision", signals.get("final_decision", "HOLD"))).upper()
        confidence = float(signals.get("confidence", 0.0))
        signals["decision"] = decision
        signals["final_decision"] = decision

        if decision == "HOLD":
            logger.info("   HOLD: insufficient signal agreement")
            return {
                **signals,
                "features": features,
                "physics": physics,
                "portfolio": await self.portfolio_engine.calculate_portfolio_metrics(self.paper_portfolio),
            }

        if confidence < self.min_confidence:
            logger.info("   REJECTED: low confidence")
            signals["decision"] = "HOLD"
            signals["final_decision"] = "HOLD"
            return {
                **signals,
                "features": features,
                "physics": physics,
                "portfolio": await self.portfolio_engine.calculate_portfolio_metrics(self.paper_portfolio),
            }

        if signals["final_decision"] != "HOLD":
            signal_strength = signals.get("confidence", 0.5)
            volatility = features.get("realized_volatility", 0.3)
            sizing = signals.get("sizing_multipliers", {})
            position_size = await self.portfolio_engine.optimize_position_size(
                signal_strength,
                self.paper_portfolio,
                volatility,
                confidence_multiplier=sizing.get("confidence_multiplier", 1.0),
                regime_multiplier=sizing.get("regime_multiplier", 1.0),
                liquidity_multiplier=sizing.get("microstructure_multiplier", 1.0),
                correlation_penalty=sizing.get("correlation_penalty", 1.0),
            )
            trade = {
                "symbol": symbol,
                "side": signals["final_decision"],
                "size": position_size,
                "price": data[-1]["close"],
            }
            execution_plan = await self.execution_engine.plan_execution(
                trade,
                {
                    "volume_ratio": features.get("volume_ratio", 1.0),
                    "spread_pressure": features.get("spread_pressure", 0.001),
                },
            )
            risk = await self.risk_engine.evaluate_risk(trade, self.paper_portfolio)
            if risk["action"] == "REJECT":
                self.stats["risk_rejections"] += 1
                signals["final_decision"] = "HOLD"
                signals["decision"] = "HOLD"
                logger.warning(f"   TRADE REJECTED: {risk.get('reason', 'Risk limit')}")
            else:
                self.stats["actionable_signals"] += 1
                logger.info(f"   TRADE APPROVED: {trade['side']} {position_size:.1%} @ {trade['price']}")
                signals["execution_plan"] = execution_plan
                signals["position_size"] = position_size
                signals["allocation"] = position_size
                signals["volatility"] = volatility

        portfolio_metrics = await self.portfolio_engine.calculate_portfolio_metrics(self.paper_portfolio)
        await self.memory.add_experience(
            f"QUANT ANALYSIS: {symbol} | Decision: {signals.get('final_decision', 'HOLD')} | "
            f"Vol: {features.get('realized_volatility', 0):.3f} | "
            f"Tail Risk: {physics['tail_risk']['tail_risk_score']:.3f} | "
            f"Exposure: {portfolio_metrics.get('total_exposure', 0):.1%} | "
            f"Regime: {regime}",
            source="trading_agent",
            metadata={
                "symbol": symbol,
                "features": features,
                "physics": physics,
                "signals": signals,
                "portfolio": portfolio_metrics,
            },
        )

        return {
            **signals,
            "features": features,
            "physics": physics,
            "portfolio": portfolio_metrics,
        }

    async def analyze_multi_asset(self, market_data: Dict[str, List[Dict]]) -> Dict[str, Any]:
        per_asset: Dict[str, Dict[str, Any]] = {}
        for symbol, data in market_data.items():
            per_asset[symbol] = await self.analyze_market(symbol, data)

        correlations = {}
        symbols = list(market_data.keys())
        for i, left in enumerate(symbols):
            left_series = [bar.get("close", 0.0) for bar in market_data[left]]
            if len(left_series) < 10:
                continue
            for right in symbols[i + 1:]:
                right_series = [bar.get("close", 0.0) for bar in market_data[right]]
                min_len = min(len(left_series), len(right_series))
                if min_len < 10:
                    continue
                a = left_series[-min_len:]
                b = right_series[-min_len:]
                mean_a = sum(a) / min_len
                mean_b = sum(b) / min_len
                var_a = sum((x - mean_a) ** 2 for x in a)
                var_b = sum((x - mean_b) ** 2 for x in b)
                if var_a <= 1e-9 or var_b <= 1e-9:
                    corr = 0.0
                else:
                    cov = sum((a[j] - mean_a) * (b[j] - mean_b) for j in range(min_len))
                    corr = cov / (var_a ** 0.5 * var_b ** 0.5)
                correlations[f"{left}:{right}"] = float(corr)

        pair_arbitrage = []
        for left, right in combinations(symbols, 2):
            try:
                pair_signal = await self.stat_arb_engine.analyze_pair(market_data[left], market_data[right])
                pair_signal["pair"] = [left, right]
                pair_arbitrage.append(pair_signal)
            except Exception as exc:
                pair_arbitrage.append({"pair": [left, right], "signal": "HOLD", "error": str(exc)})

        return {
            "asset_signals": per_asset,
            "cross_asset_correlation": correlations,
            "pair_arbitrage": pair_arbitrage,
        }

    def get_performance_metrics(self) -> Dict[str, Any]:
        analyses = max(self.stats["analyses"], 1)
        actionable_rate = self.stats["actionable_signals"] / analyses
        return {
            **self.stats,
            "actionable_rate": actionable_rate,
            "sharpe_ratio": 0,
            "max_drawdown": 0,
            "portfolio_value": self.paper_portfolio["total_value"],
        }
