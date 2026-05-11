"""
MECOS Phase 5 - Trading Agent
Market data ingestion, technical indicators (RSI, MACD, ATR, BB, EMA, SMA),
pattern recognition, backtesting engine, risk management, and paper trading.
"""

import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger

try:
    import pandas as pd
    import numpy as np
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    logger.warning("pandas/numpy not available — TradingAgent in limited mode.")

from memory_system import MemorySystem


class IndicatorEngine:
    """Computes technical indicators from OHLCV data."""

    @staticmethod
    def rsi(close: "pd.Series", period: int = 14) -> "pd.Series":
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss.replace(0, float("inf"))
        return 100 - (100 / (1 + rs))

    @staticmethod
    def ema(close: "pd.Series", period: int) -> "pd.Series":
        return close.ewm(span=period, adjust=False).mean()

    @staticmethod
    def sma(close: "pd.Series", period: int) -> "pd.Series":
        return close.rolling(period).mean()

    @staticmethod
    def macd(close: "pd.Series", fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, "pd.Series"]:
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return {"macd": macd_line, "signal": signal_line, "histogram": histogram}

    @staticmethod
    def atr(high: "pd.Series", low: "pd.Series", close: "pd.Series", period: int = 14) -> "pd.Series":
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ], axis=1).max(axis=1)
        return tr.rolling(period).mean()

    @staticmethod
    def bollinger_bands(close: "pd.Series", period: int = 20, std_dev: float = 2.0) -> Dict[str, "pd.Series"]:
        sma = close.rolling(period).mean()
        std = close.rolling(period).std()
        return {
            "upper": sma + std_dev * std,
            "middle": sma,
            "lower": sma - std_dev * std,
        }

    @classmethod
    def compute_all(cls, df: "pd.DataFrame") -> "pd.DataFrame":
        """Compute all indicators and add them to the DataFrame."""
        df = df.copy()
        close = df["close"]
        df["rsi"] = cls.rsi(close)
        df["ema_20"] = cls.ema(close, 20)
        df["ema_50"] = cls.ema(close, 50)
        df["sma_20"] = cls.sma(close, 20)
        macd = cls.macd(close)
        df["macd"] = macd["macd"]
        df["macd_signal"] = macd["signal"]
        df["macd_hist"] = macd["histogram"]
        if all(c in df.columns for c in ["high", "low"]):
            df["atr"] = cls.atr(df["high"], df["low"], close)
            bb = cls.bollinger_bands(close)
            df["bb_upper"] = bb["upper"]
            df["bb_middle"] = bb["middle"]
            df["bb_lower"] = bb["lower"]
        return df


class RiskManager:
    """Manages position sizing and risk controls."""

    def __init__(self, capital: float = 10000.0, risk_per_trade: float = 0.02):
        self.capital = capital
        self.risk_per_trade = risk_per_trade  # 2% of capital per trade

    def position_size(self, entry: float, stop_loss: float) -> float:
        """Calculate position size based on risk per trade."""
        risk_amount = self.capital * self.risk_per_trade
        risk_per_unit = abs(entry - stop_loss)
        if risk_per_unit == 0:
            return 0
        return risk_amount / risk_per_unit

    def check_drawdown(self, current_capital: float, max_drawdown: float = 0.10) -> bool:
        """Return True if drawdown is within acceptable limits."""
        drawdown = (self.capital - current_capital) / self.capital
        return drawdown <= max_drawdown


