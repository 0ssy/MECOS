import os
from trading.asset_profiles import get_sector
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
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
from trading.persona_engine import PersonaEngine
from trading.mecos_consensus_engine import ConsensusEngine
from trading.openbb_adapter import OpenBBDataAdapter
from trading.financial_analytics import FinancialAnalytics
from trading.macro_data import MacroDataProvider
from trading.news_sentiment import NewsSentimentEngine
from trading.portfolio_optimizer import PortfolioOptimizer
from trading.regime_detector import RegimeDetector
from trading.multi_timeframe import MultiTimeframeAnalyzer
from trading.options_pricing import OptionsEngine
from trading.backtester import SimpleBacktester
from trading.risk_manager import RiskManager as PortfolioRiskManager
from trading.signal_weighter import SignalWeighter


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
            "confidence": self.optimizer.action_confidence(state, action),
            "state": state,
        }


class TradingAgent:
    def __init__(self, memory: MemorySystem, quant_mode: str = "balanced"):
        self.memory = memory
        self.quant_mode = quant_mode

        self.regime_detector = RegimeDetectionAgent(memory)
        self.meta_orchestrator = MetaOrchestrator(memory)
        self.quant_fusion = QuantSignalFusion()  # Primary signal fusion layer
        # Portfolio and execution engines (lazy import to avoid circular deps)
        try:
            from trading.portfolio_engine import PortfolioEngine
            from trading.execution_engine import ExecutionEngine
            self.portfolio_engine = PortfolioEngine(memory)
            self.execution_engine = ExecutionEngine(memory)
        except Exception as _eng_err:
            self.portfolio_engine = None
            self.execution_engine = None
        self.uncertainty_flagger = None  # wired from main.py
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
        self.persona_engine = PersonaEngine()
        require_unanimous = False
        min_support = float(os.getenv("MECOS_CONSENSUS_MIN_SUPPORT", "0.67"))
        self.consensus_engine = ConsensusEngine(
            self.persona_engine.get_personas(),
            minimum_support_ratio=min_support,
            require_unanimous=require_unanimous,
        )
        # Unified collaborative engine — replaces MetaOrchestrator + ConsensusEngine chain
        from trading.collaborative_decision_engine import CollaborativeDecisionEngine
        self.collab_engine = CollaborativeDecisionEngine(
            agents=self.meta_orchestrator.agents,
            personas={
                name: self.consensus_engine._persona_analysis
                for name in self.consensus_engine.personas
            },
        )
        logger.info(
            f"Consensus config | require_unanimous={require_unanimous} min_support={min_support:.2f}"
        )
        self.openbb_adapter = OpenBBDataAdapter()
        self.use_openbb_macro = os.getenv("MECOS_USE_OPENBB_MACRO", "false").strip().lower() == "true"
        self.financial_analytics = FinancialAnalytics()
        self.macro_data_provider = MacroDataProvider()
        self.news_sentiment = NewsSentimentEngine()
        self.portfolio_optimizer = PortfolioOptimizer()
        self.rule_regime_detector = RegimeDetector()
        self.multi_timeframe_analyzer = MultiTimeframeAnalyzer()
        self.options_engine = OptionsEngine()
        self.quick_backtester = SimpleBacktester(initial_cash=10_000.0, fee_bps=5.0)
        self.portfolio_risk_manager = PortfolioRiskManager(account_balance=10_000.0, max_risk_per_trade=0.01)
        self.signal_weighter = SignalWeighter()
        self.neural_brain = None
        self.neural_brain_enabled = os.getenv("MECOS_ENABLE_NEURAL_BRAIN", "false").strip().lower() == "true"
        if self.neural_brain_enabled:
            try:
                from mecos_brain import MECOSBrain

                self.neural_brain = MECOSBrain(memory_system=memory)
                logger.info("Neural brain enabled for TradingAgent")
            except Exception as exc:
                self.neural_brain_enabled = False
                logger.warning(f"Neural brain unavailable, continuing without it: {exc}")

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
        sector = get_sector(symbol)
        if sector == "crypto":
            persona_asset_type = "crypto"
        elif sector == "forex":
            persona_asset_type = "forex"
        elif sector == "commodity_fx":
            persona_asset_type = "macro"
        else:
            persona_asset_type = "equity"
        active_personas = self.persona_engine.get_active_personas(persona_asset_type)
        primary_persona = self.persona_engine.get_primary_persona(persona_asset_type)
        persona_context = self.persona_engine.get_prompt_injection(persona_asset_type)
        regime = await self.regime_detector.detect_regime(valid_data)
        features = await self.feature_engine.compute_features(valid_data)
        features["close"] = float(valid_data[-1].get("close", 0.0))
        physics = await self.physics_engine.analyze(symbol, valid_data, features)
        external_market_context = {
            "market_data": self.openbb_adapter.safe_get_market_data(symbol),
            "news": self.openbb_adapter.safe_get_news(symbol, limit=3),
        }
        macro_indicator = "DGS10" if persona_asset_type in {"equity", "macro"} else "DEXUSEU"
        if self.use_openbb_macro:
            external_market_context["macro_data_openbb"] = self.openbb_adapter.safe_get_macro_data(macro_indicator)
        else:
            external_market_context["macro_data_openbb"] = {
                "indicator": macro_indicator,
                "available": False,
                "error": "openbb_macro_disabled",
            }
        close_prices = [float(bar.get("close", 0.0) or 0.0) for bar in valid_data if "close" in bar]
        analytics_summary = self.financial_analytics.summarize_prices(close_prices)
        macro_snapshot = self.macro_data_provider.get_macro_snapshot(persona_asset_type)
        news_snapshot = self.news_sentiment.analyze_symbol(symbol, limit=5)
        mtf_snapshot = self.multi_timeframe_analyzer.analyze_bars(valid_data)
        regime_snapshot = self.rule_regime_detector.detect_from_bars(close_prices)
        optimizer_snapshot = self.portfolio_optimizer.recommend_single_asset(
            prices=close_prices,
            base_confidence=float(features.get("trend_strength", 0.0)),
            edge=float(features.get("roc_20", 0.0)),
            regime=str(regime_snapshot.get("regime", "unknown")),
        )
        option_snapshot = self._build_option_snapshot(close_prices, features)
        backtest_snapshot = self._build_quick_backtest(valid_data)
        external_market_context["macro_data"] = macro_snapshot
        external_market_context["news_sentiment"] = news_snapshot
        external_market_context["analytics"] = analytics_summary
        external_market_context["multi_timeframe"] = mtf_snapshot
        external_market_context["rule_regime"] = regime_snapshot
        external_market_context["optimizer"] = optimizer_snapshot
        external_market_context["options"] = option_snapshot
        external_market_context["quick_backtest"] = backtest_snapshot

        # ── Unified collaborative decision — replaces four-layer chain ──────────
        collab = await self.collab_engine.decide(
            symbol=symbol,
            data=valid_data,
            features=features,
            regime=regime,
            physics=physics,
            asset_type=persona_asset_type,
            news_score=float(news_snapshot.get("sentiment_score", 0.0) or 0.0),
            macro_snapshot=macro_snapshot,
            extra_context={
                "active_personas": active_personas,
                "external_market_context": external_market_context,
            },
        )
        final_decision = str(collab.get("decision", "HOLD")).upper()
        confidence     = float(collab.get("confidence", 0.0))
        edge           = float(collab.get("edge", 0.0))
        orchestrated   = collab  # keep legacy key for downstream code

        # Kelly-fraction position sizing
        _vol   = max(float(features.get("realized_volatility", 0.02)), 0.01)
        _kelly = float(np.clip(0.5 * (abs(edge) * confidence) / _vol, 0.01, 0.20)) \
            if edge != 0 and confidence > 0 else 0.01
        orchestrated["kelly_fraction"] = _kelly
        orchestrated["allocation"]     = _kelly

        risk_gate_reason = ""
        macro_regime = str(macro_snapshot.get("risk_regime", "neutral")).lower()
        news_score = float(news_snapshot.get("sentiment_score", 0.0) or 0.0)
        var_95 = float(analytics_summary.get("var_95", 0.0) or 0.0)
        drawdown = float(analytics_summary.get("max_drawdown", 0.0) or 0.0)
        if final_decision == "BUY":
            if macro_regime == "risk_off" and confidence < 0.50:
                risk_gate_reason = "macro_risk_off"
            elif news_score <= -0.35 and confidence < 0.45:
                risk_gate_reason = "negative_news_sentiment"
            elif drawdown <= -0.12 and abs(var_95) >= 0.035 and confidence < 0.50:
                risk_gate_reason = "high_drawdown_and_var"
            elif str(regime_snapshot.get("regime", "unknown")) in {"bear", "panic"} and confidence < 0.55:
                risk_gate_reason = "rule_regime_not_supporting_buy"
        elif final_decision == "SELL":
            if macro_regime == "risk_on" and news_score >= 0.35 and confidence < 0.50:
                risk_gate_reason = "risk_on_with_bullish_news"
        mtf_alignment = float(mtf_snapshot.get("alignment_score", 0.0) or 0.0)
        if final_decision == "BUY" and mtf_alignment < -0.40 and confidence < 0.55:
            risk_gate_reason = "multi_timeframe_bearish_alignment"
        if final_decision == "SELL" and mtf_alignment > 0.40 and confidence < 0.55:
            risk_gate_reason = "multi_timeframe_bullish_alignment"
        bt_return = float(backtest_snapshot.get("total_return", 0.0) or 0.0)
        if final_decision == "BUY" and bt_return < -0.03 and confidence < 0.45:
            risk_gate_reason = "backtest_negative_expectancy"
        if risk_gate_reason:
            logger.info(f"Risk gate forced HOLD for {symbol}: {risk_gate_reason}")
            final_decision = "HOLD"

        rsi_value = float(features.get("rsi_14", features.get("rsi", 50.0)) or 50.0)
        weighted_confidence = self.signal_weighter.score_opportunity(
            {
                "rsi": rsi_value,
                "regime": str(regime_snapshot.get("regime", regime)),
                "sentiment": news_score,
                "macro": str(macro_snapshot.get("risk_regime", "neutral")),
                "pattern": float(edge),
                "timeframe": mtf_alignment,
            }
        )
        confidence = float(np.clip(0.75 * confidence + 0.25 * weighted_confidence, 0.0, 1.0))
        neural_context = self._run_neural_brain(
            symbol=symbol,
            bars=valid_data,
            features=features,
            regime=regime,
            mtf_snapshot=mtf_snapshot,
            macro_snapshot=macro_snapshot,
            news_snapshot=news_snapshot,
            edge=edge,
        )
        if neural_context:
            neural_decision = str(neural_context.get("decision", "HOLD")).upper()
            neural_uncertainty = float(neural_context.get("uncertainty", 1.0) or 1.0)
            if neural_decision == final_decision and neural_uncertainty <= 0.5:
                confidence = float(np.clip(confidence + 0.07, 0.0, 1.0))
            elif final_decision == "HOLD" and neural_decision in {"BUY", "SELL"} and neural_uncertainty <= 0.35:
                final_decision = neural_decision
                confidence = float(np.clip(max(confidence, 1.0 - neural_uncertainty), 0.0, 1.0))
            if neural_uncertainty >= 0.85 and confidence < 0.95 and final_decision != "HOLD":
                risk_gate_reason = "neural_high_uncertainty"
                final_decision = "HOLD"
            external_market_context["neural_brain"] = neural_context

        if False: # Overridden for Testing
            final_decision = "HOLD"

        position_size = 0.0
        portfolio_metrics = await self.portfolio_engine.calculate_portfolio_metrics(self.paper_portfolio)
        if final_decision != "HOLD":
            sizing = fused.get("sizing_multipliers", {})
            volatility = float(features.get("realized_volatility", 0.3) or 0.3)
            optimizer_multiplier = float(optimizer_snapshot.get("allocation_multiplier", 1.0) or 1.0)
            position_size = await self.portfolio_engine.optimize_position_size(
                signal_strength=confidence,
                portfolio=self.paper_portfolio,
                volatility=volatility,
                confidence_multiplier=float(sizing.get("confidence_multiplier", 1.0)) * optimizer_multiplier,
                regime_multiplier=float(sizing.get("regime_multiplier", 1.0)),
                liquidity_multiplier=float(sizing.get("microstructure_multiplier", 1.0)),
                correlation_penalty=float(sizing.get("correlation_penalty", 1.0)),
            )
            entry = float(valid_data[-1].get("close", 0.0) or 0.0)
            atr = float(features.get("atr", 0.0) or 0.0)
            default_stop = entry - max(atr * 2.0, entry * 0.01) if final_decision == "BUY" else entry + max(atr * 2.0, entry * 0.01)
            risk_manager_size = self.portfolio_risk_manager.position_size(entry=entry, stop_loss=default_stop)
            if risk_manager_size > 0.0:
                position_size = max(0.01, min(position_size, risk_manager_size))
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

        # UncertaintyFlagger gate
            if self.uncertainty_flagger is not None:
                try:
                    _uf_approval = self.uncertainty_flagger.score_plan(
                        plan=f"{symbol} {final_decision}",
                        signal_strength=float(fused.get("confidence", 0.5)),
                        market_regime=0.7 if regime != "unknown" else 0.4,
                        volatility_regime=float(min(1.0, 1.0 - features.get("realized_volatility", 0.3))),
                        data_freshness=0.9,
                        historical_accuracy=float(fused.get("agreement", 0.5)),
                        edge_case_coverage=0.6,
                    )
                    if not _uf_approval.execution_approved and final_decision != "HOLD":
                        logger.debug(f"UncertaintyFlagger blocked {symbol}: conf={_uf_approval.confidence_score:.2f}")
                        final_decision = "HOLD"
                        confidence = _uf_approval.confidence_score
                except Exception as exc:
                    logger.warning(f"UncertaintyFlagger evaluation failed for {symbol}: {exc}")
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
            "weighted_confidence": float(weighted_confidence),
            "neural_brain": neural_context,
            "persona_context": persona_context,
            "consensus": consensus,
            "sector": sector,
            "primary_persona": primary_persona,
            "active_personas": active_personas,
            "external_market_context": external_market_context,
            "risk_gate_reason": risk_gate_reason,
        }

    def _run_neural_brain(
        self,
        symbol: str,
        bars: List[Dict[str, Any]],
        features: Dict[str, Any],
        regime: str,
        mtf_snapshot: Dict[str, Any],
        macro_snapshot: Dict[str, Any],
        news_snapshot: Dict[str, Any],
        edge: float,
    ) -> Dict[str, Any]:
        if not self.neural_brain_enabled or self.neural_brain is None:
            return {}
        try:
            base_rsi = float(features.get("rsi_14", features.get("rsi", 50.0)) or 50.0)
            signals = {
                "rsi": base_rsi,
                "macd": float(features.get("macd", 0.0) or 0.0),
                "atr": float(features.get("atr", 0.0) or 0.0),
                "volume_ratio": float(features.get("volume_ratio", 1.0) or 1.0),
                "news_sentiment": float(news_snapshot.get("sentiment_score", 0.0) or 0.0),
                "regime": str(regime),
                "portfolio_heat": float(self.paper_portfolio.get("total_value", 10_000.0) / 10_000.0),
                "drawdown": float(features.get("drawdown", 0.0) or 0.0),
                "win_rate": 0.5,
                "fed_rate": float(macro_snapshot.get("policy_rate", 5.0) or 5.0),
                "vix": float(macro_snapshot.get("vix", 20.0) or 20.0),
                "rsi_1d": float(mtf_snapshot.get("rsi_daily", base_rsi) if isinstance(mtf_snapshot, dict) else base_rsi),
                "rsi_4h": float(mtf_snapshot.get("rsi_4h", base_rsi) if isinstance(mtf_snapshot, dict) else base_rsi),
                "rsi_1h": float(mtf_snapshot.get("rsi_1h", base_rsi) if isinstance(mtf_snapshot, dict) else base_rsi),
                "pattern": float(edge),
            }
            regime_token = str(regime).lower()
            signals["regime_bull"] = 1.0 if regime_token in {"bull", "trending"} else 0.0
            signals["regime_bear"] = 1.0 if regime_token in {"bear", "panic"} else 0.0
            signals["regime_sideways"] = 1.0 if regime_token in {"sideways", "ranging"} else 0.0
            brain_out = self.neural_brain.process(symbol, signals, bars)
            action = str(brain_out.get("action", "hold")).lower()
            decision_map = {
                "strong_buy": "BUY",
                "buy": "BUY",
                "hold": "HOLD",
                "sell": "SELL",
                "strong_sell": "SELL",
            }
            brain_out["decision"] = decision_map.get(action, "HOLD")
            return brain_out
        except Exception as exc:
            logger.warning(f"Neural brain processing failed for {symbol}: {exc}")
            return {}

    def _build_option_snapshot(self, close_prices: List[float], features: Dict[str, Any]) -> Dict[str, Any]:
        if not close_prices:
            return {"available": False, "error": "no_prices"}
        spot = float(close_prices[-1])
        strike = spot
        sigma = max(0.05, float(features.get("realized_volatility", 0.20) or 0.20))
        maturity = 30.0 / 365.0
        rate = float(getattr(TradingConfig, "RISK_FREE_RATE", 0.05))
        call_price = self.options_engine.black_scholes(spot, strike, maturity, rate, sigma, "call")
        put_price = self.options_engine.black_scholes(spot, strike, maturity, rate, sigma, "put")
        greeks = self.options_engine.greeks(spot, strike, maturity, rate, sigma, "call")
        return {
            "available": True,
            "spot": spot,
            "strike": strike,
            "call_price": float(call_price),
            "put_price": float(put_price),
            "call_greeks": greeks,
        }

    def _build_quick_backtest(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        closes = [float(d.get("close", 0.0) or 0.0) for d in data if "close" in d]
        if len(closes) < 30:
            return {"status": "SKIPPED", "reason": "insufficient_bars"}
        bars = [{"close": c} for c in closes[-120:]]
        signals: List[str] = []
        for i in range(len(closes[-120:])):
            window = closes[max(0, len(closes) - 120 + i - 19): len(closes) - 120 + i + 1]
            if len(window) < 20:
                signals.append("HOLD")
                continue
            ma20 = float(np.mean(window[-20:]))
            price = float(window[-1])
            if price > ma20 * 1.002:
                signals.append("BUY")
            elif price < ma20 * 0.998:
                signals.append("SELL")
            else:
                signals.append("HOLD")
        result = self.quick_backtester.run(bars=bars, signals=signals, size_fraction=0.15)
        return {
            "status": result.get("status", "SKIPPED"),
            "total_return": float(result.get("total_return", 0.0) or 0.0),
            "max_drawdown": float(result.get("max_drawdown", 0.0) or 0.0),
            "sharpe": float(result.get("sharpe", 0.0) or 0.0),
            "trades": int(result.get("trades", 0) or 0),
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




















