from typing import Dict, Any
from loguru import logger
import numpy as np

class RiskEngine:
    def __init__(self, memory):
        self.memory = memory

        self.max_drawdown = 0.10
        self.max_position_size = 0.40
        self.max_leverage = 3.0
        self.daily_loss_limit = 0.03

        logger.info("Risk Engine initialized")

    async def evaluate_risk(self,
                            proposed_trade: Dict,
                            portfolio: Dict) -> Dict[str, Any]:

        total_value = portfolio.get("total_value", 10000)
        cash = portfolio.get("cash", total_value)

        price = proposed_trade["price"]
        size = proposed_trade["size"]

        notional = price * size

        if notional > total_value * self.max_position_size:
            return {
                "action": "REJECT",
                "reason": "Position size exceeded"
            }

        leverage = notional / max(cash, 1)

        if leverage > self.max_leverage:
            return {
                "action": "REJECT",
                "reason": "Leverage exceeded"
            }

        return {
            "action": "APPROVE",
            "risk_score": float(notional / total_value)
        }
