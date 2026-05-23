from loguru import logger
from typing import Dict, Any, List

class RiskEngine:
    def __init__(self, memory_system, max_drawdown=0.1, max_leverage=3.0):
        self.memory = memory_system
        self.max_drawdown, self.max_leverage = max_drawdown, max_leverage
        self.current_drawdown = 0.0

    async def evaluate_risk(self, proposed_trade: Dict, portfolio: Dict) -> Dict[str, Any]:
        cash, price = portfolio.get("cash", 0), proposed_trade.get("price", 0)
        notional = proposed_trade.get("size", 0) * price
        
        if proposed_trade.get("side") == "BUY" and notional > cash:
            if cash <= 0: return {"action": "REJECT", "reason": "Insufficient buying power"}
            return {"action": "ADJUST", "new_size": cash / price, "reason": "Insufficient buying power"}

        # ... (rest of the drawdown and leverage checks) ...
        return {"action": "APPROVE"}
