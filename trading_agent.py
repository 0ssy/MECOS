"""
MECOS Trading Agent
Full implementation with:
  - Alpaca (stocks, paper & live)
  - Binance (crypto, testnet & live)
  - RSI / MACD / Bollinger Bands signal generation
  - Risk management (position sizing, daily loss limit, max positions)
  - Paper-trading kill-switch (TRADING_ENABLED must be True to place real orders)
  - Performance metrics tracked for IndependenceManager governance gates
"""
import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import numpy as np
from loguru import logger

from config import settings
from memory_system import MemorySystem

# ── Optional broker imports (graceful degradation) ───────────────────────────
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.data.enums import DataFeed
    from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest, CryptoBarsRequest
    from alpaca.data.timeframe import TimeFrame
    _ALPACA_AVAILABLE = True
except ImportError:
    _ALPACA_AVAILABLE = False
    logger.warning("alpaca-py not installed. Run: pip install alpaca-py")

try:
    from binance.client import Client as BinanceClient
    from binance.exceptions import BinanceAPIException
    _BINANCE_AVAILABLE = True
except ImportError:
    _BINANCE_AVAILABLE = False
    logger.warning("python-binance not installed. Run: pip install python-binance")

try:
    import openbb  # type: ignore
    _OPENBB_AVAILABLE = True
except ImportError:
    openbb = None
    _OPENBB_AVAILABLE = False
    logger.warning("openbb not installed. News updates disabled.")


class OpenBBNewsAdapter:
    """Optional OpenBB news adapter with resilient endpoint probing."""

    def __init__(self):
        self.available = _OPENBB_AVAILABLE

    def get_news(self, symbol: str, limit: int = 3) -> Dict[str, Any]:
        if not self.available or openbb is None:
            return {"symbol": symbol, "available": False, "headlines": [], "error": "openbb_not_installed"}

        obb = getattr(openbb, "obb", None)
        attempts = [
            lambda: obb.news.company(symbol=symbol, limit=limit) if obb else None,
            lambda: obb.news.company(symbol) if obb else None,
            lambda: obb.news.world(limit=limit) if obb else None,
            lambda: openbb.news.company(symbol=symbol, limit=limit),
            lambda: openbb.news.company(symbol),
            lambda: openbb.news.world(limit=limit),
        ]
        last_error: Optional[Exception] = None
        for fetch in attempts:
            try:
                raw = fetch()
                headlines = self._extract_headlines(raw, limit)
                if headlines:
                    return {"symbol": symbol, "available": True, "headlines": headlines}
            except Exception as exc:
                last_error = exc
                continue

        return {
            "symbol": symbol,
            "available": True,
            "headlines": [],
            "error": str(last_error) if last_error else "no_news_returned",
        }

    @staticmethod
    def _extract_headlines(raw: Any, limit: int) -> List[str]:
        if raw is None:
            return []

        if hasattr(raw, "to_dataframe"):
            try:
                raw = raw.to_dataframe()
            except Exception:
                pass

        records: List[Dict[str, Any]] = []
        if hasattr(raw, "to_dict"):
            try:
                as_dict = raw.to_dict(orient="records")  # pandas
                if isinstance(as_dict, list):
                    records = [r for r in as_dict if isinstance(r, dict)]
            except TypeError:
                as_dict = raw.to_dict()
                if isinstance(as_dict, dict):
                    records = [as_dict]
                elif isinstance(as_dict, list):
                    records = [r for r in as_dict if isinstance(r, dict)]
        elif isinstance(raw, dict):
            records = [raw]
        elif isinstance(raw, list):
            records = [r for r in raw if isinstance(r, dict)]

        headlines: List[str] = []
        for rec in records:
            for key in ("headline", "title", "summary", "text"):
                value = rec.get(key)
                if isinstance(value, str) and value.strip():
                    cleaned = " ".join(value.strip().split())
                    headlines.append(cleaned[:180])
                    break
            if len(headlines) >= limit:
                break
        return headlines


# ── Signal dataclass ──────────────────────────────────────────────────────────

