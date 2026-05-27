from typing import Dict, Any, List, Optional, Tuple
from loguru import logger

from memory_system import MemorySystem
from trading.config import TradingConfig
from trading.regime_detection_agent import RegimeDetectionAgent
from trading.meta_orchestrator import MetaOrchestrator
from trading.risk_engine import RiskEngine
from trading.feature_engine import FeatureEngine
from trading.market_physics_engine import MarketPhysicsEngine
from trading.portfolio_engine import PortfolioEngine
from trading.quant_signal_fusion import QuantSignalFusion
from trading.trend_agent import TrendAgent
from trading.mean_reversion_agent import MeanReversionAgent
from trading.volatility_arbitrage_agent import VolatilityArbitrageAgent
from trading.options_pricing_agent import OptionsPricingAgent
from trading.liquidity_hunter_agent import LiquidityHunterAgent
from trading.statistical_arbitrage_engine import StatisticalArbitrageEngine
from trading.sentiment_agent import SentimentAgent
from trading.reinforcement_learning_optimizer import ReinforcementLearningOptimizer
from trading.market_making_agent import MarketMakingAgent


class _OrderFlowProxyAgent:
    def __init__(self, memory: MemorySystem):
        self.memory = memory

    async def analyze(self, data: List[Dict], features: Dict, physics: Optional[Dict] = None) -> Dict[str, Any]:
        imbalance = float(features.get("order_flow_imbalance", 0.0))
        spread_pressure = float(features.get("spread_pressure", 0.0))
        signal = "HOLD"
        if imbalance > 0.25 and spread_pressure < 0.01:
            signal = "BUY"
        elif imbalance < -0.25 and spread_pressure < 0.01:
            signal = "SELL"
        confidence = min(0.9, abs(imbalance) * 1.5)
        return {
            "signal": signal,
            "confidence": float(confidence),
            "imbalance": imbalance,
            "spread_pressure": spread_pressure,
        }


