import asyncio
from datetime import datetime
from typing import Dict, Any, Callable
from loguru import logger

try:
    from alpaca.data.live import StockDataStream
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce

    ALPACA_AVAILABLE = True

except ImportError:
    ALPACA_AVAILABLE = False
    logger.warning('Alpaca SDK not available')

class LiveTradingConnector:

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        paper: bool = True
    ):

        if not ALPACA_AVAILABLE:
            logger.error('Alpaca SDK required')
            self.enabled = False
            return

        self.trading_client = TradingClient(
            api_key,
            secret_key,
            paper=paper
        )

        self.data_stream = StockDataStream(
            api_key,
            secret_key
        )

        self.enabled = True

        logger.info('Live Trading Connector initialized')

    async def get_account(self):

        account = self.trading_client.get_account()

        return {
            'id': str(account.id),
            'equity': float(account.equity),
            'cash': float(account.cash),
            'buying_power': float(account.buying_power),
            'status': str(account.status)
        }

    async def stream_quotes(
        self,
        symbols: list,
        callback: Callable
    ):
        reconnect_attempt = 0
        while True:
            async def quote_handler(data):
                raw = data._raw if hasattr(data, '_raw') else dict(data)
                symbol = getattr(data, 'symbol', None) or raw.get('symbol') or raw.get('S')
                bid = float(raw.get('bid_price', raw.get('bp', 0.0)) or 0.0)
                ask = float(raw.get('ask_price', raw.get('ap', 0.0)) or 0.0)
                mid = (bid + ask) / 2.0 if bid > 0.0 and ask > 0.0 else max(bid, ask)
                if not symbol or mid <= 0.0:
                    return
                tick = {
                    'symbol': symbol,
                    'open': mid,
                    'high': max(bid, ask, mid),
                    'low': min(x for x in [bid, ask, mid] if x > 0.0),
                    'close': mid,
                    'volume': max(1.0, float(raw.get('bid_size', raw.get('bs', 0.0)) or 0.0) + float(raw.get('ask_size', raw.get('as', 0.0)) or 0.0)),
                    'timestamp': str(raw.get('timestamp') or raw.get('t') or datetime.utcnow().isoformat()),
                }
                await callback(symbol, tick)

            for symbol in symbols:
                self.data_stream.subscribe_quotes(quote_handler, symbol)

            try:
                logger.info(f'Starting quote stream: {symbols}')
                await self.data_stream._run_forever()
                reconnect_attempt = 0
                await asyncio.sleep(1)
            except Exception as exc:
                reconnect_attempt += 1
                backoff = min(2 ** reconnect_attempt, 60)
                logger.error(f'Live quote stream disconnected (attempt {reconnect_attempt}): {exc}')
                await asyncio.sleep(backoff)