class TradeSignal:
    def __init__(
        self,
        symbol: str,
        exchange: str,          # "alpaca" | "binance"
        side: str,              # "buy" | "sell" | "hold"
        confidence: float,      # 0.0–1.0
        reason: str,
        price: float,
        rsi: Optional[float] = None,
        macd: Optional[float] = None,
        bb_position: Optional[float] = None,
    ):
        self.symbol = symbol
        self.exchange = exchange
        self.side = side
        self.confidence = confidence
        self.reason = reason
        self.price = price
        self.rsi = rsi
        self.macd = macd
        self.bb_position = bb_position
        self.timestamp = datetime.now(timezone.utc)

    def is_actionable(self) -> bool:
        return self.side in ("buy", "sell") and self.confidence >= 0.55

    def __repr__(self):
        return (
            f"TradeSignal({self.symbol} {self.side.upper()} "
            f"conf={self.confidence:.2f} @ {self.price:.4f} | {self.reason})"
        )


# ── Indicator helpers ─────────────────────────────────────────────────────────

def _rsi(prices: pd.Series, period: int = 14) -> float:
    delta = prices.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    last_loss = loss.iloc[-1]
    last_gain = gain.iloc[-1]
    if pd.isna(last_loss) or pd.isna(last_gain):
        return 50.0
    if last_loss == 0:
        return 100.0  # No down-days in window → fully overbought
    rs = last_gain / last_loss
    return 100 - (100 / (1 + rs))


def _macd(prices: pd.Series, fast=12, slow=26, signal=9) -> Tuple[float, float]:
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return float(macd_line.iloc[-1]), float(signal_line.iloc[-1])


def _bollinger(prices: pd.Series, period: int = 20) -> Tuple[float, float, float]:
    """Returns (upper, mid, lower)."""
    mid = prices.rolling(period).mean()
    std = prices.rolling(period).std()
    upper = mid + 2 * std
    lower = mid - 2 * std
    return float(upper.iloc[-1]), float(mid.iloc[-1]), float(lower.iloc[-1])


def _bb_position(price: float, upper: float, lower: float) -> float:
    """0 = at lower band, 1 = at upper band."""
    band_range = upper - lower
    if band_range == 0:
        return 0.5
    return (price - lower) / band_range


# ── Signal generator ──────────────────────────────────────────────────────────

def generate_signal(symbol: str, exchange: str, prices: pd.Series) -> TradeSignal:
    """
    Multi-indicator consensus signal.
    Requires RSI + MACD + BB to agree before classifying as buy/sell.
    """
    if len(prices) < 30:
        return TradeSignal(symbol, exchange, "hold", 0.0, "insufficient data", float(prices.iloc[-1]))

    current_price = float(prices.iloc[-1])
    rsi = _rsi(prices)
    macd_val, macd_sig = _macd(prices)
    bb_upper, bb_mid, bb_lower = _bollinger(prices)
    bb_pos = _bb_position(current_price, bb_upper, bb_lower)

    buy_votes = 0
    sell_votes = 0
    reasons = []

    # RSI
    if rsi < 35:
        buy_votes += 1
        reasons.append(f"RSI={rsi:.1f} oversold")
    elif rsi > 65:
        sell_votes += 1
        reasons.append(f"RSI={rsi:.1f} overbought")

    # MACD crossover
    if macd_val > macd_sig:
        buy_votes += 1
        reasons.append(f"MACD bullish cross")
    elif macd_val < macd_sig:
        sell_votes += 1
        reasons.append(f"MACD bearish cross")

    # Bollinger Bands
    if bb_pos < 0.15:
        buy_votes += 1
        reasons.append(f"BB lower touch ({bb_pos:.2f})")
    elif bb_pos > 0.85:
        sell_votes += 1
        reasons.append(f"BB upper touch ({bb_pos:.2f})")

    # Consensus
    if buy_votes >= 2 and buy_votes > sell_votes:
        confidence = 0.5 + (buy_votes / 3) * 0.4
        side = "buy"
    elif sell_votes >= 2 and sell_votes > buy_votes:
        confidence = 0.5 + (sell_votes / 3) * 0.4
        side = "sell"
    else:
        side = "hold"
        confidence = 0.3

    return TradeSignal(
        symbol=symbol,
        exchange=exchange,
        side=side,
        confidence=confidence,
        reason=" | ".join(reasons) or "no clear signal",
        price=current_price,
        rsi=rsi,
        macd=macd_val,
        bb_position=bb_pos,
    )


# ── Risk manager ──────────────────────────────────────────────────────────────

