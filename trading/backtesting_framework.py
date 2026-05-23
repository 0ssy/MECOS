import numpy as np
from typing import Dict, List, Any
from loguru import logger


class BacktestingFramework:
    def __init__(self, memory):
        self.memory = memory
        logger.info("Backtesting Framework initialized")

    @staticmethod
    def _max_drawdown(equity_curve: List[float]) -> float:
        if not equity_curve:
            return 0.0
        arr = np.array(equity_curve, dtype=float)
        running_max = np.maximum.accumulate(arr)
        drawdowns = (arr - running_max) / np.maximum(running_max, 1.0)
        return float(abs(np.min(drawdowns)))

    async def run_backtest(
        self,
        strategy,
        historical_data: Any,
        initial_capital: float = 100000.0,
        commission_bps: float = 2.0,
        slippage_bps: float = 5.0,
        warmup: int = 50,
    ) -> Dict[str, Any]:
        is_multi_asset = isinstance(historical_data, dict)

        if is_multi_asset:
            symbols = list(historical_data.keys())
            min_len = min(len(v) for v in historical_data.values()) if symbols else 0
            if min_len <= warmup:
                return {"final_equity": float(initial_capital), "total_return": 0.0, "num_trades": 0, "equity_curve": []}
        else:
            if len(historical_data) <= warmup:
                return {"final_equity": float(initial_capital), "total_return": 0.0, "num_trades": 0, "equity_curve": []}
            symbols = ["TEST"]
            min_len = len(historical_data)

        cash = float(initial_capital)
        positions: Dict[str, float] = {symbol: 0.0 for symbol in symbols}
        equity_curve: List[float] = []
        trades: List[Dict[str, Any]] = []

        def get_price(data_slice: Any, symbol: str, idx: int) -> float:
            if isinstance(data_slice, dict):
                return float(data_slice[symbol][idx]["close"])
            return float(data_slice[idx]["close"])

        for i in range(warmup, min_len):
            if is_multi_asset:
                window = {symbol: rows[:i] for symbol, rows in historical_data.items()}
                result = await strategy.analyze_multi_asset(window)
                decisions = {s: result["asset_signals"].get(s, {}).get("final_decision", "HOLD") for s in symbols}
                sizes = {s: result["asset_signals"].get(s, {}).get("position_size", 0.1) for s in symbols}
            else:
                window = historical_data[:i]
                single = await strategy.analyze_market("TEST", window)
                decisions = {"TEST": single.get("final_decision", "HOLD")}
                sizes = {"TEST": single.get("position_size", 0.1)}

            for symbol in symbols:
                signal = decisions.get(symbol, "HOLD")
                price = get_price(historical_data, symbol, i)
                size = float(max(0.0, sizes.get(symbol, 0.1)))

                slippage = price * (slippage_bps / 10000.0)
                fee_rate = commission_bps / 10000.0

                if signal == "BUY" and positions[symbol] <= 0:
                    allocation = cash * min(size, 1.0)
                    if allocation <= 0:
                        continue
                    exec_price = price + slippage
                    qty = allocation / exec_price
                    fee = allocation * fee_rate
                    total_cost = allocation + fee
                    if total_cost <= cash:
                        cash -= total_cost
                        positions[symbol] += qty
                        trades.append({"symbol": symbol, "side": "BUY", "price": exec_price, "qty": qty, "fee": fee, "step": i})

                elif signal == "SELL" and positions[symbol] > 0:
                    exec_price = max(price - slippage, 0.0)
                    gross = positions[symbol] * exec_price
                    fee = gross * fee_rate
                    cash += gross - fee
                    trades.append({"symbol": symbol, "side": "SELL", "price": exec_price, "qty": positions[symbol], "fee": fee, "step": i})
                    positions[symbol] = 0.0

            mark_to_market = sum(positions[s] * get_price(historical_data, s, i) for s in symbols)
            equity_curve.append(float(cash + mark_to_market))

        if not equity_curve:
            return {"final_equity": float(initial_capital), "total_return": 0.0, "num_trades": 0, "equity_curve": []}

        returns = np.diff(equity_curve) / np.maximum(np.array(equity_curve[:-1]), 1.0)
        sharpe = float((np.mean(returns) / np.std(returns)) * np.sqrt(252)) if len(returns) > 1 and np.std(returns) > 0 else 0.0
        downside = returns[returns < 0]
        sortino = float((np.mean(returns) / np.std(downside)) * np.sqrt(252)) if len(downside) > 1 and np.std(downside) > 0 else 0.0
        max_drawdown = self._max_drawdown(equity_curve)

        completed = []
        open_buys: Dict[str, List[Dict[str, Any]]] = {s: [] for s in symbols}
        for t in trades:
            if t["side"] == "BUY":
                open_buys[t["symbol"]].append(t)
            elif t["side"] == "SELL" and open_buys[t["symbol"]]:
                b = open_buys[t["symbol"]].pop(0)
                pnl = (t["price"] - b["price"]) * min(t["qty"], b["qty"]) - (t["fee"] + b["fee"])
                completed.append(pnl)
        win_rate = float(sum(1 for p in completed if p > 0) / len(completed)) if completed else 0.0

        return {
            "final_equity": float(equity_curve[-1]),
            "total_return": float((equity_curve[-1] - initial_capital) / initial_capital),
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "max_drawdown": max_drawdown,
            "num_trades": len(trades),
            "win_rate": win_rate,
            "equity_curve": equity_curve,
            "trades": trades,
        }
