import asyncio
from loguru import logger
from typing import List, Dict, Any
from memory_system import MemorySystem
from trading import *

class TradingAgent:
    def __init__(self, memory: MemorySystem):
        self.memory = memory
        self.regime_detector = RegimeDetectionAgent(memory)
        self.meta_orchestrator = MetaOrchestrator(memory)
        self.risk_engine = RiskEngine(memory)
        self.agents = {"trend": TrendAgent(memory), "options": OptionsPricingAgent(memory)}
        for n, a in self.agents.items(): self.meta_orchestrator.register_agent(n, a)
        self.paper_portfolio = {"cash": 10000.0, "positions": {}, "total_value": 10000.0}
        self.stats = {
            "analyses": 0,
            "actionable_signals": 0,
            "risk_rejections": 0,
        }
        logger.info("Advanced TradingAgent initialized.")

    async def analyze_market(self, symbol: str, data: List[Dict]) -> Dict[str, Any]:
        self.stats["analyses"] += 1
        regime = await self.regime_detector.detect_regime(data)
        res = await self.meta_orchestrator.orchestrate_signals(data, regime)
        if res["final_decision"] != "HOLD":
            trade = {"symbol": symbol, "side": res["final_decision"], "size": 1.0, "price": data[-1]["close"]}
            risk = await self.risk_engine.evaluate_risk(trade, self.paper_portfolio)
            if risk["action"] == "REJECT":
                self.stats["risk_rejections"] += 1
                res["final_decision"] = "HOLD"
            else:
                self.stats["actionable_signals"] += 1
        await self.memory.add_experience(
            f"TRADING ANALYSIS: symbol={symbol}, decision={res.get('final_decision', 'HOLD')}",
            source="trading_agent",
        )
        return res

    def get_performance_metrics(self) -> Dict[str, Any]:
        analyses = max(self.stats["analyses"], 1)
        actionable_rate = self.stats["actionable_signals"] / analyses
        return {
            **self.stats,
            "actionable_rate": actionable_rate,
        }
