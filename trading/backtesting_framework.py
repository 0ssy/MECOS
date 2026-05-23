import numpy as np
from typing import Dict, List, Any
from loguru import logger

class BacktestingFramework:
    def __init__(self, memory):
        self.memory = memory
        logger.info("Backtesting Framework initialized")

    async def run_backtest(self,
                           strategy,
                           historical_data: List[Dict]) -> Dict[str, Any]:

        capital = 100000
        position = 0

        equity_curve = []

        trades = []

        for i in range(50, len(historical_data)):

            window = historical_data[:i]

            result = await strategy.analyze_market(
                "TEST",
                window
            )

            signal = result.get("final_decision", "HOLD")

            price = historical_data[i]["close"]

            if signal == "BUY" and position == 0:
                position = capital / price
                capital = 0

                trades.append({
                    "side": "BUY",
                    "price": price
                })

            elif signal == "SELL" and position > 0:
                capital = position * price
                position = 0

                trades.append({
                    "side": "SELL",
                    "price": price
                })

            equity = capital + position * price

            equity_curve.append(equity)

        returns = np.diff(equity_curve) / np.maximum(
            equity_curve[:-1],
            1
        )

        sharpe = (
            np.mean(returns) /
            np.std(returns)
        ) * np.sqrt(252) if len(returns) > 1 else 0

        return {
            "final_equity": float(equity_curve[-1]),
            "total_return": float(
                (equity_curve[-1] - 100000) / 100000
            ),
            "sharpe_ratio": float(sharpe),
            "num_trades": len(trades),
            "equity_curve": equity_curve
        }
