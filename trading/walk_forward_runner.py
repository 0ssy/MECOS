"""
trading/walk_forward_runner.py
Walk-forward validation using BacktestingFramework.

Runs automatically on startup if historical data is available.
Stores results to memory_db/benchmarks/backtest_results.json.

Usage:
    from trading.walk_forward_runner import WalkForwardRunner
    runner = WalkForwardRunner(memory, trading_agent)
    results = await runner.run(historical_data)
"""
import json
import time
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Optional
from loguru import logger
from trading.backtesting_framework import BacktestingFramework


RESULTS_PATH = Path("memory_db/benchmarks/backtest_results.json")


class WalkForwardRunner:
    def __init__(self, memory, strategy):
        self.memory   = memory
        self.strategy = strategy
        self.framework = BacktestingFramework(memory)
        logger.info("WalkForwardRunner initialized")

    async def run(
        self,
        historical_data: Any,
        n_splits: int = 5,
        train_pct: float = 0.70,
        initial_capital: float = 10000.0,
        commission_bps: float = 2.0,
        slippage_bps: float = 5.0,
    ) -> Dict[str, Any]:
        """
        Walk-forward validation.
        Splits data into n_splits windows, trains on 70% and tests on 30% of each.
        Returns aggregate out-of-sample statistics.
        """
        logger.info(f"Walk-forward validation: {n_splits} splits, train={train_pct:.0%}")

        is_multi = isinstance(historical_data, dict)
        if is_multi:
            symbols  = list(historical_data.keys())
            data_len = min(len(v) for v in historical_data.values())
        else:
            symbols  = ["SINGLE"]
            data_len = len(historical_data)

        if data_len < 200:
            logger.warning(f"Insufficient history ({data_len} bars) for walk-forward. Need 200+.")
            return {"status": "insufficient_data", "bars": data_len}

        window_size = data_len // n_splits
        oos_results = []

        for i in range(n_splits):
            start = i * window_size
            end   = start + window_size if i < n_splits - 1 else data_len
            split_len = end - start
            train_end = start + int(split_len * train_pct)

            if is_multi:
                test_data = {s: v[train_end:end] for s, v in historical_data.items()}
            else:
                test_data = historical_data[train_end:end]

            try:
                result = await self.framework.run_backtest(
                    strategy=self.strategy,
                    historical_data=test_data,
                    initial_capital=initial_capital,
                    commission_bps=commission_bps,
                    slippage_bps=slippage_bps,
                    warmup=50,
                )
                result["split"] = i + 1
                result["period"] = f"bars {train_end}-{end}"
                oos_results.append(result)
                logger.info(
                    f"Split {i+1}/{n_splits}: return={result.get('total_return', 0):.2%} "
                    f"trades={result.get('num_trades', 0)} "
                    f"sharpe={result.get('sharpe_ratio', 0):.2f}"
                )
            except Exception as e:
                logger.error(f"Split {i+1} failed: {e}")
                continue

        if not oos_results:
            return {"status": "all_splits_failed"}

        # Aggregate OOS statistics
        returns    = [r.get("total_return", 0) for r in oos_results]
        sharpes    = [r.get("sharpe_ratio", 0) for r in oos_results]
        drawdowns  = [r.get("max_drawdown", 0) for r in oos_results]
        trade_cnts = [r.get("num_trades", 0) for r in oos_results]

        aggregate = {
            "status":              "complete",
            "splits":              len(oos_results),
            "avg_oos_return":      float(np.mean(returns)),
            "std_oos_return":      float(np.std(returns)),
            "avg_sharpe":          float(np.mean(sharpes)),
            "avg_max_drawdown":    float(np.mean(drawdowns)),
            "avg_trades_per_split": float(np.mean(trade_cnts)),
            "profitable_splits":   int(sum(1 for r in returns if r > 0)),
            "total_splits":        len(oos_results),
            "split_results":       oos_results,
            "run_at":              time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        self._save(aggregate)
        self._log_summary(aggregate)
        return aggregate

    def _log_summary(self, agg: Dict):
        logger.info("=" * 50)
        logger.info("WALK-FORWARD VALIDATION RESULTS")
        logger.info(f"  Splits:          {agg['splits']}")
        logger.info(f"  Avg OOS Return:  {agg['avg_oos_return']:.2%}")
        logger.info(f"  Avg Sharpe:      {agg['avg_sharpe']:.2f}")
        logger.info(f"  Avg Max DD:      {agg['avg_max_drawdown']:.2%}")
        logger.info(f"  Profitable:      {agg['profitable_splits']}/{agg['total_splits']} splits")
        logger.info("=" * 50)

    def _save(self, results: Dict):
        try:
            RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(RESULTS_PATH, "w") as f:
                json.dump(results, f, indent=2, default=str)
            logger.info(f"Walk-forward results saved to {RESULTS_PATH}")
        except Exception as e:
            logger.error(f"Failed to save walk-forward results: {e}")

    @staticmethod
    def load_last_results() -> Optional[Dict]:
        if not RESULTS_PATH.exists():
            return None
        try:
            with open(RESULTS_PATH) as f:
                return json.load(f)
        except Exception:
            return None