class BacktestEngine:
    """Simple vectorized backtesting engine."""

    def __init__(self, initial_capital: float = 10000.0, commission: float = 0.001):
        self.initial_capital = initial_capital
        self.commission = commission

    def run(self, df: "pd.DataFrame", signals: "pd.Series") -> Dict[str, Any]:
        """
        Run a backtest given price data and buy/sell signals.
        signals: Series of 1 (buy), -1 (sell), 0 (hold)
        """
        if not HAS_PANDAS:
            return {"error": "pandas not available"}

        capital = self.initial_capital
        position = 0.0
        trades = []
        equity_curve = []

        for i, (idx, row) in enumerate(df.iterrows()):
            price = row["close"]
            signal = signals.iloc[i] if i < len(signals) else 0

            if signal == 1 and position == 0:
                # Buy
                shares = (capital * 0.95) / price
                cost = shares * price * (1 + self.commission)
                if cost <= capital:
                    position = shares
                    capital -= cost
                    trades.append({"type": "BUY", "price": price, "shares": shares, "date": str(idx)})

            elif signal == -1 and position > 0:
                # Sell
                proceeds = position * price * (1 - self.commission)
                capital += proceeds
                trades.append({"type": "SELL", "price": price, "shares": position, "date": str(idx)})
                position = 0

            equity_curve.append(capital + position * price)

        # Final close
        if position > 0:
            final_price = df["close"].iloc[-1]
            capital += position * final_price * (1 - self.commission)

        total_return = (capital - self.initial_capital) / self.initial_capital * 100
        num_trades = len([t for t in trades if t["type"] == "BUY"])

        return {
            "initial_capital": self.initial_capital,
            "final_capital": round(capital, 2),
            "total_return_pct": round(total_return, 2),
            "num_trades": num_trades,
            "trades": trades[-10:],  # Last 10 trades
        }


