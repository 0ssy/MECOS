from typing import Dict, Any
from loguru import logger
from trading.config import TradingConfig

class RiskEngine:
    def __init__(self, memory):
        self.memory = memory

        self.max_drawdown = float(getattr(TradingConfig, "MAX_DRAWDOWN", 0.10))
        self.max_position_size = float(getattr(TradingConfig, "MAX_POSITION_SIZE", 0.40))
        self.max_leverage = float(getattr(TradingConfig, "MAX_LEVERAGE", 3.0))
        self.daily_loss_limit = float(getattr(TradingConfig, "MAX_DAILY_LOSS", 0.03))
        self.max_open_trades = int(getattr(TradingConfig, "MAX_OPEN_TRADES", 10))
        self.max_total_exposure = float(getattr(TradingConfig, "MAX_TOTAL_EXPOSURE", 3.0))

        logger.info("Risk Engine initialized")

    async def evaluate_risk(self,
                            proposed_trade: Dict,
                            portfolio: Dict) -> Dict[str, Any]:

        total_value = float(portfolio.get("total_value", 10000) or 10000)
        cash = float(portfolio.get("cash", total_value) or total_value)
        buying_power = float(portfolio.get("buying_power", cash) or cash)
        daily_pnl = float(portfolio.get("daily_pnl", 0.0) or 0.0)
        positions = portfolio.get("positions", {})
        if not isinstance(positions, dict):
            positions = {}

        price = float(proposed_trade.get("price", 0.0) or 0.0)
        size = float(proposed_trade.get("size", 0.0) or 0.0)
        symbol = str(proposed_trade.get("symbol", "") or "").upper()
        side = str(proposed_trade.get("side", "BUY") or "BUY").upper()
        if price <= 0.0 or size <= 0.0:
            return {
                "action": "REJECT",
                "reason": "Invalid trade price or size"
            }

        if daily_pnl <= -abs(total_value * self.daily_loss_limit):
            return {
                "action": "REJECT",
                "reason": "Daily loss limit reached"
            }

        is_new_position = symbol and symbol not in positions
        if side == "BUY" and is_new_position and len(positions) >= self.max_open_trades:
            return {
                "action": "REJECT",
                "reason": f"Max open trades reached ({self.max_open_trades})"
            }

        notional = price * size
        max_notional_position = max(total_value * self.max_position_size, 0.0)
        available_capital = max(buying_power, 0.0)
        max_notional_leverage = available_capital * self.max_leverage
        allowed_notional = min(max_notional_position, max_notional_leverage)

        current_exposure_notional = 0.0
        for pos in positions.values():
            if not isinstance(pos, dict):
                continue
            pos_value = float(pos.get("value", 0.0) or 0.0)
            if pos_value > 0.0:
                current_exposure_notional += pos_value
                continue
            pos_size = float(pos.get("size", pos.get("shares", 0.0)) or 0.0)
            pos_price = float(pos.get("price", pos.get("avg_price", price)) or price)
            current_exposure_notional += max(0.0, pos_size * pos_price)
        proposed_total_exposure = (current_exposure_notional + max(notional, 0.0)) / max(total_value, 1.0)
        if proposed_total_exposure > self.max_total_exposure:
            return {
                "action": "REJECT",
                "reason": (
                    f"Total exposure limit exceeded ({proposed_total_exposure:.2f} > "
                    f"{self.max_total_exposure:.2f})"
                ),
            }

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
