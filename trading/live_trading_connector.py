import asyncio
from alpaca.data.live import StockDataStream
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from loguru import logger

class LiveTradingConnector:
    def __init__(self,
                 api_key: str,
                 secret_key: str,
                 paper: bool = True):

        self.trading_client = TradingClient(
            api_key,
            secret_key,
            paper=paper
        )

        self.data_stream = StockDataStream(
            api_key,
            secret_key
        )

        logger.info("Live Trading Connector initialized")

    async def submit_market_order(self,
                                  symbol: str,
                                  qty: float,
                                  side: str):

        order = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY if side == "BUY" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY
        )

        return self.trading_client.submit_order(order)

    async def stream_quotes(self,
                            symbol: str,
                            callback):

        async def quote_handler(data):
            await callback(data)

        self.data_stream.subscribe_quotes(
            quote_handler,
            symbol
        )

        self.data_stream.run()
