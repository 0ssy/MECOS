import asyncio
from typing import Dict, Any, Callable, List
from loguru import logger
from datetime import datetime
import numpy as np
from trading.price_streamer import stream_binance_prices


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
        self._public_stream_task = None
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

    async def preseed_cache(self, symbols: List[str], lookback: int = 100):
        """
        Pre-fill the historical cache with yfinance data on startup.
        Eliminates the warmup wait — signals fire from the first tick
        instead of waiting for 35-50 live bars to accumulate.
        """
        import yfinance as yf

        CRYPTO_BASES = {
            "BTC", "ETH", "SOL", "AVAX", "LINK", "DOGE",
            "ADA", "BNB", "XRP", "DOT", "MATIC", "LTC",
        }

        logger.info(f"Pre-seeding cache for {len(symbols)} symbols...")

        for symbol in symbols:
            try:
                # Convert symbol to yfinance format
                if "/" in symbol:
                    base, quote = symbol.split("/", 1)
                    if base.upper() in CRYPTO_BASES:
                        yf_symbol = f"{base}-{quote}"       # BTC/USD -> BTC-USD
                    else:
                        yf_symbol = f"{base}{quote}=X"      # EUR/USD -> EURUSD=X
                else:
                    yf_symbol = symbol                      # AAPL -> AAPL

                def _yf_fetch_preseed(sym):
                    import yfinance as yf
                    return yf.Ticker(sym)
                ticker = await asyncio.to_thread(_yf_fetch_preseed, yf_symbol)

                # Try 5-minute bars first (more granular, better for signals)
                df = ticker.history(period="30d", interval="1h", auto_adjust=True)

                # Fall back to hourly if 5m not available
                if df.empty:
                    df = ticker.history(period="30d", interval="1h", auto_adjust=True)

                if df.empty:
                    logger.warning(f"Could not preseed {symbol} ({yf_symbol})")
                    continue

                bars = []
                for ts, row in df.iterrows():
                    close = float(row.get("Close", 0) or 0)
                    if close <= 0:
                        continue
                    bars.append({
                        "symbol":    symbol,
                        "open":      float(row.get("Open",   close) or close),
                        "close":     close,
                        "high":      float(row.get("High",   close) or close),
                        "low":       float(row.get("Low",    close) or close),
                        "volume":    float(row.get("Volume", 1)     or 1),
                        "timestamp": str(ts),
                    })

                if bars:
                    # Directly populate cache — bypass validate_tick
                    # since yfinance data can have older timestamps
                    self.market_data_cache[symbol] = bars[-200:]
                    logger.info(
                        f"Pre-seeded {symbol}: {len(self.market_data_cache[symbol])} bars "
                        f"(latest close: {bars[-1]['close']:.4f})"
                    )

            except Exception as e:
                logger.warning(f"Preseed failed for {symbol}: {e}")

        seeded = sum(1 for s in symbols if s in self.market_data_cache and self.market_data_cache[s])
        logger.info(f"Cache pre-seeding complete: {seeded}/{len(symbols)} symbols ready")

    async def stream_live_market_data(self, symbols: List[str]):
        """Stream live market data from broker adapters (Alpaca + Binance)."""
        if not self.broker_adapter:
            raise RuntimeError('No broker adapter configured; live market data is required.')

        self.running = True
        self.live_mode = True

        for symbol in symbols:
            self.quote_queues.setdefault(symbol, asyncio.Queue(maxsize=1000))

        self._router_task     = asyncio.create_task(self._router_loop(symbols))
        self._heartbeat_task  = asyncio.create_task(self._heartbeat_loop())

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
                logger.error(
                    f'Live stream error (attempt {attempt}/{self.max_reconnect_attempts}): {e}'
                )
                await asyncio.sleep(backoff)

        if attempt >= self.max_reconnect_attempts:
            raise RuntimeError('Max reconnect attempts reached for live market stream.')

    async def stream_public_crypto_data(self, symbols: List[str]):
        """Stream public Binance crypto ticks without broker credentials."""
        if not symbols:
            raise ValueError('No symbols provided for public crypto stream.')

        self.running = True
        self.live_mode = True

        normalized_map: Dict[str, str] = {}
        for symbol in symbols:
            token = str(symbol).upper().replace("/", "").replace("-", "")
            if token:
                normalized_map[token] = str(symbol)

        async def _public_callback(tick: Dict[str, Any]):
            raw_symbol      = str(tick.get("symbol", "")).upper()
            canonical_symbol = normalized_map.get(raw_symbol, raw_symbol)
            price  = float(tick.get("price",  0.0) or 0.0)
            volume = float(tick.get("volume", 0.0) or 0.0)
            bar = {
                "symbol":    canonical_symbol,
                "open":      price,
                "close":     price,
                "high":      price,
                "low":       price,
                "volume":    max(volume, 1.0),
                "timestamp": datetime.now().isoformat(),
            }
            await self.emit_market_data(canonical_symbol, bar)

        stream_symbols = list(normalized_map.keys())
        if not stream_symbols:
            raise ValueError('No valid symbols for Binance public stream.')

        logger.info(f'Starting Binance public stream for {len(stream_symbols)} symbols')
        self._public_stream_task = asyncio.current_task()
        try:
            await stream_binance_prices(stream_symbols, _public_callback)
        finally:
            self._public_stream_task = None

    async def simulate_market_stream(self, symbols: List[str]):
        """Simulated stream for testing. Not used in live trading."""
        self.running = True
        self.live_mode = False
        logger.info(f'Starting simulated market stream for {symbols}')

        # Use realistic base prices for each symbol type
        base_prices = {}
        for sym in symbols:
            if 'BTC' in sym:
                base_prices[sym] = 64000.0 + np.random.uniform(-1000, 1000)
            elif 'ETH' in sym:
                base_prices[sym] = 1700.0 + np.random.uniform(-50, 50)
            elif 'SOL' in sym:
                base_prices[sym] = 70.0 + np.random.uniform(-5, 5)
            elif sym in {'SPY', 'QQQ', 'IWM'}:
                base_prices[sym] = 700.0 + np.random.uniform(-20, 20)
            else:
                base_prices[sym] = 300.0 + np.random.uniform(-30, 30)

        prices = dict(base_prices)

        while self.running:
            for symbol in symbols:
                # Upward drift with occasional pullbacks for realistic exits
                drift = np.random.normal(0.0005, 0.001)  # Positive bias
                vol   = np.random.normal(0, 0.001)
                
                prev_price      = prices[symbol]
                new_price       = prices[symbol] * (1 + drift + vol)
                prices[symbol]  = max(new_price, base_prices[symbol] * 0.5)
                open_price      = prev_price

                tick = {
                    'symbol':    symbol,
                    'open':      float(open_price),
                    'close':     float(prices[symbol]),
                    'high':      float(max(open_price, prices[symbol]) * 1.001),
                    'low':       float(min(open_price, prices[symbol]) * 0.999),
                    'volume':    float(np.random.randint(1000, 10000)),
                    'timestamp': datetime.now().isoformat(),
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

    def stop(self):
        self.running  = False
        self.live_mode = False

        if self._router_task:
            self._router_task.cancel()
            self._router_task = None

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

        if self._public_stream_task:
            self._public_stream_task.cancel()
            self._public_stream_task = None

        logger.info('Market stream stopped')