import asyncio
import os
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional, Union
from loguru import logger
from dotenv import load_dotenv

from alpaca.common.exceptions import APIError
from alpaca.data.live import StockDataStream
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce


class LiveTradingConnector:
    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        paper: bool = True,
    ):
        load_dotenv()
        self.api_key = api_key or os.getenv("ALPACA_API_KEY")
        self.secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY")
        if not self.api_key or not self.secret_key:
            raise ValueError("Missing Alpaca credentials for LiveTradingConnector")

        self.trading_client = TradingClient(self.api_key, self.secret_key, paper=paper)
        self.data_stream = StockDataStream(self.api_key, self.secret_key)
        self._stream_task: Optional[asyncio.Task] = None

        logger.info("Live Trading Connector initialized")

    async def get_account(self) -> Dict[str, Any]:
        account = self.trading_client.get_account()
        return {
            "id": str(account.id),
            "equity": float(account.equity),
            "cash": float(account.cash),
            "buying_power": float(account.buying_power),
            "status": str(account.status),
        }

    async def get_positions(self) -> List[Dict[str, Any]]:
        positions = self.trading_client.get_all_positions()
        return [
            {
                "symbol": p.symbol,
                "qty": float(p.qty),
                "avg_entry_price": float(p.avg_entry_price),
                "market_value": float(p.market_value),
                "unrealized_pl": float(p.unrealized_pl),
            }
            for p in positions
        ]

    async def submit_market_order(self, symbol: str, qty: float, side: str) -> Dict[str, Any]:
        order = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
        try:
            submitted = self.trading_client.submit_order(order)
        except APIError as exc:
            raise RuntimeError(f"Order submit failed for {symbol} {side} qty={qty}: {exc}") from exc

        return {
            "id": str(submitted.id),
            "symbol": submitted.symbol,
            "qty": str(submitted.qty),
            "side": side.upper(),
            "status": str(submitted.status),
        }

    async def cancel_order(self, order_id: str) -> None:
        try:
            self.trading_client.cancel_order_by_id(order_id)
        except APIError as exc:
            raise RuntimeError(f"Cancel failed for order {order_id}: {exc}") from exc

    async def list_open_orders(self) -> List[Dict[str, Any]]:
        orders = self.trading_client.get_orders()
        return [
            {
                "id": str(o.id),
                "symbol": o.symbol,
                "qty": str(o.qty),
                "side": str(o.side),
                "status": str(o.status),
            }
            for o in orders
        ]

    async def stream_quotes(
        self,
        symbols: Union[str, Iterable[str]],
        callback: Callable[[Any], Union[None, Awaitable[None]]],
    ):
        symbol_list = [symbols] if isinstance(symbols, str) else list(symbols)

        async def quote_handler(data):
            maybe_coro = callback(data)
            if asyncio.iscoroutine(maybe_coro):
                await maybe_coro

        for symbol in symbol_list:
            self.data_stream.subscribe_quotes(quote_handler, symbol)

        if self._stream_task and not self._stream_task.done():
            return
        self._stream_task = asyncio.create_task(asyncio.to_thread(self.data_stream.run))

    async def stop_stream(self):
        self.data_stream.stop()
        if self._stream_task and not self._stream_task.done():
            await self._stream_task
