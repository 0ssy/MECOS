# trading/pnl_engine.py
import numpy as np
from typing import List


class PnLEngine:
    def __init__(self):
        self.realized_pnl   = 0.0
        self.unrealized_pnl = 0.0
        self._trade_returns: List[float] = []   # per-trade % returns
        self._wins  = 0
        self._total = 0

    def update_realized(self, pnl: float):
        """Call after each trade closes with the PnL amount."""
        pnl = float(pnl or 0.0)
        self.realized_pnl += pnl
        self._total += 1
        if pnl > 0:
            self._wins += 1

    def record_trade_return(self, entry_price: float, exit_price: float, side: str = "BUY"):
        """Record a percentage return for Sharpe calculation."""
        if entry_price <= 0:
            return
        ret = (exit_price - entry_price) / entry_price
        if str(side).upper() == "SELL":
            ret = -ret
        self._trade_returns.append(float(ret))
        if len(self._trade_returns) > 500:
            self._trade_returns = self._trade_returns[-500:]

    def update_unrealized(self, positions: dict, prices: dict):
        total = 0.0
        for sym, pos in (positions or {}).items():
            if sym not in (prices or {}):
                continue
            size  = float(pos.get("size", 0.0) or 0.0)
            entry = float(pos.get("entry", pos.get("avg_price", 0.0)) or 0.0)
            mark  = float(prices.get(sym, 0.0) or 0.0)
            if size == 0.0 or entry <= 0.0 or mark <= 0.0:
                continue
            total += size * (mark - entry)
        self.unrealized_pnl = float(total)

    def total_pnl(self) -> float:
        return float(self.realized_pnl + self.unrealized_pnl)

    def sharpe_ratio(self, periods_per_year: int = 252) -> float:
        """Annualised Sharpe ratio from per-trade returns."""
        if len(self._trade_returns) < 5:
            return 0.0
        arr  = np.array(self._trade_returns)
        mean = np.mean(arr)
        std  = np.std(arr)
        if std < 1e-9:
            return 0.0
        return float((mean / std) * np.sqrt(periods_per_year))

    def win_rate(self) -> float:
        return float(self._wins / self._total) if self._total > 0 else 0.0

    def profit_factor(self) -> float:
        gross_profit = sum(r for r in self._trade_returns if r > 0)
        gross_loss   = abs(sum(r for r in self._trade_returns if r < 0))
        return float(gross_profit / gross_loss) if gross_loss > 1e-9 else 0.0

    def summary(self) -> dict:
        return {
            "realized_pnl":   round(self.realized_pnl, 4),
            "unrealized_pnl": round(self.unrealized_pnl, 4),
            "total_pnl":      round(self.total_pnl(), 4),
            "sharpe":         round(self.sharpe_ratio(), 3),
            "win_rate":       round(self.win_rate(), 3),
            "profit_factor":  round(self.profit_factor(), 3),
            "total_trades":   self._total,
        }
