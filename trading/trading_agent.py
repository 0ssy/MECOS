import asyncio
from loguru import logger
from typing import List, Dict, Any
from memory_system import MemorySystem
from trading import *

class TradingAgent:
    def __init__(self, memory: MemorySystem):
        self.memory = memory
        
        # INSTITUTIONAL ENGINES
        self.feature_engine = FeatureEngine(memory)
        self.physics_engine = MarketPhysicsEngine(memory)
        self.portfolio_engine = PortfolioEngine(memory)
        self.execution_engine = ExecutionEngine(memory)
        
        # Existing components
        self.regime_detector = RegimeDetectionAgent(memory)
        self.meta_orchestrator = MetaOrchestrator(memory)
        self.risk_engine = RiskEngine(memory)
        
        # EXPANDED AGENT SUITE
        self.agents = {
            "trend": TrendAgent(memory),
            "options": OptionsPricingAgent(memory),
            "mean_reversion": MeanReversionAgent(memory),
            "volatility": VolatilityArbitrageAgent(memory),
            "liquidity": LiquidityHunterAgent(memory),
            "sentiment": SentimentAgent(memory)
        }
        
        # Register all agents
        for name, agent in self.agents.items():
            self.meta_orchestrator.register_agent(name, agent)
        
        # Portfolio
        self.paper_portfolio = {
            "cash": 10000.0,
            "positions": {},
            "total_value": 10000.0
        }
        
        # Statistics
        self.stats = {
            "analyses": 0,
            "actionable_signals": 0,
            "risk_rejections": 0,
            "total_pnl": 0,
            "win_rate": 0
        }
        
        logger.info("INSTITUTIONAL QUANT TRADING AGENT INITIALIZED")
        logger.info(f"    Engines: Feature, Physics, Portfolio, Execution")
        logger.info(f"    Agents: {len(self.agents)} specialist strategies")

    async def analyze_market(self, symbol: str, data: List[Dict]) -> Dict[str, Any]:
        """COMPLETE INSTITUTIONAL ANALYSIS PIPELINE"""
        self.stats["analyses"] += 1
        
        logger.info(f" Analyzing {symbol}...")
        if not data:
            logger.warning(f"   No market data for {symbol}, holding.")
            return {
                "final_decision": "HOLD",
                "confidence": 0.0,
                "reason": "no_market_data"
            }

        valid_data = [bar for bar in data if isinstance(bar, dict) and "close" in bar]
        if not valid_data:
            logger.warning(f"   Market data missing close prices for {symbol}, holding.")
            return {
                "final_decision": "HOLD",
                "confidence": 0.0,
                "reason": "invalid_market_data"
            }
        data = valid_data
        
        # STEP 1: FEATURE ENGINEERING
        features = await self.feature_engine.compute_features(data)
        logger.debug(f"   Vol: {features.get('realized_volatility', 0):.3f} | "
                    f"Momentum: {features.get('roc_20', 0):.2%} | "
                    f"Liquidity: {features.get('liquidity_score', 0):.2f}")
        
        # STEP 2: MARKET PHYSICS
        physics = await self.physics_engine.analyze(symbol, data, features)
        logger.debug(f"   Expected Return: {physics['monte_carlo']['expected_return']:.2%} | "
                    f"Tail Risk: {physics['tail_risk']['tail_risk_score']:.3f}")
        
        # STEP 3: REGIME DETECTION
        regime = await self.regime_detector.detect_regime(data)
        
        # STEP 4: MULTI-AGENT SIGNAL ORCHESTRATION
        signals = await self.meta_orchestrator.orchestrate_signals(data, regime)
        
        # Add specialist signals
        signals['mean_reversion'] = await self.agents['mean_reversion'].analyze(data, features)
        signals['volatility'] = await self.agents['volatility'].analyze(data, features, physics)
        signals['liquidity'] = await self.agents['liquidity'].analyze(data, features)
        signals['sentiment'] = await self.agents['sentiment'].analyze(data, features)
        
        logger.debug(f"   Signals: Trend={signals.get('trend', {}).get('signal', 'N/A')} | "
                    f"MeanRev={signals['mean_reversion']['signal']} | "
                    f"Sentiment={signals['sentiment']['sentiment']}")
        
        # STEP 5: PORTFOLIO OPTIMIZATION
        if signals["final_decision"] != "HOLD":
            signal_strength = signals.get('confidence', 0.5)
            volatility = features.get('realized_volatility', 0.3)
            
            position_size = await self.portfolio_engine.optimize_position_size(
                signal_strength,
                self.paper_portfolio,
                volatility
            )
            
            trade = {
                "symbol": symbol,
                "side": signals["final_decision"],
                "size": position_size,
                "price": data[-1]["close"]
            }
            
            # STEP 6: EXECUTION PLANNING
            execution_plan = await self.execution_engine.plan_execution(
                trade,
                {
                    'volume_ratio': features.get('volume_ratio', 1.0),
                    'spread_pressure': features.get('spread_pressure', 0.001)
                }
            )
            
            # STEP 7: RISK VALIDATION
            risk = await self.risk_engine.evaluate_risk(trade, self.paper_portfolio)
            
            if risk["action"] == "REJECT":
                self.stats["risk_rejections"] += 1
                signals["final_decision"] = "HOLD"
                logger.warning(f"   ⚠️ TRADE REJECTED: {risk.get('reason', 'Risk limit')}")
            else:
                self.stats["actionable_signals"] += 1
                logger.info(f"   ✅ TRADE APPROVED: {trade['side']} {position_size:.1%} @ {trade['price']}")
                logger.info(f"      Execution: {execution_plan['strategy']} | "
                           f"Slippage: {execution_plan['estimated_slippage_bps']:.1f} bps")
                
                signals['execution_plan'] = execution_plan;

                signals['position_size'] = position_size;
        
        # STEP 8: PORTFOLIO METRICS
        portfolio_metrics = await self.portfolio_engine.calculate_portfolio_metrics(
            self.paper_portfolio
        )
        
        # Comprehensive logging
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
                "portfolio": portfolio_metrics
            }
        )
        
        return {
            **signals,
            "features": features,
            "physics": physics,
            "portfolio": portfolio_metrics
        }

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Enhanced performance metrics"""
        analyses = max(self.stats["analyses"], 1)
        actionable_rate = self.stats["actionable_signals"] / analyses
        
        return {
            **self.stats,
            "actionable_rate": actionable_rate,
            "sharpe_ratio": 0,  # Calculate from trade history
            "max_drawdown": 0,
            "portfolio_value": self.paper_portfolio["total_value"]
        }
