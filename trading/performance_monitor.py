import numpy as np
from typing import Dict, List, Any
from loguru import logger

class PerformanceMonitor:
    def __init__(self, database):
        self.database = database
        self.equity_curve = []
        logger.info('Performance Monitor initialized')

    async def update(self, portfolio_value: float):
        self.equity_curve.append(portfolio_value)

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
            'total_trades': len(self.equity_curve)
        }
