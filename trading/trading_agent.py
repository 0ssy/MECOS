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
)


class TradingAgent:
    def __init__(self, memory: MemorySystem):
        self.memory = memory

        self.feature_engine = FeatureEngine(memory)
        self.physics_engine = MarketPhysicsEngine(memory)
        self.portfolio_engine = PortfolioEngine(memory)
        self.execution_engine = ExecutionEngine(memory)

        self.regime_detector = RegimeDetectionAgent(memory)
        self.meta_orchestrator = MetaOrchestrator(memory)
        self.risk_engine = RiskEngine(memory)
        self.stat_arb_engine = StatisticalArbitrageEngine(memory)

        self.agents = {
            "trend": TrendAgent(memory),
            "options": OptionsPricingAgent(memory),
            "mean_reversion": MeanReversionAgent(memory),
            "volatility": VolatilityArbitrageAgent(memory),
            "liquidity": LiquidityHunterAgent(memory),
            "sentiment": SentimentAgent(memory),
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
        logger.info("    Engines: Feature, Physics, Portfolio, Execution")
        logger.info(f"    Agents: {len(self.agents)} specialist strategies")

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
        signals = await self.meta_orchestrator.orchestrate_signals(data, regime, features, physics)

        logger.debug(
            "   Signals: Trend={} | MeanRev={} | Sentiment={}".format(
                signals.get("agent_signals", {}).get("trend", {}).get("signal", "N/A"),
                signals.get("agent_signals", {}).get("mean_reversion", {}).get("signal", "N/A"),
                signals.get("agent_signals", {}).get("sentiment", {}).get("sentiment", "N/A"),
            )
        )

        if signals["final_decision"] != "HOLD":
            signal_strength = signals.get("confidence", 0.5)
            volatility = features.get("realized_volatility", 0.3)
            position_size = await self.portfolio_engine.optimize_position_size(
                signal_strength,
                self.paper_portfolio,
                volatility,
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
                logger.warning(f"   TRADE REJECTED: {risk.get('reason', 'Risk limit')}")
            else:
                self.stats["actionable_signals"] += 1
                logger.info(f"   TRADE APPROVED: {trade['side']} {position_size:.1%} @ {trade['price']}")
                signals["execution_plan"] = execution_plan
                signals["position_size"] = position_size

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

        pair_arbitrage = []
        symbols = list(market_data.keys())
        for left, right in combinations(symbols, 2):
            try:
                pair_signal = await self.stat_arb_engine.analyze_pair(market_data[left], market_data[right])
                pair_signal["pair"] = [left, right]
                pair_arbitrage.append(pair_signal)
            except Exception as exc:
                pair_arbitrage.append({"pair": [left, right], "signal": "HOLD", "error": str(exc)})

        return {
            "asset_signals": per_asset,
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
