from typing import Any, Awaitable, Callable, Dict, List

from loguru import logger

from ..broker_connector import BrokerConnector
from .base_adapter import BrokerAdapter


class AlpacaAdapter(BrokerAdapter):
    def __init__(self):
        self.connector = BrokerConnector()

    async def get_live_bars(self, symbol: str, timeframe: str = '1Min', limit: int = 200) -> List[Dict[str, Any]]:
        return await self.connector.get_market_data(symbol, timeframe=timeframe, limit=limit)

    async def submit_order(self, symbol: str, qty: float, side: str, order_type: str = 'market') -> Dict[str, Any]:
        return await self.connector.place_order(symbol=symbol, qty=qty, side=side)

    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        logger.warning(f'cancel_order not implemented in BrokerConnector yet: {order_id}')
        return {'status': 'UNSUPPORTED', 'order_id': order_id}

    async def get_positions(self) -> List[Dict[str, Any]]:
        return await self.connector.get_positions()

    async def get_account(self) -> Dict[str, Any]:
        return await self.connector.get_account_info()

    async def stream_quotes(self, symbols: List[str], callback: Callable[[str, Dict[str, Any]], Awaitable[None]]) -> None:
        # BrokerConnector currently exposes historical requests only.
        # This adapter keeps the unified interface and will route to live websocket implementation once added.
        raise NotImplementedError('Alpaca live quote streaming is not implemented in BrokerConnector yet')
