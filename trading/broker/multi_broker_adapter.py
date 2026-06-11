import asyncio
import os
from typing import Any, Awaitable, Callable, Dict, List

from loguru import logger

from .alpaca_adapter import AlpacaAdapter
from .base_adapter import BrokerAdapter
from .binance_adapter import BinanceAdapter
from .oanda_adapter import OandaAdapter


class MultiBrokerAdapter(BrokerAdapter):
    def __init__(self):
        self.alpaca = self._try_init('Alpaca', AlpacaAdapter)
        self.binance = self._try_init('Binance', BinanceAdapter)
        if os.getenv("OANDA_API_KEY") and os.getenv("OANDA_ACCOUNT_ID"):
            self.oanda = self._try_init('OANDA', OandaAdapter)
        else:
            self.oanda = None
            logger.info('OANDA disabled: credentials not set.')
        self._degraded_stream_adapters = set()

        if not any([self.alpaca, self.binance, self.oanda]):
            raise RuntimeError('No broker adapters available. Check broker credentials and runtime connectivity.')

        logger.info(
            'MultiBrokerAdapter ready | '
            f'alpaca={self.alpaca is not None} '
            f'binance={self.binance is not None} oanda={self.oanda is not None}'
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
        candidates = self._stream_candidates_for_symbol(symbol)
        return candidates[0] if candidates else None

    def _order_adapter_for_symbol(self, symbol: str):
        candidates = self._order_candidates_for_symbol(symbol)
        return candidates[0] if candidates else None

    @staticmethod
    def _unique_adapters(adapters):
        out = []
        for adapter in adapters:
            if adapter is None:
                continue
            if adapter in out:
                continue
            out.append(adapter)
        return out

    def _stream_candidates_for_symbol(self, symbol: str, exclude=None):
        excluded = set(exclude or set())
        excluded |= self._degraded_stream_adapters

        if self._is_crypto(symbol):
            preferred = [self.binance, self.alpaca]
        elif self._is_forex(symbol):
            preferred = [self.oanda, self.alpaca]
        else:
            preferred = [self.alpaca]

        return [a for a in self._unique_adapters(preferred) if a not in excluded]

    def _order_candidates_for_symbol(self, symbol: str, exclude=None):
        excluded = set(exclude or set())
        if self._is_crypto(symbol):
            preferred = [self.binance, self.alpaca]
        elif self._is_forex(symbol):
            preferred = [self.oanda]
        else:
            preferred = [self.alpaca]
        return [a for a in self._unique_adapters(preferred) if a not in excluded]

    async def get_live_bars(self, symbol: str, timeframe: str = '1Min', limit: int = 200) -> List[Dict[str, Any]]:
        errors = []
        for adapter in self._stream_candidates_for_symbol(symbol):
            try:
                return await adapter.get_live_bars(symbol, timeframe=timeframe, limit=limit)
            except Exception as exc:
                logger.warning(f'Live bars failed on {type(adapter).__name__} for {symbol}: {exc}')
                errors.append(f'{type(adapter).__name__}: {exc}')
        raise RuntimeError(f'No broker adapter available for live bars: {symbol} | errors={errors}')

    async def submit_order(self, symbol: str, qty: float, side: str, order_type: str = 'market') -> Dict[str, Any]:
        requested_qty = float(qty or 0.0)
        if requested_qty <= 0.0:
            raise RuntimeError(f'Invalid order quantity: {requested_qty}')

        candidates = self._order_candidates_for_symbol(symbol)

        errors = []
        for adapter in candidates:
            adapter_qty = requested_qty
            try:
                return await adapter.submit_order(symbol, adapter_qty, side, order_type=order_type)
            except Exception as exc:
                logger.warning(
                    f'Order submit failed on {type(adapter).__name__} for {symbol} '
                    f'(qty={adapter_qty}, requested={requested_qty}): {exc}'
                )
                errors.append(f'{type(adapter).__name__}: {exc}')
        raise RuntimeError(f'No broker adapter available for order: {symbol} | errors={errors}')

    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        for adapter in [self.alpaca, self.binance, self.oanda]:
            if adapter is None:
                continue
            try:
                return await adapter.cancel_order(order_id)
            except Exception:
                continue
        raise RuntimeError(f'Unable to cancel order_id={order_id} on any adapter')

    async def get_positions(self) -> List[Dict[str, Any]]:
        merged: List[Dict[str, Any]] = []
        for adapter in [self.alpaca, self.binance, self.oanda]:
            if adapter is None:
                continue
            try:
                merged.extend(await adapter.get_positions())
            except Exception as exc:
                logger.warning(f'Position fetch failed on {type(adapter).__name__}: {exc}')
        return merged

    async def get_account(self) -> Dict[str, Any]:
        accounts = []
        for adapter in [self.alpaca, self.binance, self.oanda]:
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
        connection_limit_detected = False
        for adapter, adapter_symbols in grouped.items():
            active_tasks[adapter] = asyncio.create_task(adapter.stream_quotes(adapter_symbols, callback))

        try:
            while active_tasks:
                done, _ = await asyncio.wait(list(active_tasks.values()), return_when=asyncio.FIRST_COMPLETED)

                finished_adapters = []
                restart_map: Dict[BrokerAdapter, List[str]] = {}
                for adapter, task in active_tasks.items():
                    if task in done:
                        finished_adapters.append(adapter)
                        adapter_symbols = grouped.get(adapter, [])
                        if task.cancelled():
                            logger.warning(f'{type(adapter).__name__} stream cancelled.')
                            continue

                        exc = task.exception()
                        if exc is not None:
                            logger.error(f'{type(adapter).__name__} stream failed: {exc}')
                            if 'connection limit' in str(exc).lower():
                                connection_limit_detected = True
                            self._degraded_stream_adapters.add(adapter)
                            rerouted = 0
                            for symbol in adapter_symbols:
                                candidates = self._stream_candidates_for_symbol(symbol, exclude={adapter})
                                if not candidates:
                                    continue
                                fallback_adapter = candidates[0]
                                restart_map.setdefault(fallback_adapter, []).append(symbol)
                                rerouted += 1
                            if rerouted:
                                logger.warning(
                                    f'Rerouting {rerouted} symbols from {type(adapter).__name__} '
                                    f'to fallback streams after failure.'
                                )
                        else:
                            logger.warning(f'{type(adapter).__name__} stream ended.')

                for adapter in finished_adapters:
                    active_tasks.pop(adapter, None)
                    grouped.pop(adapter, None)

                for adapter, adapter_symbols in restart_map.items():
                    # Avoid duplicate symbol subscriptions if multiple failed streams reroute in the same cycle.
                    merged_symbols = list(dict.fromkeys(grouped.get(adapter, []) + adapter_symbols))
                    grouped[adapter] = merged_symbols
                    if adapter in active_tasks:
                        continue
                    logger.info(f'Starting fallback stream on {type(adapter).__name__} for: {merged_symbols}')
                    active_tasks[adapter] = asyncio.create_task(adapter.stream_quotes(merged_symbols, callback))

                if not active_tasks:
                    if connection_limit_detected:
                        logger.warning(
                            'Broker stream paused after connection-limit failure; '
                            'keeping fallback polling paths active without restarting stream.'
                        )
                        while True:
                            await asyncio.sleep(300)
                    raise RuntimeError('All broker streams stopped.')
        except asyncio.CancelledError:
            for task in active_tasks.values():
                task.cancel()
            await asyncio.gather(*active_tasks.values(), return_exceptions=True)
            raise

