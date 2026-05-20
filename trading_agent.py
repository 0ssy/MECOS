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
        logger.info("Advanced TradingAgent initialized.")

    async def analyze_market(self, symbol: str, data: List[Dict]) -> Dict[str, Any]:
        regime = await self.regime_detector.detect_regime(data)
        res = await self.meta_orchestrator.orchestrate_signals(data, regime)
        if res["final_decision"] != "HOLD":
            trade = {"symbol": symbol, "side": res["final_decision"], "size": 1.0, "price": data[-1]["close"]}
            risk = await self.risk_engine.evaluate_risk(trade, self.paper_portfolio)
            if risk["action"] == "REJECT": res["final_decision"] = "HOLD"
        return res
