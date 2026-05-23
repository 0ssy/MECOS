import asyncio
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

        async def quote_handler(data):
            await callback(data)

        for symbol in symbols:
            self.data_stream.subscribe_quotes(
                quote_handler,
                symbol
            )

        logger.info(f'Starting quote stream: {symbols}')

        await self.data_stream._run_forever()
