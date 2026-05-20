import asyncio
from loguru import logger
from typing import Dict, Any, List
from trading.config import TradingConfig

class MetaOrchestrator:
    def __init__(self, memory_system):
        self.memory = memory_system
        self.agents = {}
        logger.info("MetaOrchestrator initialized.")

    def register_agent(self, name, instance): self.agents[name] = instance

    async def orchestrate_signals(self, data, regime):
        logger.info(f"Orchestrating for: {regime}")
        sigs = {}
        if regime == "trending" and "trend" in self.agents: sigs["trend"] = await self.agents["trend"].analyze_trend(data)
        
        buy, sell, conf = 0, 0, 0
        for name, res in sigs.items():
            weight = TradingConfig.SIGNAL_WEIGHTS.get(name, 1.0)
            c = res.get("confidence", 0.5) * weight
            if res.get("signal") == "BUY": buy += c
            elif res.get("signal") == "SELL": sell += c
            conf += c
        
        ratio = max(buy, sell) / conf if conf > 0 else 0
        dec = "BUY" if buy > sell and ratio > TradingConfig.MIN_CONFIDENCE else "SELL" if sell > buy and ratio > TradingConfig.MIN_CONFIDENCE else "HOLD"
        return {"final_decision": dec, "regime": regime, "confidence": round(ratio, 2), "agent_signals": sigs}
