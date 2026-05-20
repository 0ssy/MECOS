from loguru import logger
from typing import Dict, Any
from trading.config import TradingConfig

class RiskEngine:
    def __init__(self, memory_system):
        self.memory = memory_system
        logger.info("RiskEngine initialized.")

    async def evaluate_risk(self, proposed_trade: Dict, portfolio: Dict) -> Dict[str, Any]:
        logger.info(f"Evaluating risk for: {proposed_trade['symbol']}")
        
        # Drawdown check
        current_value = portfolio.get("total_value", 10000)
        initial_value = 10000 # Example starting value
        drawdown = (initial_value - current_value) / initial_value
        if drawdown > TradingConfig.MAX_DRAWDOWN:
            return {"action": "REJECT", "reason": "Max drawdown exceeded"}
            
        # Position size check
        notional = proposed_trade['size'] * proposed_trade['price']
        if notional > current_value * TradingConfig.MAX_POSITION_SIZE:
            return {"action": "REJECT", "reason": "Position too large"}
            
        return {"action": "APPROVE"}
