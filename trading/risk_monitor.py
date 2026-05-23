from typing import Dict, Any
from loguru import logger

class RiskMonitor:
    def __init__(self):
        self.max_daily_loss = 0.05
        self.max_total_drawdown = 0.10
        self.max_leverage = 3.0
        self.daily_pnl = 0
        self.peak_value = 10000
        logger.info('Risk Monitor initialized')

    async def check_risk_limits(self, portfolio: Dict) -> Dict[str, Any]:
        total_value = portfolio['total_value']
        
        if total_value > self.peak_value:
            self.peak_value = total_value
        
        drawdown = (self.peak_value - total_value) / self.peak_value
        
        if drawdown > self.max_total_drawdown:
            return {
                'breach': True,
                'reason': 'Max drawdown exceeded',
                'action': 'HALT_TRADING'
            }
        
        return {
            'breach': False,
            'drawdown': float(drawdown)
        }

    async def update_daily_pnl(self, pnl: float):
        self.daily_pnl += pnl

    def reset_daily(self):
        self.daily_pnl = 0