class TradingAgent:
    """
    Full-featured trading intelligence agent.
    Handles market analysis, indicator computation, signal generation,
    backtesting, risk management, and paper trading.
    """

    def __init__(self, memory: MemorySystem):
        self.memory = memory
        self.indicator_engine = IndicatorEngine()
        self.risk_manager = RiskManager()
        self.backtest_engine = BacktestEngine()
        self.paper_portfolio: Dict[str, Any] = {
            "cash": 10000.0,
            "positions": {},
            "trade_history": [],
        }
        logger.info("TradingAgent initialized.")

    def _to_dataframe(self, data: List[Dict]) -> Optional["pd.DataFrame"]:
        """Convert list of OHLCV dicts to a DataFrame."""
        if not HAS_PANDAS:
            return None
        required = {"close"}
        if not data or not required.issubset(data[0].keys()):
            return None
        df = pd.DataFrame(data)
        df = df.sort_index()
        return df

    def analyze_market(self, symbol: str, data: List[Dict]) -> Dict[str, Any]:
        """
        Analyze market data and generate a trading signal.
        Returns signal, reasoning, and key indicator values.
        """
        if not HAS_PANDAS:
            return {"symbol": symbol, "signal": "NEUTRAL", "reason": "pandas not available"}

        df = self._to_dataframe(data)
        if df is None or len(df) < 30:
            return {"symbol": symbol, "signal": "NEUTRAL", "reason": "Insufficient data"}

        df = self.indicator_engine.compute_all(df)
        latest = df.iloc[-1]

        signals = []
        reasons = []

        # RSI signals
        rsi = latest.get("rsi", 50)
        if rsi < 30:
            signals.append(1)
            reasons.append(f"RSI={rsi:.1f} (oversold)")
        elif rsi > 70:
            signals.append(-1)
            reasons.append(f"RSI={rsi:.1f} (overbought)")
        else:
            signals.append(0)
            reasons.append(f"RSI={rsi:.1f} (neutral)")

        # MACD signals
        macd_hist = latest.get("macd_hist", 0)
        prev_hist = df.iloc[-2].get("macd_hist", 0) if len(df) > 1 else 0
        if macd_hist > 0 and prev_hist <= 0:
            signals.append(1)
            reasons.append("MACD bullish crossover")
        elif macd_hist < 0 and prev_hist >= 0:
            signals.append(-1)
            reasons.append("MACD bearish crossover")
        else:
            signals.append(0)

        # EMA trend
        ema_20 = latest.get("ema_20", latest["close"])
        ema_50 = latest.get("ema_50", latest["close"])
        if ema_20 > ema_50:
            signals.append(1)
            reasons.append("EMA20 > EMA50 (uptrend)")
        else:
            signals.append(-1)
            reasons.append("EMA20 < EMA50 (downtrend)")

        # Consensus
        score = sum(signals)
        if score >= 2:
            signal = "BUY"
        elif score <= -2:
            signal = "SELL"
        else:
            signal = "NEUTRAL"

        result = {
            "symbol": symbol,
            "signal": signal,
            "score": score,
            "reasons": reasons,
            "rsi": round(float(rsi), 2),
            "macd_hist": round(float(macd_hist), 4),
            "close": round(float(latest["close"]), 4),
            "timestamp": datetime.now().isoformat(),
        }

        # Store in memory
        asyncio.get_event_loop().run_until_complete(
            self.memory.add_experience(
                f"TRADING ANALYSIS [{symbol}]: Signal={signal}, Score={score}, Reasons={reasons}",
                source="trading_agent",
            )
        ) if not asyncio.get_event_loop().is_running() else None

        logger.info(f"Trading analysis [{symbol}]: {signal} (score={score})")
        return result

    async def analyze_market_async(self, symbol: str, data: List[Dict]) -> Dict[str, Any]:
        """Async version of analyze_market."""
        result = self.analyze_market(symbol, data)
        await self.memory.add_experience(
            f"TRADING ANALYSIS [{symbol}]: Signal={result['signal']}, Score={result.get('score', 0)}",
            source="trading_agent",
        )
        return result

    def generate_signals(self, df: "pd.DataFrame") -> "pd.Series":
        """Generate buy/sell signals for backtesting."""
        if not HAS_PANDAS:
            return None
        df = self.indicator_engine.compute_all(df)
        signals = pd.Series(0, index=df.index)

        # Simple RSI + MACD strategy
        buy = (df["rsi"] < 35) & (df["macd_hist"] > 0)
        sell = (df["rsi"] > 65) & (df["macd_hist"] < 0)
        signals[buy] = 1
        signals[sell] = -1
        return signals

    async def backtest_strategy(self, data: List[Dict], strategy_params: Optional[Dict] = None) -> Dict[str, Any]:
        """Run a backtest on historical data."""
        if not HAS_PANDAS:
            return {"error": "pandas not available"}

        df = self._to_dataframe(data)
        if df is None or len(df) < 50:
            return {"error": "Insufficient data for backtesting (need 50+ candles)"}

        signals = self.generate_signals(df)
        result = self.backtest_engine.run(df, signals)

        await self.memory.add_experience(
            f"BACKTEST RESULT: Return={result['total_return_pct']}%, Trades={result['num_trades']}",
            source="trading_agent",
        )
        logger.info(f"Backtest complete: {result['total_return_pct']}% return over {result['num_trades']} trades")
        return result

    async def paper_trade(self, symbol: str, signal: str, price: float, quantity: float = 1.0) -> Dict[str, Any]:
        """Execute a paper trade based on a signal."""
        portfolio = self.paper_portfolio
        trade = {"symbol": symbol, "signal": signal, "price": price, "quantity": quantity, "timestamp": datetime.now().isoformat()}

        if signal == "BUY":
            cost = price * quantity
            if portfolio["cash"] >= cost:
                portfolio["cash"] -= cost
                portfolio["positions"][symbol] = portfolio["positions"].get(symbol, 0) + quantity
                trade["status"] = "EXECUTED"
                logger.info(f"Paper BUY {quantity} {symbol} @ {price}")
            else:
                trade["status"] = "REJECTED (insufficient cash)"
        elif signal == "SELL":
            held = portfolio["positions"].get(symbol, 0)
            if held >= quantity:
                portfolio["cash"] += price * quantity
                portfolio["positions"][symbol] = held - quantity
                trade["status"] = "EXECUTED"
                logger.info(f"Paper SELL {quantity} {symbol} @ {price}")
            else:
                trade["status"] = "REJECTED (insufficient position)"
        else:
            trade["status"] = "NO ACTION (neutral)"

        portfolio["trade_history"].append(trade)
        await self.memory.add_experience(
            f"PAPER TRADE [{symbol}]: {signal} @ {price} — {trade['status']}",
            source="trading_agent",
        )
        return trade

    def get_portfolio_summary(self, current_prices: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """Return a summary of the paper portfolio."""
        portfolio = self.paper_portfolio
        positions_value = 0.0
        if current_prices:
            for sym, qty in portfolio["positions"].items():
                positions_value += current_prices.get(sym, 0) * qty
        total_value = portfolio["cash"] + positions_value
        return {
            "cash": round(portfolio["cash"], 2),
            "positions": portfolio["positions"],
            "positions_value": round(positions_value, 2),
            "total_value": round(total_value, 2),
            "total_trades": len(portfolio["trade_history"]),
        }
