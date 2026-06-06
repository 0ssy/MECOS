import asyncio
from typing import Dict, Any, List, Tuple
import inspect
from loguru import logger
from trading.config import TradingConfig


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
        symbol: str = "",
    ) -> Dict[str, Any]:
        try:
            params: List[str] = list(inspect.signature(agent.analyze).parameters.keys())
            signature = inspect.signature(agent.analyze)
            kwargs = {}
            if "symbol" in signature.parameters and symbol:
                kwargs["symbol"] = symbol

            if len(params) >= 3:
                result = await agent.analyze(asset_data, features, physics, **kwargs)
            elif len(params) == 2:
                second = params[1].lower()
                if second in {"features", "feature", "context"}:
                    result = await agent.analyze(asset_data, features, **kwargs)
                else:
                    result = await agent.analyze(asset_data, {}, **kwargs)
            else:
                result = await agent.analyze(asset_data, **kwargs)
        except Exception as exc:
            logger.error(f"{name} failed: {exc}")
            return {"signal": "HOLD", "confidence": 0.0, "error": str(exc)}

        if not isinstance(result, dict):
            return {"signal": "HOLD", "confidence": 0.0, "raw_result": str(result)}
        return result

    def _normalize_market_data(self, data: Any) -> Dict[str, Any]:
        if isinstance(data, dict):
            return data
        return {"primary": data}

    def _agent_weight(self, agent_name: str) -> float:
        # Use base agent name so keys like "trend:BTCUSD" still map correctly.
        base_name = agent_name.split(":", 1)[0]
        return float(TradingConfig.SIGNAL_WEIGHTS.get(base_name, 1.0))

    async def _run_named_agent(
        self,
        name: str,
        agent: Any,
        asset_data: Any,
        features: Dict[str, Any],
        physics: Dict[str, Any],
        symbol: str,
    ) -> Tuple[str, Dict[str, Any]]:
        key = name if symbol == "primary" else f"{name}:{symbol}"
        result = await self._run_agent(name, agent, asset_data, features, physics, symbol=symbol)
        return key, result

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
        total_weight = 0.0
        collected: Dict[str, Dict[str, Any]] = {}
        market_data = self._normalize_market_data(data)
        symbols = list(market_data.keys())
        tasks = []

        for name, agent in self.agents.items():
            if not hasattr(agent, "analyze"):
                logger.warning(f"Agent {name} does not have an 'analyze' method.")
                continue

            if "statistical_arbitrage" in name and len(symbols) >= 2:
                pair_data = {
                    symbols[0]: market_data[symbols[0]],
                    symbols[1]: market_data[symbols[1]],
                }
                pair_symbol = f"{symbols[0]}:{symbols[1]}"
                tasks.append(self._run_named_agent(name, agent, pair_data, features, physics, pair_symbol))
                continue

            for symbol, asset_data in market_data.items():
                tasks.append(self._run_named_agent(name, agent, asset_data, features, physics, symbol))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in results:
            if isinstance(res, Exception):
                logger.error(f"Agent analysis failed: {res}")
                continue

            signal_key, signal_data = res
            if not isinstance(signal_data, dict):
                signal_data = {"signal": "HOLD", "confidence": 0.0, "raw_result": str(signal_data)}

            collected[signal_key] = signal_data

            signal = str(signal_data.get("signal", "HOLD")).upper()
            confidence = float(signal_data.get("confidence", 0.0))
            weight = self._agent_weight(signal_key)

            if signal in {"BUY", "BUY_VOL", "BUY_SPREAD"}:
                buy_score += confidence * weight
            elif signal in {"SELL", "SELL_VOL", "SELL_SPREAD"}:
                sell_score += confidence * weight
            else:
                hold_score += confidence * weight
            total_weight += weight

        if total_weight > 0 and buy_score > sell_score:
            consensus_confidence = buy_score / total_weight
        elif total_weight > 0 and sell_score > buy_score:
            consensus_confidence = sell_score / total_weight
        else:
            consensus_confidence = 0.0
        final_decision = "HOLD"
        if buy_score > sell_score and consensus_confidence >= TradingConfig.MIN_CONFIDENCE:
            final_decision = "BUY"
        elif sell_score > buy_score and consensus_confidence >= TradingConfig.MIN_CONFIDENCE:
            final_decision = "SELL"

        logger.info(
            f"MetaOrchestrator Decision: {final_decision} with Confidence: {consensus_confidence:.2f}"
        )

        return {
            "final_decision": final_decision,
            "confidence": float(consensus_confidence),
            "regime": regime,
            "agent_signals": collected,
            "buy_score": float(buy_score),
            "sell_score": float(sell_score),
            "hold_score": float(hold_score),
            "total_weight": float(total_weight),
        }


