"""
Integration test for MECOS trading stack.
Validates that all trading layers work together as one unit.
"""

import asyncio
from trading import (
    AutonomousTradingLoop, CooldownManager, detect_regime, ExposureManager, EquityPersistence,
    PnLEngine, AttributionLogger, ConfidenceCalibrator, TradingAgent, UniverseManager,
    PaperTradingExecutor, PerformanceMonitor, MarketDataStream
)

class DummyMarketStream:
    def __init__(self):
        self.callbacks = {}
    def subscribe(self, symbol, cb):
        self.callbacks[symbol] = cb
    def has_live_adapter(self):
        return False
    async def simulate_market_stream(self, symbols):
        # Simulate 3 ticks per symbol
        for i in range(3):
            for symbol in symbols:
                tick = {'symbol': symbol, 'open': 100, 'close': 100 + i, 'volatility': 0.01, 'sector': 'tech'}
                await self.callbacks[symbol](symbol, tick)
    def stop(self):
        pass

class DummySignalGenerator:
    def __init__(self):
        self.count = 0
    async def on_market_data(self, symbol, tick):
        self.count += 1
        # Alternate BUY/SELL/HOLD
        if self.count % 3 == 1:
            signal = {'decision': 'BUY', 'confidence': 0.8, 'size': 1.0, 'trend_signal': 'BUY', 'meanrev_signal': 'HOLD', 'sentiment_signal': 'BULLISH'}
        elif self.count % 3 == 2:
            signal = {'decision': 'SELL', 'confidence': 0.7, 'size': 1.0, 'trend_signal': 'SELL', 'meanrev_signal': 'HOLD', 'sentiment_signal': 'BEARISH'}
        else:
            signal = {'decision': 'HOLD', 'confidence': 0.5, 'size': 1.0, 'trend_signal': 'HOLD', 'meanrev_signal': 'HOLD', 'sentiment_signal': 'NEUTRAL'}
        print(f"Signal for {symbol}: {signal}")
        with open('test_trading_outputs.txt', 'a') as f:
            f.write(f"Signal for {symbol}: {signal}\n")
        return signal
    def get_stats(self):
        return {'total_signals': self.count, 'buy_signals': self.count // 3, 'sell_signals': self.count // 3}

class DummyPaperExecutor:
    def __init__(self):
        self.execution_enabled = True
        self.paper_account = {'equity': 10000, 'cash': 10000}
        self.position_manager = type('PM', (), {'positions': {}})()
    async def execute_signal(self, signal):
        result = {'status': 'EXECUTED'} if signal['decision'] != 'HOLD' else {'status': 'SKIPPED'}
        if result['status'] == 'EXECUTED':
            print(f"Trade executed: {signal}")
            with open('test_trading_outputs.txt', 'a') as f:
                f.write(f"Trade executed: {signal}\n")
        return result
    async def update_equity(self, prices):
        pass
    def get_account_status(self):
        return {'total_return': 0.01, 'executed_orders': 2}

class DummyPerformanceMonitor:
    def get_metrics(self):
        return {'sharpe_ratio': 1.2, 'max_drawdown': 0.05, 'win_rate': 0.6}
    async def update(self, equity):
        pass

class DummyDatabase:
    def save_portfolio_snapshot(self, snapshot):
        pass

class DummyUniverseManager:
    def load_starter_universe(self):
        return ['AAPL', 'MSFT']
    def get_sector_allocation(self):
        return {'tech': 1.0}
    def load_default_universe(self):
        return ['AAPL', 'MSFT']
    def get_universe_statistics(self):
        return {'active_universe_size': 2}
    def rotate_universe(self, regime, scan_results):
        return ['AAPL', 'MSFT']

async def main():
    # Clear output file
    with open('test_trading_outputs.txt', 'w') as f:
        f.write('')

    loop = AutonomousTradingLoop(
        market_stream=DummyMarketStream(),
        signal_generator=DummySignalGenerator(),
        paper_executor=DummyPaperExecutor(),
        performance_monitor=DummyPerformanceMonitor(),
        database=DummyDatabase(),
        universe_manager=DummyUniverseManager(),
        universe_scanner=None
    )
    await loop.start(use_starter_universe=True)

    # Print and write final stats
    stats = loop.signal_generator.get_stats()
    print(f"Final signal stats: {stats}")
    with open('test_trading_outputs.txt', 'a') as f:
        f.write(f"Final signal stats: {stats}\n")

if __name__ == "__main__":
    asyncio.run(main())
