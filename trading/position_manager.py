from typing import Dict, Any
from loguru import logger
from datetime import datetime

class PositionManager:
    def __init__(self, database):
        self.database = database
        self.positions = {}
        logger.info('Position Manager initialized')

    async def update_position(self, symbol: str, side: str, size: float, price: float):
        if symbol not in self.positions:
            self.positions[symbol] = {
                'size':         0,
                'avg_price':    0,
                'unrealized_pnl': 0,
                'entry_time':   None,
                'peak_price':   0,
                'last_price':   0,
                'sector':       'unknown',
                'stop_loss':    0,
                'take_profit':  0,
            }

        position = self.positions[symbol]

        if side == 'BUY':
            total_cost          = position['size'] * position['avg_price'] + size * price
            position['size']   += size
            position['avg_price'] = total_cost / position['size'] if position['size'] > 0 else 0
            if position['entry_time'] is None:
                position['entry_time'] = datetime.now().isoformat()
            position['peak_price'] = max(position.get('peak_price', 0), price)
            position['last_price'] = price
            # Persist stop levels on first entry
            if position.get('stop_loss', 0) == 0:
                position['stop_loss']  = round(price * 0.98, 6)   # 2% stop loss
                position['take_profit'] = round(price * 1.05, 6)  # 5% take profit

        elif side == 'SELL':
            position['size'] -= size
            if position['size'] <= 0:
                del self.positions[symbol]
            else:
                position['last_price'] = price

        self.save_positions()
        logger.info(f'Position updated: {symbol} - {self.positions.get(symbol, "closed")}')

    def load_positions(self, positions: Dict[str, Dict[str, Any]]):
        restored = {}
        for symbol, pos in (positions or {}).items():
            if not isinstance(pos, dict):
                continue
            size = float(pos.get('size', 0.0) or 0.0)
            if size <= 0.0:
                continue
            restored[symbol] = {
                'size': size,
                'avg_price': float(pos.get('avg_price', pos.get('entry', 0.0)) or 0.0),
                'unrealized_pnl': float(pos.get('unrealized_pnl', 0.0) or 0.0),
                'entry_time': pos.get('entry_time') or pos.get('opened_at'),
                'peak_price': float(pos.get('peak_price', pos.get('avg_price', 0.0)) or 0.0),
                'last_price': float(pos.get('last_price', pos.get('avg_price', 0.0)) or 0.0),
                'sector': pos.get('sector', 'unknown'),
                'stop_loss': float(pos.get('stop_loss', pos.get('stop', 0.0)) or 0.0),
                'take_profit': float(pos.get('take_profit', 0.0) or 0.0),
            }
        self.positions = restored
        logger.info(f'Position state restored: {len(self.positions)} active positions')

    def mark_price(self, symbol: str, price: float):
        if symbol not in self.positions:
            return
        self.positions[symbol]['last_price'] = price
        self.positions[symbol]['peak_price'] = max(
            self.positions[symbol].get('peak_price', price),
            price
        )

    def get_holding_seconds(self, symbol: str) -> float:
        position = self.positions.get(symbol, {})
        logger.debug(
            f'holding_seconds check for {symbol}: '
            f'entry_time={position.get("entry_time")} opened_at={position.get("opened_at")}'
        )
        if not position:
            return 0.0
        entry_time = position.get('entry_time') or position.get('opened_at')

        if not entry_time:
            return 0.0

        entry_time = str(entry_time).strip()
        if entry_time.endswith('Z'):
            entry_time = entry_time[:-1] + '+00:00'

        try:
            dt = datetime.fromisoformat(entry_time)
            now = datetime.now(dt.tzinfo) if dt.tzinfo is not None else datetime.now()
            return max(0.0, (now - dt).total_seconds())
        except (ValueError, TypeError):
            return 0.0

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

    def save_positions(self):
        """Persist all open positions with stop levels to disk."""
        import json
        from pathlib import Path
        data = {
            "open_positions": {
                symbol: {
                    "entry":       pos.get("avg_price", 0),
                    "size":        pos.get("size", 0),
                    "stop":        pos.get("stop_loss", 0),
                    "take_profit": pos.get("take_profit", 0),
                    "opened_at":   pos.get("entry_time", ""),
                    "peak_price":  pos.get("peak_price", 0),
                    "sector":      pos.get("sector", "unknown"),
                }
                for symbol, pos in self.positions.items()
                if pos.get("size", 0) > 0
            },
            "last_updated": __import__("datetime").datetime.utcnow().isoformat()
        }
        Path("data/state.json").write_text(json.dumps(data, indent=2))
