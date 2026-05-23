import asyncio
from loguru import logger
from typing import Dict, Any, List

class MetaOrchestrator:
    def __init__(self, memory_system):
        self.memory = memory_system
        self.agents = {}
        logger.info("MetaOrchestrator initialized.")

    def register_agent(self, name: str, agent_instance: Any):
        self.agents[name] = agent_instance

    async def orchestrate_signals(self, market_data: List[Dict], regime: str) -> Dict[str, Any]:
        logger.info(f"Orchestrating unified consensus for regime: {regime}")
        signals = {}
        tasks = []
        agent_names = list(self.agents.keys())
        
        for name in agent_names:
            agent = self.agents[name]
            if hasattr(agent, "analyze_trend"): tasks.append(agent.analyze_trend(market_data))
            elif hasattr(agent, "analyze_mean_reversion"): tasks.append(agent.analyze_mean_reversion(market_data))
            elif hasattr(agent, "analyze_volatility"): tasks.append(agent.analyze_volatility(market_data))
            elif hasattr(agent, "analyze_sentiment"): tasks.append(agent.analyze_sentiment(market_data))
            elif hasattr(agent, "analyze_order_flow"): tasks.append(agent.analyze_order_flow(market_data))
            elif hasattr(agent, "find_liquidity"): tasks.append(agent.find_liquidity(market_data))
            elif hasattr(agent, "find_arbitrage"): tasks.append(agent.find_arbitrage({"market": market_data}))
            elif hasattr(agent, "price_options"): tasks.append(agent.price_options({"S": market_data[-1]["close"], "K": market_data[-1]["close"], "T": 30/365, "sigma": 0.2}))
            elif hasattr(agent, "optimize"): tasks.append(agent.optimize(market_data))
            else: tasks.append(asyncio.sleep(0, result={}))

        results = await asyncio.gather(*tasks)
        for name, res in zip(agent_names, results): signals[name] = res

        buy_score = sell_score = confidence_sum = 0
        for name, res in signals.items():
            signal, confidence = res.get("signal", "HOLD"), res.get("confidence", 0.5)
            weight = 1.0
            if regime == "trending": weight = 2.0 if name == "trend" else 0.5 if name == "mean_reversion" else 1.0
            elif regime in ["mean_reverting", "ranging"]: weight = 2.0 if name == "mean_reversion" else 0.5 if name == "trend" else 1.0
            
            weighted_conf = confidence * weight
            if signal == "BUY": buy_score += weighted_conf
            elif signal == "SELL": sell_score += weighted_conf
            confidence_sum += weighted_conf

        final_decision = "HOLD"
        consensus_conf = round(max(buy_score, sell_score) / confidence_sum, 2) if confidence_sum > 0 else 0
        if buy_score > sell_score and consensus_conf > 0.6: final_decision = "BUY"
        elif sell_score > buy_score and consensus_conf > 0.6: final_decision = "SELL"

        return {"final_decision": final_decision, "regime": regime, "confidence": consensus_conf, "agent_signals": signals}
