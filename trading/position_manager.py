from typing import Dict, Any
from loguru import logger

class PositionManager:
    def __init__(self, database):
        self.database = database
        self.positions = {}
        logger.info('Position Manager initialized')

    async def update_position(self, symbol: str, side: str, size: float, price: float):
        if symbol not in self.positions:
            self.positions[symbol] = {
                'size': 0,
                'avg_price': 0,
                'unrealized_pnl': 0
            }
        
        position = self.positions[symbol]
        
        if side == 'BUY':
            total_cost = position['size'] * position['avg_price'] + size * price
            position['size'] += size
            position['avg_price'] = total_cost / position['size'] if position['size'] > 0 else 0
        
        elif side == 'SELL':
            position['size'] -= size
            if position['size'] <= 0:
                del self.positions[symbol]
        
        logger.info(f'Position updated: {symbol} - {position}')

    async def calculate_unrealized_pnl(self, current_prices: Dict[str, float]) -> float:
        total_pnl = 0
        
        for symbol, position in self.positions.items():
            if symbol in current_prices:
                current_price = current_prices[symbol]
                pnl = (current_price - position['avg_price']) * position['size']
                position['unrealized_pnl'] = pnl
                total_pnl += pnl
        
        return total_pnl

    def get_exposure(self, current_prices: Dict[str, float]) -> float:
        total_exposure = 0
        
        for symbol, position in self.positions.items():
            if symbol in current_prices:
                exposure = position['size'] * current_prices[symbol]
                total_exposure += abs(exposure)
        
        return total_exposure