class _StatisticalArbitrageProxyAgent:
    def __init__(self, memory: MemorySystem):
        self.engine = StatisticalArbitrageEngine(memory)

    async def analyze(
        self,
        pair_data: Any,
        features: Optional[Dict[str, Any]] = None,
        physics: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        if not isinstance(pair_data, dict):
            return {"signal": "HOLD", "confidence": 0.0, "reason": "pair_data_not_available"}
        symbols = list(pair_data.keys())
        if len(symbols) < 2:
            return {"signal": "HOLD", "confidence": 0.0, "reason": "insufficient_pair_data"}
        left, right = symbols[0], symbols[1]
        result = await self.engine.analyze_pair(pair_data[left], pair_data[right])
        signal = str(result.get("signal", "HOLD")).upper()
        confidence = min(0.9, abs(float(result.get("z_score", 0.0))) / 3.0)
        return {
            **result,
            "signal": signal,
            "confidence": float(confidence),
            "pair": [left, right],
        }


class _ReinforcementLearningProxyAgent:
    def __init__(self, memory: MemorySystem):
        self.optimizer = ReinforcementLearningOptimizer(memory)

    async def analyze(self, data: List[Dict], features: Dict, physics: Optional[Dict] = None) -> Dict[str, Any]:
        state = {
            "trend_strength": round(float(features.get("trend_strength", 0.0)), 3),
            "volatility": round(float(features.get("realized_volatility", 0.0)), 3),
            "momentum": round(float(features.get("roc_20", 0.0)), 3),
        }
        action = self.optimizer.choose_action(state)
        return {
            "signal": str(action).upper(),
            "confidence": 0.55 if action != "HOLD" else 0.40,
            "state": state,
        }


class TradingAgent:
    def __init__(self, memory: MemorySystem, quant_mode: str = "balanced"):
        self.memory = memory
        self.quant_mode = quant_mode

        self.regime_detector = RegimeDetectionAgent(memory)
        self.meta_orchestrator = MetaOrchestrator(memory)
        self.risk_engine = RiskEngine(memory)
        self.feature_engine = FeatureEngine(memory)
        self.physics_engine = MarketPhysicsEngine(memory)
        self.portfolio_engine = PortfolioEngine(memory)
        self.signal_fusion = QuantSignalFusion()

        self.trend_agent = TrendAgent(memory)
        self.mean_reversion_agent = MeanReversionAgent(memory)
        self.volatility_agent = VolatilityArbitrageAgent(memory)
        self.options_pricing_agent = OptionsPricingAgent(memory)
        self.order_flow_agent = _OrderFlowProxyAgent(memory)
        self.liquidity_hunter_agent = LiquidityHunterAgent(memory)
        self.statistical_arbitrage_agent = _StatisticalArbitrageProxyAgent(memory)
        self.sentiment_agent = SentimentAgent(memory)
        self.reinforcement_learning_agent = _ReinforcementLearningProxyAgent(memory)
        self.market_making_agent = MarketMakingAgent(memory)

        self.meta_orchestrator.register_agent("trend", self.trend_agent)
        self.meta_orchestrator.register_agent("mean_reversion", self.mean_reversion_agent)
        self.meta_orchestrator.register_agent("volatility", self.volatility_agent)
        self.meta_orchestrator.register_agent("options_pricing", self.options_pricing_agent)
        self.meta_orchestrator.register_agent("order_flow", self.order_flow_agent)
        self.meta_orchestrator.register_agent("liquidity_hunter", self.liquidity_hunter_agent)
        self.meta_orchestrator.register_agent("statistical_arbitrage", self.statistical_arbitrage_agent)
        self.meta_orchestrator.register_agent("sentiment", self.sentiment_agent)
        self.meta_orchestrator.register_agent("reinforcement_learning", self.reinforcement_learning_agent)
        self.meta_orchestrator.register_agent("market_making", self.market_making_agent)

        self.paper_portfolio = {"cash": 10000.0, "positions": {}, "total_value": 10000.0}
        logger.info("Advanced TradingAgent initialized with all specialist agents.")

    async def _analyze_symbol(self, symbol: str, data: List[Dict]) -> Dict[str, Any]:
        if not data:
            return {
                "decision": "HOLD",
                "final_decision": "HOLD",
                "confidence": 0.0,
                "signals": {},
                "agent_signals": {},
                "regime": "unknown",
                "reason": "no_data",
            }

        valid_data = [bar for bar in data if isinstance(bar, dict) and "close" in bar]
        if not valid_data:
            return {
                "decision": "HOLD",
                "final_decision": "HOLD",
                "confidence": 0.0,
                "signals": {},
                "agent_signals": {},
                "regime": "unknown",
                "reason": "invalid_data",
            }

        logger.info(f"Analyzing {symbol}...")
        regime = await self.regime_detector.detect_regime(valid_data)
        features = await self.feature_engine.compute_features(valid_data)
        features["close"] = float(valid_data[-1].get("close", 0.0))
        physics = await self.physics_engine.analyze(symbol, valid_data, features)

        orchestrator_data = {symbol: valid_data}
        orchestrated = await self.meta_orchestrator.orchestrate_signals(
            orchestrator_data,
            regime,
            features,
            physics,
        )
        fused = self.signal_fusion.fuse(orchestrated, features, regime)

        orchestrator_decision = str(orchestrated.get("final_decision", "HOLD")).upper()
        final_decision = str(fused.get("decision", orchestrator_decision)).upper()
        confidence = float(fused.get("confidence", orchestrated.get("confidence", 0.0)))
        edge = float(fused.get("edge", 0.0))
        if orchestrator_decision == "HOLD" and abs(edge) < 0.20:
            final_decision = "HOLD"

        if confidence < float(TradingConfig.MIN_CONFIDENCE):
            final_decision = "HOLD"

        position_size = 0.0
        portfolio_metrics = await self.portfolio_engine.calculate_portfolio_metrics(self.paper_portfolio)
        if final_decision != "HOLD":
            sizing = fused.get("sizing_multipliers", {})
            volatility = float(features.get("realized_volatility", 0.3) or 0.3)
            position_size = await self.portfolio_engine.optimize_position_size(
                signal_strength=confidence,
                portfolio=self.paper_portfolio,
                volatility=volatility,
                confidence_multiplier=float(sizing.get("confidence_multiplier", 1.0)),
                regime_multiplier=float(sizing.get("regime_multiplier", 1.0)),
                liquidity_multiplier=float(sizing.get("microstructure_multiplier", 1.0)),
                correlation_penalty=float(sizing.get("correlation_penalty", 1.0)),
            )
            trade = {
                "symbol": symbol,
                "side": final_decision,
                "size": max(position_size, 0.01),
                "price": float(valid_data[-1].get("close", 0.0)),
            }
            risk_evaluation = await self.risk_engine.evaluate_risk(trade, self.paper_portfolio)
            risk_action = str(risk_evaluation.get("action", "APPROVE")).upper()

            if risk_action == "REJECT":
                final_decision = "HOLD"
                logger.warning(
                    f"TRADE REJECTED for {symbol}: {risk_evaluation.get('reason', 'Risk rejection')}"
                )
            elif risk_action == "ADJUST":
                trade["size"] = float(risk_evaluation.get("new_size", trade["size"]))
                position_size = float(trade["size"])
                logger.info(
                    f"TRADE ADJUSTED for {symbol}: New size {trade['size']:.2f} due to "
                    f"{risk_evaluation.get('reason', 'Risk adjustment')}"
                )

        logger.info(f"Decision for {symbol}: {final_decision} (Confidence: {confidence:.2f})")
        spread_pressure = float(features.get("spread_pressure", 0.0))
        expected_move = float(max(abs(features.get("roc_5", 0.0)), abs(features.get("trend_strength", 0.0))))
        if expected_move <= 0.0 and valid_data[-1].get("open"):
            expected_move = abs(
                float(valid_data[-1].get("close", 0.0) or 0.0) / float(valid_data[-1].get("open", 1.0) or 1.0) - 1.0
            )

        return {
            "symbol": symbol,
            "decision": final_decision,
            "final_decision": final_decision,
            "confidence": confidence,
            "signals": orchestrated.get("agent_signals", {}),
            "agent_signals": orchestrated.get("agent_signals", {}),
            "features": features,
            "physics": physics,
            "portfolio": portfolio_metrics,
            "position_size": float(position_size),
            "allocation": float(position_size),
            "buy_score": float(fused.get("buy_score", orchestrated.get("buy_score", 0.0))),
            "sell_score": float(fused.get("sell_score", orchestrated.get("sell_score", 0.0))),
            "hold_score": float(fused.get("hold_score", orchestrated.get("hold_score", 0.0))),
            "edge": float(edge),
            "expected_move": float(expected_move),
            "spread_pressure": float(spread_pressure),
            "regime": regime,
        }

    async def analyze_market(
        self,
        symbol_or_market_data: Any,
        data: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        if isinstance(symbol_or_market_data, dict) and data is None:
            all_decisions: Dict[str, Any] = {}
            for symbol, symbol_data in symbol_or_market_data.items():
                all_decisions[symbol] = await self._analyze_symbol(symbol, symbol_data)
            return all_decisions

        symbol = str(symbol_or_market_data)
        return await self._analyze_symbol(symbol, data or [])

    async def analyze_multi_asset(self, market_data: Dict[str, List[Dict]]) -> Dict[str, Any]:
        decisions = await self.analyze_market(market_data)
        return {"asset_signals": decisions}
