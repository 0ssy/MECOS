from typing import Dict, Any
from loguru import logger

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

        total_value = float(portfolio.get("total_value", 10000) or 10000)
        cash = float(portfolio.get("cash", total_value) or total_value)
        buying_power = float(portfolio.get("buying_power", cash) or cash)

        price = float(proposed_trade.get("price", 0.0) or 0.0)
        size = float(proposed_trade.get("size", 0.0) or 0.0)
        if price <= 0.0 or size <= 0.0:
            return {
                "action": "REJECT",
                "reason": "Invalid trade price or size"
            }

        notional = price * size
        max_notional_position = max(total_value * self.max_position_size, 0.0)
        available_capital = max(buying_power, 0.0)
        max_notional_leverage = available_capital * self.max_leverage
        allowed_notional = min(max_notional_position, max_notional_leverage)

        if allowed_notional <= 0.0:
            return {
                "action": "REJECT",
                "reason": "Insufficient buying power"
            }

        if notional > allowed_notional:
            new_size = allowed_notional / price
            if new_size < 0.01:
                return {
                    "action": "REJECT",
                    "reason": "Position size below minimum after risk adjustment"
                }
            return {
                "action": "ADJUST",
                "reason": (
                    f"Position capped by risk limits "
                    f"(max_notional={allowed_notional:.2f})"
                ),
                "new_size": float(new_size)
            }

        return {
            "action": "APPROVE",
            "risk_score": float(notional / max(total_value, 1.0))
        }
