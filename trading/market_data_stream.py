import asyncio
from typing import Dict, Any, Callable, List
from loguru import logger
from datetime import datetime
import numpy as np

class MarketDataStream:
    def __init__(self, broker_adapter=None):
        self.subscribers = {}
        self.running = False
        self.live_mode = False
        self.broker_adapter = broker_adapter
        self.market_data_cache = {}
        self.quote_queues = {}
        self.heartbeat_interval = 30
        self.max_reconnect_attempts = 8
        self._router_task = None
        self._heartbeat_task = None
        self._last_timestamp_by_symbol = {}
        self.integrity_rejections = {
            'stale_or_duplicate': 0,
            'invalid_price': 0,
            'invalid_volume': 0,
        }
        logger.info('Market Data Stream initialized')

    def _parse_ts(self, ts_value):
        if not ts_value:
            return None
        try:
            return datetime.fromisoformat(str(ts_value))
        except ValueError:
            return None

    def _validate_tick(self, symbol: str, data: Dict[str, Any]) -> bool:
        ts = self._parse_ts(data.get('timestamp'))
        if ts is not None:
            prev = self._last_timestamp_by_symbol.get(symbol)
            if prev is not None:
                lag_seconds = (prev - ts).total_seconds()
                # Quote streams can arrive slightly out of order; reject only materially stale data.
                if lag_seconds > 2.0:
                    self.integrity_rejections['stale_or_duplicate'] += 1
                    return False
                if ts > prev:
                    self._last_timestamp_by_symbol[symbol] = ts
            else:
                self._last_timestamp_by_symbol[symbol] = ts

        close_price = float(data.get('close', 0.0) or 0.0)
        if close_price <= 0:
            self.integrity_rejections['invalid_price'] += 1
            return False

        volume = float(data.get('volume', 0.0) or 0.0)
        if volume <= 0:
            self.integrity_rejections['invalid_volume'] += 1
            return False

        return True

    def subscribe(self, symbol: str, callback: Callable):
        if symbol not in self.subscribers:
            self.subscribers[symbol] = []
        if symbol not in self.quote_queues:
            self.quote_queues[symbol] = asyncio.Queue(maxsize=1000)
        self.subscribers[symbol].append(callback)
        logger.info(f'Subscribed to {symbol}')

    def set_broker_adapter(self, broker_adapter):
        self.broker_adapter = broker_adapter

    def has_live_adapter(self) -> bool:
        return self.broker_adapter is not None

    async def emit_market_data(self, symbol: str, data: Dict[str, Any]):
        if not self._validate_tick(symbol, data):
            logger.debug(f'Data integrity reject for {symbol}: {data}')
            return

        if symbol not in self.market_data_cache:
            self.market_data_cache[symbol] = []
        
        self.market_data_cache[symbol].append(data)
        
        if len(self.market_data_cache[symbol]) > 1000:
            self.market_data_cache[symbol] = self.market_data_cache[symbol][-1000:]
        
        if symbol in self.subscribers:
            for callback in self.subscribers[symbol]:
                try:
                    await callback(symbol, data)
                except Exception as e:
                    logger.error(f'Callback error for {symbol}: {e}')

    def get_historical_cache(self, symbol: str, lookback: int = 100) -> List[Dict]:
        if symbol not in self.market_data_cache:
            return []
        return self.market_data_cache[symbol][-lookback:]

    async def simulate_market_stream(self, symbols: List[str]):
        self.running = True
        self.live_mode = False
        logger.info(f'Starting simulated market stream for {symbols}')
        
        prices = {sym: 100.0 for sym in symbols}
        
        while self.running:
            for symbol in symbols:
                drift = np.random.normal(0, 0.0002)
                vol = np.random.normal(0, 0.001)

                prev_price = prices[symbol]
                prices[symbol] = prices[symbol] * (1 + drift + vol)
                prices[symbol] = max(prices[symbol], 1.0)

                # Simulate open as previous close, or same as close for first tick
                open_price = prev_price if prev_price else prices[symbol]

                tick = {
                    'symbol': symbol,
                    'open': float(open_price),
                    'close': float(prices[symbol]),
                    'high': float(max(open_price, prices[symbol]) * 1.001),
                    'low': float(min(open_price, prices[symbol]) * 0.999),
                    'volume': float(np.random.randint(1000, 10000)),
                    'timestamp': datetime.now().isoformat()
                }

                await self.emit_market_data(symbol, tick)

            await asyncio.sleep(1)

    async def _router_loop(self, symbols: List[str]):
        while self.running:
            for symbol in symbols:
                queue = self.quote_queues.get(symbol)
                if queue is None:
                    continue

                while not queue.empty():
                    tick = await queue.get()
                    await self.emit_market_data(symbol, tick)

            await asyncio.sleep(0.01)

    async def _heartbeat_loop(self):
        while self.running and self.live_mode:
            logger.debug('Market data heartbeat: live router active')
            await asyncio.sleep(self.heartbeat_interval)

    async def _quote_callback(self, symbol: str, tick: Dict[str, Any]):
        queue = self.quote_queues.setdefault(symbol, asyncio.Queue(maxsize=1000))

        if queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass

        queue.put_nowait(tick)

    async def stream_live_market_data(self, symbols: List[str]):
        if not self.broker_adapter:
            raise RuntimeError('No broker adapter configured; live market data is required.')

        self.running = True
        self.live_mode = True

        for symbol in symbols:
            self.quote_queues.setdefault(symbol, asyncio.Queue(maxsize=1000))

        self._router_task = asyncio.create_task(self._router_loop(symbols))
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        attempt = 0
        while self.running and attempt < self.max_reconnect_attempts:
            try:
                logger.info(f'Starting live market stream for {len(symbols)} symbols')
                await self.broker_adapter.stream_quotes(symbols, self._quote_callback)
                if not self.running:
                    break
                attempt += 1
                backoff = min(2 ** attempt, 60)
                logger.warning(f'Live stream ended unexpectedly; reconnecting in {backoff}s')
                await asyncio.sleep(backoff)
            except NotImplementedError as e:
                raise RuntimeError(f'Live stream unavailable: {e}') from e
            except asyncio.CancelledError:
                logger.info('Live market stream cancelled')
                raise
            except Exception as e:
                attempt += 1
                backoff = min(2 ** attempt, 60)
                logger.error(f'Live stream error (attempt {attempt}/{self.max_reconnect_attempts}): {e}')
                await asyncio.sleep(backoff)

        if attempt >= self.max_reconnect_attempts:
            raise RuntimeError('Max reconnect attempts reached for live market stream.')

    def stop(self):
        self.running = False
        self.live_mode = False

        if self._router_task:
            self._router_task.cancel()
            self._router_task = None

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

        logger.info('Market stream stopped')

