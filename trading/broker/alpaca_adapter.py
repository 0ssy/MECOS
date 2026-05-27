import asyncio
import os
from datetime import datetime
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

    @staticmethod
    def _extract_field(payload: Dict[str, Any], *keys: str, default: float = 0.0) -> float:
        for key in keys:
            if key in payload and payload[key] is not None:
                try:
                    return float(payload[key])
                except Exception:
                    continue
        return float(default)

    def _normalize_quote_to_tick(self, symbol: str, raw: Dict[str, Any]) -> Dict[str, Any]:
        bid = self._extract_field(raw, 'bid_price', 'bp', default=0.0)
        ask = self._extract_field(raw, 'ask_price', 'ap', default=0.0)
        bid_size = self._extract_field(raw, 'bid_size', 'bs', default=0.0)
        ask_size = self._extract_field(raw, 'ask_size', 'as', default=0.0)
        ts = raw.get('timestamp') or raw.get('t') or datetime.utcnow().isoformat()

        mid = 0.0
        if bid > 0.0 and ask > 0.0:
            mid = (bid + ask) / 2.0
        elif bid > 0.0:
            mid = bid
        elif ask > 0.0:
            mid = ask

        if mid <= 0.0:
            return {}

        return {
            'symbol': symbol,
            'open': float(mid),
            'high': float(max(bid, ask, mid)),
            'low': float(min(x for x in [bid, ask, mid] if x > 0.0)),
            'close': float(mid),
            'volume': float(max(1.0, bid_size + ask_size)),
            'timestamp': str(ts),
            'bid': float(bid),
            'ask': float(ask),
            'quote_size': float(bid_size + ask_size),
            'source': 'alpaca_quote',
        }

    async def stream_quotes(self, symbols: List[str], callback: Callable[[str, Dict[str, Any]], Awaitable[None]]) -> None:
        try:
            from alpaca.data.live import StockDataStream
            from config import settings
        except ImportError:
            logger.error('Alpaca SDK not available. Please install alpaca-py.')
            raise

        api_key = (
            getattr(settings, 'ALPACA_API_KEY', None)
            or os.getenv('ALPACA_API_KEY')
            or os.getenv('APCA_API_KEY_ID')
        )
        secret_key = (
            getattr(settings, 'ALPACA_SECRET_KEY', None)
            or os.getenv('ALPACA_SECRET_KEY')
            or os.getenv('APCA_API_SECRET_KEY')
        )
        if isinstance(api_key, str):
            api_key = api_key.strip().strip('"').strip("'")
        if isinstance(secret_key, str):
            secret_key = secret_key.strip().strip('"').strip("'")
        if not api_key or not secret_key:
            logger.error('Missing Alpaca API credentials.')
            raise RuntimeError('Missing Alpaca API credentials.')

        reconnect_attempt = 0
        while True:
            data_stream = StockDataStream(api_key, secret_key)

            async def quote_handler(data):
                if hasattr(data, '_raw'):
                    raw = data._raw
                elif isinstance(data, dict):
                    raw = data
                else:
                    raw = dict(data)
                symbol = str(getattr(data, 'symbol', None) or raw.get('symbol') or raw.get('S') or '')
                if not symbol:
                    return

                tick = self._normalize_quote_to_tick(symbol, raw)
                if tick:
                    await callback(symbol, tick)

            for symbol in symbols:
                data_stream.subscribe_quotes(quote_handler, symbol)

            try:
                logger.info(f'Starting Alpaca live quote stream for: {symbols}')
                await data_stream._run_forever()
                reconnect_attempt = 0
            except Exception as exc:
                if 'auth failed' in str(exc).lower():
                    raise RuntimeError('Alpaca websocket auth failed. Check ALPACA_API_KEY/ALPACA_SECRET_KEY.') from exc
                reconnect_attempt += 1
                backoff = min(2 ** reconnect_attempt, 60)
                logger.error(f'Alpaca quote stream disconnected (attempt {reconnect_attempt}): {exc}')
                await asyncio.sleep(backoff)
