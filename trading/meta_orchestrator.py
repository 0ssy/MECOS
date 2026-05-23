from typing import Dict, Any, List
import inspect
from loguru import logger


class MetaOrchestrator:
    def __init__(self, memory):
        self.memory = memory
        self.agents: Dict[str, Any] = {}
        logger.info("Meta Orchestrator initialized")

    def register_agent(self, name: str, agent):
        self.agents[name] = agent

    async def _run_agent(
        self,
        name: str,
        agent: Any,
        asset_data: Any,
        features: Dict[str, Any],
        physics: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            params: List[str] = list(inspect.signature(agent.analyze).parameters.keys())
            if len(params) >= 3:
                result = await agent.analyze(asset_data, features, physics)
            elif len(params) == 2:
                second = params[1].lower()
                if second in {"features", "feature", "context"}:
                    result = await agent.analyze(asset_data, features)
                else:
                    result = await agent.analyze(asset_data, {})
            else:
                result = await agent.analyze(asset_data)
        except Exception as exc:
            logger.error(f"{name} failed: {exc}")
            return {"signal": "HOLD", "confidence": 0.0, "error": str(exc)}

        if not isinstance(result, dict):
            return {"signal": "HOLD", "confidence": 0.0, "raw_result": str(result)}
        return result

    async def orchestrate_signals(
        self,
        data: Any,
        regime: str,
        features: Dict[str, Any] = None,
        physics: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        features = features or {}
        physics = physics or {}

        buy_score = 0.0
        sell_score = 0.0
        hold_score = 0.0
        collected: Dict[str, Dict[str, Any]] = {}

        for name, agent in self.agents.items():
            result = await self._run_agent(name, agent, data, features, physics)
            collected[name] = result
            signal = str(result.get("signal", "HOLD")).upper()
            confidence = float(result.get("confidence", 0.0))

            if signal in {"BUY", "BUY_VOL", "BUY_SPREAD"}:
                buy_score += confidence
            elif signal in {"SELL", "SELL_VOL", "SELL_SPREAD"}:
                sell_score += confidence
            else:
                hold_score += confidence

        total = buy_score + sell_score + hold_score
        if total <= 0:
            final_decision = "HOLD"
            confidence = 0.0
        elif buy_score >= sell_score and buy_score >= hold_score:
            final_decision = "BUY"
            confidence = buy_score / total
        elif sell_score >= buy_score and sell_score >= hold_score:
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
            "hold_score": float(hold_score),
        }
