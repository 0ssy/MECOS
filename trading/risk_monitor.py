from typing import Dict, Any
from loguru import logger

from .asset_profiles import infer_market

class RiskMonitor:
    def __init__(self):
        self.max_daily_loss = 0.03
        self.max_total_drawdown = 0.10
        self.max_leverage = 3.0

        self.max_total_exposure = 0.80
        self.max_single_position = 0.10
        self.max_crypto_exposure = 0.25
        self.max_open_trades = 10

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

        if self.peak_value > 0:
            daily_loss_ratio = max(0.0, -self.daily_pnl / self.peak_value)
            if daily_loss_ratio > self.max_daily_loss:
                return {
                    'breach': True,
                    'reason': 'Max daily loss exceeded',
                    'action': 'HALT_TRADING'
                }
        
        return {
            'breach': False,
            'drawdown': float(drawdown)
        }

    async def check_order_risk(self,
                               portfolio: Dict,
                               symbol: str,
                               proposed_notional: float,
                               current_prices: Dict[str, float],
                               positions: Dict[str, Dict]) -> Dict[str, Any]:
        total_value = max(portfolio.get('total_value', 0.0), 1.0)
        open_trades = len(positions)

        if open_trades >= self.max_open_trades and symbol not in positions:
            return {
                'breach': True,
                'reason': 'Max open trades exceeded',
                'action': 'REJECT_ORDER'
            }

        single_position_ratio = proposed_notional / total_value
        if single_position_ratio > self.max_single_position:
            return {
                'breach': True,
                'reason': 'Max single position exceeded',
                'action': 'REJECT_ORDER'
            }

        total_exposure = 0.0
        crypto_exposure = 0.0

        for held_symbol, position in positions.items():
            if held_symbol not in current_prices:
                continue

            exposure = abs(position.get('size', 0.0) * current_prices[held_symbol])
            total_exposure += exposure

            if infer_market(held_symbol) == 'crypto':
                crypto_exposure += exposure

        projected_total_exposure = (total_exposure + proposed_notional) / total_value
        if projected_total_exposure > self.max_total_exposure:
            return {
                'breach': True,
                'reason': 'Max total exposure exceeded',
                'action': 'REJECT_ORDER'
            }

        projected_crypto_exposure = crypto_exposure
        if infer_market(symbol) == 'crypto':
            projected_crypto_exposure += proposed_notional

        if (projected_crypto_exposure / total_value) > self.max_crypto_exposure:
            return {
                'breach': True,
                'reason': 'Max crypto exposure exceeded',
                'action': 'REJECT_ORDER'
            }

        return {'breach': False}

    async def update_daily_pnl(self, pnl: float):
        self.daily_pnl += pnl

    def reset_daily(self):
        self.daily_pnl = 0
