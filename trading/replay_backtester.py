from typing import Dict, List, Any
import csv
from loguru import logger

from .backtesting_framework import BacktestingFramework


class ReplayBacktester:
    """Replay historical sessions and benchmark strategy revisions."""

    def __init__(self, memory):
        self.memory = memory
        self.framework = BacktestingFramework(memory)
        logger.info('Replay Backtester initialized')

    def load_csv_bars(self, csv_path: str) -> List[Dict[str, Any]]:
        bars: List[Dict[str, Any]] = []
        with open(csv_path, 'r', newline='') as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                try:
                    bars.append({
                        'timestamp': row.get('timestamp') or row.get('time') or '',
                        'open': float(row.get('open', 0.0) or 0.0),
                        'high': float(row.get('high', 0.0) or 0.0),
                        'low': float(row.get('low', 0.0) or 0.0),
                        'close': float(row.get('close', 0.0) or 0.0),
                        'volume': float(row.get('volume', 0.0) or 0.0),
                    })
                except ValueError:
                    continue
        logger.info(f'Loaded {len(bars)} bars from {csv_path}')
        return bars

    async def replay_csv(self, strategy, csv_path: str, initial_capital: float = 100000.0) -> Dict[str, Any]:
        bars = self.load_csv_bars(csv_path)
        results = await self.framework.run_backtest(
            strategy=strategy,
            historical_data=bars,
            initial_capital=initial_capital,
        )
        logger.info(
            'Replay complete | return=%.2f%% sharpe=%.2f drawdown=%.2f%% trades=%s',
            results.get('total_return', 0.0) * 100.0,
            results.get('sharpe_ratio', 0.0),
            results.get('max_drawdown', 0.0) * 100.0,
            results.get('num_trades', 0),
        )
        return results
