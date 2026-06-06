import asyncio
from typing import Dict, Any, List
from loguru import logger
import numpy as np

class UniverseScanner:
    def __init__(self, universe_manager, market_stream):
        self.universe_manager = universe_manager
        self.market_stream = market_stream
        
        self.scan_results = {}
        self.scan_interval = 300
        
        logger.info('Universe Scanner initialized')

    async def scan_universe(self, symbols: List[str]) -> Dict[str, Dict]:
        '''Scan universe and collect metrics for filtering'''
        
        logger.info(f'Scanning {len(symbols)} symbols...')
        
        results = {}
        
        for symbol in symbols:
            try:
                historical = self.market_stream.get_historical_cache(symbol, lookback=100)
                used_fallback = False
                if len(historical) < 20:
                    historical = await self._fetch_historical_fallback(symbol, min_bars=20, lookback=100)
                    used_fallback = len(historical) >= 20

                if len(historical) < 20:
                    results[symbol] = self._empty_metrics(symbol)
                    continue

                closes = np.array([d['close'] for d in historical])
                volumes = np.array([d['volume'] for d in historical])
                if closes.size < 2 or np.mean(closes) <= 0:
                    results[symbol] = self._empty_metrics(symbol)
                    continue
                
                returns = np.diff(np.log(closes + 1e-10))
                volatility = np.std(returns) * np.sqrt(252)
                
                momentum = (closes[-1] - closes[0]) / closes[0]
                
                avg_volume = np.mean(volumes)
                
                high_low = [(d['high'] - d['low']) for d in historical]
                avg_spread = np.mean(high_low) / np.mean(closes)
                
                liquidity_score = min(avg_volume / 1000000, 1.0)
                
                results[symbol] = {
                    'price': float(closes[-1]),
                    'volatility': float(volatility),
                    'momentum': float(momentum),
                    'volume': float(avg_volume),
                    'spread': float(avg_spread),
                    'liquidity_score': float(liquidity_score),
                    'data_quality': 'fallback' if used_fallback else 'full',
                }
                
            except Exception as e:
                logger.debug(f'Scan error for {symbol}: {e}')
                results[symbol] = self._empty_metrics(symbol)
        
        self.scan_results = results
        
        full_count = sum(1 for m in results.values() if m.get('data_quality') == 'full')
        fallback_count = sum(1 for m in results.values() if m.get('data_quality') == 'fallback')
        logger.info(
            f'Scan complete: {len(results)}/{len(symbols)} assets analyzed '
            f'({full_count} full, {fallback_count} fallback)'
        )

        return results

    @staticmethod
    def _empty_metrics(symbol: str) -> Dict[str, Any]:
        return {
            'price': 0.0,
            'volatility': 0.0,
            'momentum': 0.0,
            'volume': 0.0,
            'spread': 1.0,
            'liquidity_score': 0.0,
            'data_quality': 'fallback',
            'symbol': symbol,
        }

    async def _fetch_historical_fallback(self, symbol: str, min_bars: int = 20, lookback: int = 100) -> List[Dict[str, Any]]:
        """
        Backfill bars directly from broker adapters when local cache is still cold.
        """
        adapter = getattr(self.market_stream, "broker_adapter", None)
        if adapter is None or not hasattr(adapter, "get_live_bars"):
            return []

        try:
            bars = await adapter.get_live_bars(symbol, timeframe='1Min', limit=max(min_bars, lookback))
        except Exception as e:
            logger.debug(f'Fallback bars unavailable for {symbol}: {e}')
            return []

        normalized: List[Dict[str, Any]] = []
        for row in bars or []:
            try:
                close = float(row.get('close', 0.0) or 0.0)
                high = float(row.get('high', close) or close)
                low = float(row.get('low', close) or close)
                volume = float(row.get('volume', 0.0) or 0.0)
                if close <= 0.0:
                    continue
                normalized.append(
                    {
                        'close': close,
                        'high': max(high, close),
                        'low': min(low, close),
                        'volume': max(volume, 1.0),
                    }
                )
            except Exception:
                continue
        return normalized[-lookback:]

    async def continuous_scanning(self, symbols: List[str]):
        '''Continuously scan universe at intervals'''
        
        while True:
            await self.scan_universe(symbols)
            await asyncio.sleep(self.scan_interval)

    def get_scan_results(self) -> Dict[str, Dict]:
        return self.scan_results

    def get_top_momentum(self, n: int = 10) -> List[str]:
        '''Get top N symbols by momentum'''
        
        ranked = sorted(
            self.scan_results.items(),
            key=lambda x: x[1].get('momentum', 0),
            reverse=True
        )
        
        return [sym for sym, _ in ranked[:n]]

    def get_high_volatility(self, threshold: float = 0.03) -> List[str]:
        '''Get symbols with volatility above threshold'''
        
        return [
            sym for sym, metrics in self.scan_results.items()
            if metrics.get('volatility', 0) > threshold
        ]

    def get_liquid_assets(self, min_score: float = 0.5) -> List[str]:
        '''Get highly liquid assets'''
        
        return [
            sym for sym, metrics in self.scan_results.items()
            if metrics.get('liquidity_score', 0) >= min_score
        ]
