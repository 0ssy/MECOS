from __future__ import annotations

from typing import Dict, List


class RiskManager:
    """Position sizing, portfolio heat, and trade-permission checks."""

    def __init__(self, account_balance: float, max_risk_per_trade: float = 0.01):
        self.balance = max(float(account_balance), 1.0)
        self.max_risk_per_trade = max(0.0, min(0.20, float(max_risk_per_trade)))

    def position_size(self, entry: float, stop_loss: float) -> float:
        entry = float(entry)
        stop = float(stop_loss)
        risk_per_unit = abs(entry - stop)
        if risk_per_unit <= 0:
            return 0.0
        risk_amount = self.balance * self.max_risk_per_trade
        return float(max(0.0, risk_amount / risk_per_unit))

    def portfolio_heat(self, open_positions: List[Dict]) -> float:
        total_risk = 0.0
        for p in open_positions or []:
            if not isinstance(p, dict):
                continue
            if "risk_amount" in p:
                total_risk += float(p.get("risk_amount", 0.0) or 0.0)
                continue
            size = float(p.get("size", p.get("shares", 0.0)) or 0.0)
            entry = float(p.get("entry_price", p.get("avg_price", 0.0)) or 0.0)
            stop = float(p.get("stop_loss", entry) or entry)
            total_risk += abs(entry - stop) * max(size, 0.0)
        return float((total_risk / self.balance) * 100.0)

    def should_trade(self, open_positions: List[Dict], max_heat: float = 6.0) -> bool:
        return self.portfolio_heat(open_positions) < float(max_heat)

    @staticmethod
    def trailing_stop(current: float, atr: float, multiplier: float = 2.0) -> float:
        return float(current - (max(0.0, atr) * max(0.1, multiplier)))
