from __future__ import annotations

from typing import Any, Dict, Iterable, List

import numpy as np


class SimpleBacktester:
    """Deterministic bar-by-bar backtester for BUY/SELL/HOLD signals."""

    def __init__(self, initial_cash: float = 10_000.0, fee_bps: float = 5.0):
        self.initial_cash = float(initial_cash)
        self.fee_rate = max(float(fee_bps), 0.0) / 10_000.0

    def run(self, bars: Iterable[Dict[str, Any]], signals: Iterable[str], size_fraction: float = 0.1) -> Dict[str, Any]:
        bar_list: List[Dict[str, Any]] = list(bars or [])
        signal_list: List[str] = [str(s).upper() for s in signals or []]
        if not bar_list or not signal_list:
            return {"status": "SKIPPED", "reason": "no_data", "equity_curve": []}

        n = min(len(bar_list), len(signal_list))
        cash = self.initial_cash
        units = 0.0
        equity_curve: List[float] = []
        trades = 0

        for i in range(n):
            close = float(bar_list[i].get("close", 0.0) or 0.0)
            if close <= 0.0:
                equity_curve.append(cash + units * max(close, 0.0))
                continue
            signal = signal_list[i]
            alloc_cash = cash * max(0.0, min(1.0, float(size_fraction)))

            if signal == "BUY" and alloc_cash > 1.0:
                qty = alloc_cash / close
                gross = qty * close
                fee = gross * self.fee_rate
                total = gross + fee
                if total <= cash:
                    cash -= total
                    units += qty
                    trades += 1
            elif signal == "SELL" and units > 0.0:
                gross = units * close
                fee = gross * self.fee_rate
                cash += gross - fee
                units = 0.0
                trades += 1

            equity_curve.append(cash + units * close)

        if not equity_curve:
            return {"status": "SKIPPED", "reason": "no_equity_points", "equity_curve": []}

        equity = np.asarray(equity_curve, dtype=float)
        returns = np.diff(equity) / np.maximum(equity[:-1], 1e-9) if equity.size > 1 else np.asarray([], dtype=float)
        total_return = float(equity[-1] / max(self.initial_cash, 1e-9) - 1.0)
        running_max = np.maximum.accumulate(equity)
        drawdown = (equity - running_max) / np.maximum(running_max, 1e-9)
        max_dd = float(np.min(drawdown)) if drawdown.size else 0.0
        sharpe = 0.0
        if returns.size > 1 and float(np.std(returns)) > 0:
            sharpe = float(np.mean(returns) / np.std(returns) * np.sqrt(252.0))

        return {
            "status": "OK",
            "initial_cash": self.initial_cash,
            "final_equity": float(equity[-1]),
            "total_return": total_return,
            "max_drawdown": max_dd,
            "sharpe": sharpe,
            "trades": int(trades),
            "equity_curve": [float(x) for x in equity_curve],
        }