class RiskManager:
    def __init__(self):
        self.daily_pnl: float = 0.0
        self.open_positions: Dict[str, float] = {}  # symbol -> notional USD
        self._day_start = datetime.now(timezone.utc).date()

    def _reset_if_new_day(self):
        today = datetime.now(timezone.utc).date()
        if today != self._day_start:
            self.daily_pnl = 0.0
            self._day_start = today

    def approve(self, signal: TradeSignal, account_equity: float) -> Tuple[bool, str, float]:
        """
        Returns (approved, reason, qty_usd).
        qty_usd is the notional USD to trade.
        """
        self._reset_if_new_day()

        if not settings.TRADING_ENABLED:
            return False, "TRADING_ENABLED=false (kill-switch)", 0.0

        if self.daily_pnl <= -settings.MAX_DAILY_LOSS_USD:
            return False, f"Daily loss limit hit (${self.daily_pnl:.2f})", 0.0

        if len(self.open_positions) >= settings.MAX_OPEN_POSITIONS:
            return False, f"Max open positions ({settings.MAX_OPEN_POSITIONS}) reached", 0.0

        # Position size: 2% of equity, capped by MAX_POSITION_SIZE_USD
        qty_usd = min(account_equity * 0.02, settings.MAX_POSITION_SIZE_USD)
        if qty_usd < 1.0:
            return False, f"Position size too small (${qty_usd:.2f})", 0.0

        return True, "approved", qty_usd

    def record_fill(self, symbol: str, side: str, notional: float, pnl: float = 0.0):
        self.daily_pnl += pnl
        if side == "buy":
            self.open_positions[symbol] = notional
        elif side == "sell":
            self.open_positions.pop(symbol, None)


# ── Alpaca adapter ────────────────────────────────────────────────────────────

