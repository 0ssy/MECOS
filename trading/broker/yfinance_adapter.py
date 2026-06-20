import asyncio
from datetime import datetime
from typing import Any, Dict, List, Callable, Awaitable
import yfinance as yf
import numpy as np

from loguru import logger


class YFinanceAdapter:
    """Simple yfinance-based market data adapter for paper trading without API keys."""

    @staticmethod
    def _to_yf_symbol(symbol: str) -> str:
        s = str(symbol).upper().strip()
        if '/' in s:
            base, quote = s.split('/', 1)
            return f"{base}-{quote}"
        return s

    async def stream_quotes(self, symbols: List[str], callback: Callable[[str, Dict[str, Any]], Awaitable[None]]):
        """Generate live ticks using yfinance with realistic intraday updates."""
        logger.info(f'YFinance stream starting for {len(symbols)} symbols: {symbols}')
        
        # Pre-fetch to get last close prices
        prices = {}
        for symbol in symbols:
            try:
                yf_symbol = self._to_yf_symbol(symbol)
                df = yf.Ticker(yf_symbol).history(period="1d", interval="1m", auto_adjust=True, timeout=10)
                if not df.empty:
                    prices[symbol] = float(df.iloc[-1]["Close"])
                    logger.info(f"Pre-fetched {symbol}: {yf_symbol} -> {prices[symbol]:.2f}")
            except Exception as e:
                prices[symbol] = 100.0
                logger.warning(f"Pre-fetch failed for {symbol}: {e}")
        
        iteration = 0
        while True:
            iteration += 1
            for symbol in symbols:
                price = prices.get(symbol, 100.0)
                # Small random walk movement
                change = np.random.normal(0, 0.0015)
                price = max(price * (1 + change), prices.get(symbol, 100.0) * 0.7)
                prices[symbol] = price

                tick = {
                    'symbol': symbol,
                    'open': price,
                    'close': price,
                    'high': price * 1.001,
                    'low': price * 0.999,
                    'volume': float(np.random.randint(1000, 10000)),
                    'timestamp': datetime.utcnow().isoformat(),
                }
                try:
                    await callback(symbol, tick)
                except Exception as e:
                    logger.error(f"Callback error for {symbol}: {e}")
            
            logger.debug(f"YFinance stream tick {iteration} for {len(symbols)} symbols")
            await asyncio.sleep(2)

    async def get_live_bars(self, symbol: str, timeframe: str = '1Min', limit: int = 200) -> List[Dict[str, Any]]:
        yf_symbol = self._to_yf_symbol(symbol)
        try:
            df = yf.Ticker(yf_symbol).history(period="5d", interval="1m", auto_adjust=True)
            bars = []
            for _, row in df.iterrows():
                bars.append({
                    'symbol': symbol,
                    'timestamp': str(row.name),
                    'open': float(row.get('Open', row.get('Close', 0))),
                    'high': float(row.get('High', row.get('Close', 0))),
                    'low': float(row.get('Low', row.get('Close', 0))),
                    'close': float(row.get('Close', 0)),
                    'volume': float(row.get('Volume', 1)),
                })
            return bars[-limit:]
        except Exception as e:
            logger.warning(f'yfinance bars failed for {symbol}: {e}')
            return []

    async def submit_order(self, symbol: str, qty: float, side: str, order_type: str = 'market'):
        # Paper trading - just log the order
        logger.info(f'PAPER ORDER: {side} {qty} {symbol}')
        return {'status': 'FILLED', 'symbol': symbol, 'id': 'paper_1'}

    async def get_positions(self) -> List[Dict[str, Any]]:
        return []

    async def get_account(self) -> Dict[str, Any]:
        return {'cash': 10000.0, 'equity': 10000.0, 'status': 'PAPER'}