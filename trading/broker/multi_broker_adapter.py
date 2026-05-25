import asyncio
from typing import Any, Awaitable, Callable, Dict, List

from loguru import logger

from .alpaca_adapter import AlpacaAdapter
from .base_adapter import BrokerAdapter
from .binance_adapter import BinanceAdapter
from .ibkr_adapter import IbkrAdapter


class MultiBrokerAdapter(BrokerAdapter):
    def __init__(self):
        self.ibkr = self._try_init('IBKR', IbkrAdapter)
        self.alpaca = self._try_init('Alpaca', AlpacaAdapter)
        self.binance = self._try_init('Binance', BinanceAdapter)

        if not any([self.ibkr, self.alpaca, self.binance]):
            raise RuntimeError('No broker adapters available. Check IBKR/TWS and API keys.')

        logger.info(
            f'MultiBrokerAdapter ready | ibkr={self.ibkr is not None} alpaca={self.alpaca is not None} binance={self.binance is not None}'
        )

    @staticmethod
    def _try_init(name: str, cls):
        try:
            return cls()
        except Exception as exc:
            logger.warning(f'{name} adapter unavailable: {exc}')
            return None

    @staticmethod
    def _is_crypto(symbol: str) -> bool:
        s = str(symbol).upper()
        if s.endswith('USDT'):
            return True
        if '/' in s:
            base, quote = s.split('/', 1)
            crypto_assets = {'BTC', 'ETH', 'SOL', 'ADA', 'DOGE', 'AVAX', 'LINK', 'XRP', 'BNB', 'DOT', 'LTC'}
            return base in crypto_assets and quote in {'USD', 'USDT', 'USDC'}
        return False

    @staticmethod
    def _is_forex(symbol: str) -> bool:
        s = str(symbol).upper()
        if len(s) == 6 and s.isalpha():
            return True
        if '/' in s:
            left, right = s.split('/', 1)
            return len(left) == 3 and len(right) == 3 and left.isalpha() and right.isalpha()
        return False

    def _stream_adapter_for_symbol(self, symbol: str):
        if self._is_crypto(symbol):
            if self.binance:
                return self.binance
            if self.ibkr:
                return self.ibkr
            return self.alpaca
        if self._is_forex(symbol):
            return self.ibkr or self.alpaca
        return self.ibkr or self.alpaca

    def _order_adapter_for_symbol(self, symbol: str):
        if self._is_crypto(symbol):
            return self.binance or self.ibkr
        return self.ibkr or self.alpaca

    async def get_live_bars(self, symbol: str, timeframe: str = '1Min', limit: int = 200) -> List[Dict[str, Any]]:
        adapter = self._stream_adapter_for_symbol(symbol)
        if adapter is None:
            raise RuntimeError(f'No broker adapter available for live bars: {symbol}')
        return await adapter.get_live_bars(symbol, timeframe=timeframe, limit=limit)

    async def submit_order(self, symbol: str, qty: float, side: str, order_type: str = 'market') -> Dict[str, Any]:
        adapter = self._order_adapter_for_symbol(symbol)
        if adapter is None:
            raise RuntimeError(f'No broker adapter available for order: {symbol}')
        return await adapter.submit_order(symbol, qty, side, order_type=order_type)

    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        for adapter in [self.ibkr, self.alpaca, self.binance]:
            if adapter is None:
                continue
            try:
                return await adapter.cancel_order(order_id)
            except Exception:
                continue
        raise RuntimeError(f'Unable to cancel order_id={order_id} on any adapter')

    async def get_positions(self) -> List[Dict[str, Any]]:
        merged: List[Dict[str, Any]] = []
        for adapter in [self.ibkr, self.alpaca, self.binance]:
            if adapter is None:
                continue
            try:
                merged.extend(await adapter.get_positions())
            except Exception as exc:
                logger.warning(f'Position fetch failed on {type(adapter).__name__}: {exc}')
        return merged

    async def get_account(self) -> Dict[str, Any]:
        accounts = []
        for adapter in [self.ibkr, self.alpaca, self.binance]:
            if adapter is None:
                continue
            try:
                accounts.append(await adapter.get_account())
            except Exception as exc:
                logger.warning(f'Account fetch failed on {type(adapter).__name__}: {exc}')
        if not accounts:
            raise RuntimeError('No account information available from any adapter.')
        return accounts[0]

    async def stream_quotes(self, symbols: List[str], callback: Callable[[str, Dict[str, Any]], Awaitable[None]]) -> None:
        grouped: Dict[BrokerAdapter, List[str]] = {}
        for symbol in symbols:
            adapter = self._stream_adapter_for_symbol(symbol)
            if adapter is None:
                raise RuntimeError(f'No adapter available for symbol stream: {symbol}')
            grouped.setdefault(adapter, []).append(symbol)

        active_tasks: Dict[BrokerAdapter, asyncio.Task] = {}
        for adapter, adapter_symbols in grouped.items():
            active_tasks[adapter] = asyncio.create_task(adapter.stream_quotes(adapter_symbols, callback))

        try:
            while active_tasks:
                done, _ = await asyncio.wait(list(active_tasks.values()), return_when=asyncio.FIRST_COMPLETED)

                finished_adapters = []
                for adapter, task in active_tasks.items():
                    if task in done:
                        finished_adapters.append(adapter)
                        if task.cancelled():
                            logger.warning(f'{type(adapter).__name__} stream cancelled.')
                            continue

                        exc = task.exception()
                        if exc is not None:
                            logger.error(f'{type(adapter).__name__} stream failed: {exc}')
                        else:
                            logger.warning(f'{type(adapter).__name__} stream ended.')

                for adapter in finished_adapters:
                    active_tasks.pop(adapter, None)

                if not active_tasks:
                    raise RuntimeError('All broker streams stopped.')
        except asyncio.CancelledError:
            for task in active_tasks.values():
                task.cancel()
            await asyncio.gather(*active_tasks.values(), return_exceptions=True)
            raise