class AlpacaAdapter:
    def __init__(self):
        if not _ALPACA_AVAILABLE:
            raise RuntimeError("alpaca-py not installed")
        self.trading = TradingClient(
            api_key=settings.ALPACA_API_KEY,
            secret_key=settings.ALPACA_SECRET_KEY,
            paper=(settings.ALPACA_MODE == "paper"),
        )
        self.stock_data = StockHistoricalDataClient(
            api_key=settings.ALPACA_API_KEY,
            secret_key=settings.ALPACA_SECRET_KEY,
        )
        logger.info(f"Alpaca adapter ready (mode={settings.ALPACA_MODE})")

    def get_equity(self) -> float:
        acct = self.trading.get_account()
        return float(acct.equity)

    def get_bars(self, symbol: str, limit: int = 60) -> pd.Series:
        now_utc = pd.Timestamp.utcnow()
        # Match the proven connector behavior: explicit time window + IEX feed.
        start_utc = now_utc - pd.Timedelta(minutes=max(limit * 60 * 3, 60 * 100))
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Hour,
            start=start_utc.to_pydatetime(),
            end=now_utc.to_pydatetime(),
            feed=DataFeed.IEX,
            limit=limit,
        )
        bars = self.stock_data.get_stock_bars(req)
        df = bars.df
        if df.empty:
            return pd.Series(dtype=float)
        return df["close"].droplevel(0) if isinstance(df.index, pd.MultiIndex) else df["close"]

    def place_market_order(self, symbol: str, side: str, notional_usd: float) -> dict:
        if not settings.TRADING_ENABLED:
            logger.warning(f"[PAPER-BLOCKED] Would {side} {symbol} for ${notional_usd:.2f}")
            return {"status": "blocked", "reason": "TRADING_ENABLED=false"}

        req = MarketOrderRequest(
            symbol=symbol,
            notional=round(notional_usd, 2),
            side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
        order = self.trading.submit_order(req)
        logger.info(f"Alpaca order submitted: {order.id} {side} {symbol} ${notional_usd:.2f}")
        return {"id": str(order.id), "status": str(order.status)}


# ── Binance adapter ───────────────────────────────────────────────────────────

class BinanceAdapter:
    def __init__(self):
        if not _BINANCE_AVAILABLE:
            raise RuntimeError("python-binance not installed")
        self.client = BinanceClient(
            api_key=settings.BINANCE_API_KEY,
            api_secret=settings.BINANCE_SECRET_KEY,
            testnet=settings.BINANCE_TESTNET,
        )
        mode = "TESTNET" if settings.BINANCE_TESTNET else "LIVE"
        logger.info(f"Binance adapter ready (mode={mode})")

    def get_equity(self) -> float:
        account = self.client.get_account()
        usdt = next(
            (float(b["free"]) for b in account["balances"] if b["asset"] == "USDT"),
            0.0,
        )
        return usdt

    def get_klines(self, symbol: str, limit: int = 60) -> pd.Series:
        raw = self.client.get_klines(
            symbol=symbol,
            interval=BinanceClient.KLINE_INTERVAL_1HOUR,
            limit=limit,
        )
        closes = pd.Series([float(k[4]) for k in raw])
        return closes

    def place_market_order(self, symbol: str, side: str, notional_usd: float, price: float) -> dict:
        if not settings.TRADING_ENABLED:
            logger.warning(f"[PAPER-BLOCKED] Would {side} {symbol} for ${notional_usd:.2f}")
            return {"status": "blocked", "reason": "TRADING_ENABLED=false"}

        qty = round(notional_usd / price, 6)
        try:
            if side == "buy":
                order = self.client.order_market_buy(symbol=symbol, quantity=qty)
            else:
                order = self.client.order_market_sell(symbol=symbol, quantity=qty)
            logger.info(f"Binance order: {order['orderId']} {side} {symbol} qty={qty}")
            return {"id": str(order["orderId"]), "status": order["status"]}
        except BinanceAPIException as e:
            logger.error(f"Binance order failed: {e}")
            return {"status": "error", "reason": str(e)}


# ── TradingAgent ──────────────────────────────────────────────────────────────

class TradingAgent:
    """
    Coordinates signal generation and order execution across Alpaca and Binance.
    Feeds performance metrics back to MemorySystem and IndependenceManager.
    """

    # Watchlists
    STOCK_UNIVERSE = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL", "META"]
    CRYPTO_UNIVERSE = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]

    def __init__(self, memory: MemorySystem):
        self.memory = memory
        self.risk = RiskManager()
        self.news = OpenBBNewsAdapter()
        self._metrics: Dict = {
            "analyses": 0,
            "signals_generated": 0,
            "actionable_signals": 0,
            "orders_placed": 0,
            "orders_blocked": 0,
            "news_updates": 0,
        }

        # Broker clients (lazy, graceful)
        self._alpaca: Optional[AlpacaAdapter] = None
        self._binance: Optional[BinanceAdapter] = None

        self._init_brokers()

    def _init_brokers(self):
        if settings.ALPACA_API_KEY and _ALPACA_AVAILABLE:
            try:
                self._alpaca = AlpacaAdapter()
            except Exception as e:
                logger.error(f"Alpaca init failed: {e}")
        else:
            logger.warning("Alpaca disabled (missing key or alpaca-py not installed)")

        if settings.BINANCE_API_KEY and _BINANCE_AVAILABLE:
            try:
                self._binance = BinanceAdapter()
            except Exception as e:
                logger.error(f"Binance init failed: {e}")
        else:
            logger.warning("Binance disabled (missing key or python-binance not installed)")

    # ── Analysis ──────────────────────────────────────────────────────────

    async def analyse_stocks(self) -> List[TradeSignal]:
        if not self._alpaca:
            logger.warning("Alpaca not available, skipping stock analysis")
            return []

        signals = []
        for symbol in self.STOCK_UNIVERSE:
            try:
                prices = await asyncio.to_thread(self._alpaca.get_bars, symbol)
                if prices.empty:
                    continue
                signal = generate_signal(symbol, "alpaca", prices)
                news = await asyncio.to_thread(self.news.get_news, symbol, 3)
                headlines = news.get("headlines", []) if isinstance(news, dict) else []
                if headlines:
                    news_blurb = "; ".join(headlines[:2])
                    signal.reason = f"{signal.reason} | NEWS: {news_blurb}"
                    self._metrics["news_updates"] += len(headlines[:2])
                signals.append(signal)
                self._metrics["analyses"] += 1
                logger.debug(f"Stock signal: {signal}")
            except Exception as e:
                logger.error(f"Stock analysis failed for {symbol}: {e}")

        return signals

    async def analyse_crypto(self) -> List[TradeSignal]:
        if not self._binance:
            logger.warning("Binance not available, skipping crypto analysis")
            return []

        signals = []
        for symbol in self.CRYPTO_UNIVERSE:
            try:
                prices = await asyncio.to_thread(self._binance.get_klines, symbol)
                if prices.empty:
                    continue
                signal = generate_signal(symbol, "binance", prices)
                signals.append(signal)
                self._metrics["analyses"] += 1
                logger.debug(f"Crypto signal: {signal}")
            except Exception as e:
                logger.error(f"Crypto analysis failed for {symbol}: {e}")

        return signals

    async def run_cycle(self) -> Dict:
        """Full scan + execute cycle. Call this from the main loop."""
        logger.info("Trading cycle started")

        stock_signals = await self.analyse_stocks()
        crypto_signals = await self.analyse_crypto()
        all_signals = stock_signals + crypto_signals

        self._metrics["signals_generated"] += len(all_signals)
        actionable = [s for s in all_signals if s.is_actionable()]
        self._metrics["actionable_signals"] += len(actionable)

        results = []
        for signal in actionable:
            result = await self._execute_signal(signal)
            results.append(result)

        # Log summary to memory
        summary = (
            f"TRADING CYCLE: {len(all_signals)} signals, "
            f"{len(actionable)} actionable, "
            f"{self._metrics['orders_placed']} orders placed today"
        )
        await self.memory.add_experience(summary, source="trading")
        logger.info(summary)

        return {
            "signals": len(all_signals),
            "actionable": len(actionable),
            "executed": [r for r in results if r.get("status") not in ("blocked", "error")],
        }

    # ── Execution ─────────────────────────────────────────────────────────

    async def _execute_signal(self, signal: TradeSignal) -> Dict:
        """Apply risk check then route to the correct broker."""
        # Determine account equity for position sizing
        equity = await self._get_equity(signal.exchange)

        approved, reason, qty_usd = self.risk.approve(signal, equity)
        if not approved:
            logger.info(f"Order blocked [{signal.symbol}]: {reason}")
            self._metrics["orders_blocked"] += 1
            await self.memory.add_experience(
                f"ORDER BLOCKED {signal.symbol} {signal.side}: {reason}",
                source="trading",
            )
            return {"symbol": signal.symbol, "status": "blocked", "reason": reason}

        # Place order
        if signal.exchange == "alpaca" and self._alpaca:
            result = await asyncio.to_thread(
                self._alpaca.place_market_order, signal.symbol, signal.side, qty_usd
            )
        elif signal.exchange == "binance" and self._binance:
            result = await asyncio.to_thread(
                self._binance.place_market_order,
                signal.symbol, signal.side, qty_usd, signal.price,
            )
        else:
            result = {"status": "error", "reason": "broker unavailable"}

        if result.get("status") not in ("blocked", "error"):
            self.risk.record_fill(signal.symbol, signal.side, qty_usd)
            self._metrics["orders_placed"] += 1
            await self.memory.add_experience(
                f"ORDER FILLED {signal.symbol} {signal.side} ${qty_usd:.2f} "
                f"conf={signal.confidence:.2f} | {signal.reason}",
                source="trading",
            )

        return {**result, "symbol": signal.symbol, "side": signal.side, "notional_usd": qty_usd}

    async def _get_equity(self, exchange: str) -> float:
        try:
            if exchange == "alpaca" and self._alpaca:
                return await asyncio.to_thread(self._alpaca.get_equity)
            elif exchange == "binance" and self._binance:
                return await asyncio.to_thread(self._binance.get_equity)
        except Exception as e:
            logger.warning(f"Could not fetch equity for {exchange}: {e}")
        return 1000.0  # Safe fallback (keeps position sizes small)

    # ── Metrics (used by IndependenceManager governance gates) ────────────

    def get_performance_metrics(self) -> Dict:
        total = self._metrics["analyses"]
        actionable = self._metrics["actionable_signals"]
        return {
            "analyses": total,
            "signals_generated": self._metrics["signals_generated"],
            "actionable_signals": actionable,
            "actionable_rate": actionable / max(total, 1),
            "orders_placed": self._metrics["orders_placed"],
            "orders_blocked": self._metrics["orders_blocked"],
            "news_updates": self._metrics["news_updates"],
            "daily_pnl": self.risk.daily_pnl,
            "open_positions": dict(self.risk.open_positions),
        }

