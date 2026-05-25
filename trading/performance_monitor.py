import numpy as np
from typing import Dict, List, Any
from loguru import logger

class PerformanceMonitor:
    def __init__(self, database):
        self.database = database
        self.equity_curve = []
        self.closed_trade_pnls: List[float] = []
        self.holding_times: List[float] = []
        logger.info('Performance Monitor initialized')

    async def update(self, portfolio_value: float):
        self.equity_curve.append(portfolio_value)

    def record_trade_close(self, pnl: float, holding_seconds: float = 0.0):
        self.closed_trade_pnls.append(float(pnl))
        self.holding_times.append(float(max(0.0, holding_seconds)))

    def calculate_win_rate(self) -> float:
        if not self.closed_trade_pnls:
            return 0.0
        wins = sum(1 for pnl in self.closed_trade_pnls if pnl > 0)
        return float(wins / len(self.closed_trade_pnls))

    def calculate_profit_factor(self) -> float:
        if not self.closed_trade_pnls:
            return 0.0
        gross_profit = sum(p for p in self.closed_trade_pnls if p > 0)
        gross_loss = abs(sum(p for p in self.closed_trade_pnls if p < 0))
        if gross_loss == 0:
            return float(gross_profit) if gross_profit > 0 else 0.0
        return float(gross_profit / gross_loss)

    def calculate_average_holding_time(self) -> float:
        if not self.holding_times:
            return 0.0
        return float(np.mean(self.holding_times))

    def calculate_sharpe_ratio(self) -> float:
        if len(self.equity_curve) < 2:
            return 0
        
        returns = np.diff(self.equity_curve) / np.maximum(self.equity_curve[:-1], 1)
        
        if len(returns) == 0 or np.std(returns) == 0:
            return 0
        
        sharpe = (np.mean(returns) / np.std(returns)) * np.sqrt(252)
        return float(sharpe)

    def calculate_max_drawdown(self) -> float:
        if len(self.equity_curve) < 2:
            return 0
        
        equity = np.array(self.equity_curve)
        running_max = np.maximum.accumulate(equity)
        drawdown = (equity - running_max) / running_max
        
        return float(np.min(drawdown))

    def calculate_sortino_ratio(self) -> float:
        if len(self.equity_curve) < 2:
            return 0
        
        returns = np.diff(self.equity_curve) / np.maximum(self.equity_curve[:-1], 1)
        
        downside_returns = returns[returns < 0]
        
        if len(downside_returns) == 0:
            return 0
        
        downside_std = np.std(downside_returns)
        
        if downside_std == 0:
            return 0
        
        sortino = (np.mean(returns) / downside_std) * np.sqrt(252)
        return float(sortino)

    def get_metrics(self) -> Dict[str, Any]:
        return {
            'sharpe_ratio': self.calculate_sharpe_ratio(),
            'max_drawdown': self.calculate_max_drawdown(),
            'sortino_ratio': self.calculate_sortino_ratio(),
            'total_trades': len(self.closed_trade_pnls),
            'win_rate': self.calculate_win_rate(),
            'profit_factor': self.calculate_profit_factor(),
            'avg_holding_seconds': self.calculate_average_holding_time(),
        }
