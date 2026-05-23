from typing import Dict, Any
from loguru import logger
import numpy as np
import inspect

class MetaOrchestrator:
    def __init__(self, memory):
        self.memory = memory
        self.agents = {}
        logger.info("Meta Orchestrator initialized")

    def register_agent(self, name: str, agent):
        self.agents[name] = agent

    async def orchestrate_signals(self, data, regime: str) -> Dict[str, Any]:

        buy_score = 0
        sell_score = 0
        hold_score = 0

        collected = {}

        for name, agent in self.agents.items():

            try:
                analyze_params = len(inspect.signature(agent.analyze).parameters)
                if analyze_params >= 3:
                    result = await agent.analyze(data, {}, {})
                elif analyze_params == 2:
                    result = await agent.analyze(data, {})
                else:
                    result = await agent.analyze(data)

                collected[name] = result

                signal = result.get("signal", "HOLD")
                confidence = result.get("confidence", 0)

                if signal in ["BUY", "BUY_VOL"]:
                    buy_score += confidence

                elif signal in ["SELL", "SELL_VOL"]:
                    sell_score += confidence

                else:
                    hold_score += confidence

            except Exception as e:
                logger.error(f"{name} failed: {e}")

        total = buy_score + sell_score + hold_score

        if total <= 0:
            final_decision = "HOLD"
            confidence = 0

        else:
            if buy_score > sell_score and buy_score > hold_score:
                final_decision = "BUY"
                confidence = buy_score / total

            elif sell_score > buy_score and sell_score > hold_score:
                final_decision = "SELL"
                confidence = sell_score / total

            else:
                final_decision = "HOLD"
                confidence = hold_score / total

        return {
            "final_decision": final_decision,
            "confidence": float(confidence),
            "regime": regime,
            "agent_signals": collected,
            "buy_score": float(buy_score),
            "sell_score": float(sell_score),
            "hold_score": float(hold_score)
        }
