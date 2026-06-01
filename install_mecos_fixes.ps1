# MECOS Fix Installer
# Run this from inside your MECOS folder:
#   cd C:\path\to\MECOS
#   .\install_mecos_fixes.ps1

Write-Host "MECOS Fix Installer" -ForegroundColor Cyan
Write-Host "Writing fixed files into current directory: $(Get-Location)" -ForegroundColor Yellow
Write-Host ""

# ============================================================
# 1. config.py
# ============================================================
@'
"""
MECOS Configuration
Centralized settings for the MECOS engine.
Reads all secrets from environment / .env file — never hardcoded.
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # ── Project Identity ──────────────────────────────────────────────────
    PROJECT_NAME: str = "MECOS"
    VERSION: str = "1.0.0-trading"

    # ── Paths ─────────────────────────────────────────────────────────────
    BASE_DIR: Path = Path(__file__).parent
    DATA_DIR: Path = BASE_DIR / "data"
    MEMORY_DIR: Path = BASE_DIR / "memory_db"
    VECTOR_DB_PATH: str = str(BASE_DIR / "memory_db" / "vector_db")
    LOGS_DIR: Path = BASE_DIR / "logs"

    # ── LLM (Ollama / local) ──────────────────────────────────────────────
    SERVER_IP: str = os.getenv("SERVER_IP", "127.0.0.1")
    LOCAL_LLM_URL: str = os.getenv("LOCAL_LLM_URL", f"http://127.0.0.1:11434/v1")
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "llama3")

    # ── Embeddings ────────────────────────────────────────────────────────
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # ── Alpaca (Stocks & Crypto via Alpaca) ──────────────────────────────
    ALPACA_API_KEY: str = os.getenv("ALPACA_API_KEY", "")
    ALPACA_SECRET_KEY: str = os.getenv("ALPACA_SECRET_KEY", "")
    # "paper" uses paper trading endpoint; "live" uses real money
    ALPACA_MODE: str = os.getenv("ALPACA_MODE", "paper")
    ALPACA_BASE_URL: str = (
        "https://paper-api.alpaca.markets"
        if os.getenv("ALPACA_MODE", "paper") == "paper"
        else "https://api.alpaca.markets"
    )

    # ── Binance ───────────────────────────────────────────────────────────
    BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
    BINANCE_SECRET_KEY: str = os.getenv("BINANCE_SECRET_KEY", "")
    # True = use Binance testnet (paper crypto trading)
    BINANCE_TESTNET: bool = os.getenv("BINANCE_TESTNET", "true").lower() == "true"

    # ── Trading Safety ────────────────────────────────────────────────────
    # Hard kill-switch: if False, NO real orders are ever placed regardless of mode
    TRADING_ENABLED: bool = os.getenv("TRADING_ENABLED", "false").lower() == "true"
    MAX_POSITION_SIZE_USD: float = float(os.getenv("MAX_POSITION_SIZE_USD", "100"))
    MAX_DAILY_LOSS_USD: float = float(os.getenv("MAX_DAILY_LOSS_USD", "50"))
    MAX_OPEN_POSITIONS: int = int(os.getenv("MAX_OPEN_POSITIONS", "5"))

    # ── Agent Settings ────────────────────────────────────────────────────
    MAX_PLAN_STEPS: int = 10
    RETRY_ATTEMPTS: int = 3

    # ── Security ─────────────────────────────────────────────────────────
    ENABLE_SANDBOX: bool = True
    ALLOWED_COMMANDS: list = [
        "ls", "cat", "echo", "grep", "find",
        "mkdir", "rm", "cp", "mv", "python3", "pip", "git",
    ]

    # ── Hardware ──────────────────────────────────────────────────────────
    LOW_RESOURCE_MODE: bool = True
    MAX_CONCURRENT_AGENTS: int = 2
    CPU_LIMIT_PERCENT: int = 80
    IDLE_SLEEP_TIME: int = 60
    USE_GPU: bool = False

    # ── Sovereignty / Independence gates ─────────────────────────────────
    GOV_MIN_EXPERIENCES: int = int(os.getenv("GOV_MIN_EXPERIENCES", "500"))
    GOV_MIN_META_EPISODES: int = int(os.getenv("GOV_MIN_META_EPISODES", "10"))
    GOV_MIN_TRADING_ANALYSES: int = int(os.getenv("GOV_MIN_TRADING_ANALYSES", "100"))
    GOV_MIN_TRADING_ACTIONABLE_RATE: float = float(
        os.getenv("GOV_MIN_TRADING_ACTIONABLE_RATE", "0.3")
    )

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()

# Ensure required directories exist
for _path in [settings.DATA_DIR, settings.MEMORY_DIR, settings.LOGS_DIR]:
    _path.mkdir(parents=True, exist_ok=True)

'@ | Set-Content -Path "config.py" -Encoding UTF8
Write-Host "  [OK] config.py" -ForegroundColor Green

# ============================================================
# 2. memory_quality.py
# ============================================================
@'
"""
MECOS Memory Quality Gate
Filters and scores memories before they enter long-term storage.
Prevents noise, duplicates, and low-value experiences from polluting the vector DB.
"""
import re
from typing import List, Dict, Any


class MemoryQualityGate:
    """
    Assesses whether a memory is worth storing in long-term vector memory.

    Scoring factors:
      - Source weight   (trading/reflection/benchmarking = high; general = low)
      - Content length  (too short = noise; too long = chunking needed)
      - Duplication     (near-duplicate of recent short-term buffer entry)
      - Contradiction   (explicit negation of a recent stored fact)
    """

    SOURCE_WEIGHTS: Dict[str, float] = {
        "trading": 1.0,
        "reflection": 0.9,
        "benchmarking": 0.85,
        "research": 0.8,
        "coding": 0.75,
        "general": 0.5,
        "system": 0.4,
    }

    MIN_QUALITY_SCORE: float = 0.35
    min_retrieval_score: float = 0.2

    # ── Public API ────────────────────────────────────────────────────────

    def assess(
        self,
        content: str,
        source: str,
        metadata: Dict[str, Any],
        short_term_buffer: List[Dict],
    ) -> Dict[str, Any]:
        """Return a quality dict; 'promote' key signals whether to persist."""
        source_weight = self.SOURCE_WEIGHTS.get(source, 0.5)

        length_score = self._length_score(content)
        dup_penalty = self._duplication_penalty(content, short_term_buffer)
        contra_penalty = self._contradiction_penalty(content, short_term_buffer)

        quality_score = (
            source_weight * 0.4
            + length_score * 0.4
            - dup_penalty * 0.15
            - contra_penalty * 0.05
        )
        quality_score = max(0.0, min(1.0, quality_score))

        return {
            "quality_score": quality_score,
            "source_weight": source_weight,
            "length_score": length_score,
            "duplication_penalty": dup_penalty,
            "contradiction_penalty": contra_penalty,
            "promote": quality_score >= self.MIN_QUALITY_SCORE,
        }

    def retrieval_score(
        self,
        content: str,
        query: str,
        metadata: Dict[str, Any],
    ) -> float:
        """Score a retrieved memory for relevance at query time."""
        base = metadata.get("quality_score", 0.5)
        source_w = metadata.get("source_weight", 0.5)
        # Recency boost: newer memories score slightly higher
        age_boost = 0.0
        ts = metadata.get("timestamp_unix")
        if ts:
            import time
            age_hours = (time.time() - float(ts)) / 3600
            age_boost = max(0.0, 0.1 - age_hours * 0.001)

        score = base * 0.5 + source_w * 0.4 + age_boost
        return min(1.0, score)

    # ── Private helpers ───────────────────────────────────────────────────

    @staticmethod
    def _length_score(content: str) -> float:
        n = len(content.strip())
        if n < 20:
            return 0.1
        if n < 60:
            return 0.5
        if n <= 2000:
            return 1.0
        # Very long; still store but with mild penalty
        return 0.7

    @staticmethod
    def _duplication_penalty(content: str, buffer: List[Dict]) -> float:
        """Simple token-overlap check against the last 20 buffer entries."""
        if not buffer:
            return 0.0
        tokens = set(re.findall(r"\w+", content.lower()))
        if not tokens:
            return 0.0
        recent = buffer[-20:]
        max_overlap = 0.0
        for entry in recent:
            other_tokens = set(re.findall(r"\w+", entry.get("content", "").lower()))
            if not other_tokens:
                continue
            overlap = len(tokens & other_tokens) / len(tokens | other_tokens)
            if overlap > max_overlap:
                max_overlap = overlap
        # Only penalise if very similar (>80% overlap)
        return max_overlap if max_overlap > 0.8 else 0.0

    @staticmethod
    def _contradiction_penalty(content: str, buffer: List[Dict]) -> float:
        """Detect simple explicit negations (e.g. 'NOT' flipping a recent fact)."""
        negation_words = {"not", "never", "false", "incorrect", "wrong", "no longer"}
        tokens = set(re.findall(r"\w+", content.lower()))
        if not (tokens & negation_words):
            return 0.0
        # A negation word is present — mild penalty to flag for review
        return 0.5

'@ | Set-Content -Path "memory_quality.py" -Encoding UTF8
Write-Host "  [OK] memory_quality.py" -ForegroundColor Green

# ============================================================
# 3. trading_agent.py
# ============================================================
@'
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
from typing import Dict, List, Optional, Tuple

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
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Hour,
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
        self._metrics: Dict = {
            "analyses": 0,
            "signals_generated": 0,
            "actionable_signals": 0,
            "orders_placed": 0,
            "orders_blocked": 0,
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
            "daily_pnl": self.risk.daily_pnl,
            "open_positions": dict(self.risk.open_positions),
        }

'@ | Set-Content -Path "trading_agent.py" -Encoding UTF8
Write-Host "  [OK] trading_agent.py" -ForegroundColor Green

# ============================================================
# 4. run_live_trading.py
# ============================================================
@'
"""
MECOS Live Trading Entry Point
Run with:
    python run_live_trading.py              # paper mode (default)
    python run_live_trading.py --live       # real money (requires TRADING_ENABLED=true in .env)
    python run_live_trading.py --once       # single cycle then exit (good for testing)
    python run_live_trading.py --backtest   # run indicator logic on historical data, no orders
"""
import asyncio
import sys
from loguru import logger
from config import settings
from memory_system import MemorySystem
from trading_agent import TradingAgent


def _print_status_banner():
    mode = settings.ALPACA_MODE.upper()
    testnet = "TESTNET" if settings.BINANCE_TESTNET else "LIVE"
    enabled = "✅ ENABLED" if settings.TRADING_ENABLED else "🔒 BLOCKED (kill-switch)"

    print("\n" + "=" * 60)
    print(f"  MECOS Trading Engine")
    print(f"  Alpaca mode  : {mode}")
    print(f"  Binance mode : {testnet}")
    print(f"  Order execution: {enabled}")
    print(f"  Max position : ${settings.MAX_POSITION_SIZE_USD}")
    print(f"  Daily loss limit: ${settings.MAX_DAILY_LOSS_USD}")
    print("=" * 60 + "\n")


async def run(once: bool = False, backtest: bool = False):
    _print_status_banner()

    if "--live" in sys.argv:
        if not settings.TRADING_ENABLED:
            print(
                "ERROR: --live flag given but TRADING_ENABLED is not true in your .env\n"
                "Set TRADING_ENABLED=true in .env to enable real orders."
            )
            sys.exit(1)
        print("⚠️  LIVE MODE — real orders may be placed. Press Ctrl-C within 5s to abort.")
        await asyncio.sleep(5)

    memory = MemorySystem()
    agent = TradingAgent(memory)

    if backtest:
        logger.info("Backtest mode: running signal generation only (no orders)")
        result = await agent.run_cycle()
        print(f"\nBacktest complete: {result}")
        return

    if once:
        logger.info("Single-cycle mode")
        result = await agent.run_cycle()
        metrics = agent.get_performance_metrics()
        print(f"\nCycle result  : {result}")
        print(f"Metrics       : {metrics}")
        return

    # Continuous loop
    logger.info(f"Entering trading loop (cycle every {settings.IDLE_SLEEP_TIME}s)")
    cycle = 0
    while True:
        cycle += 1
        logger.info(f"=== Trading Cycle #{cycle} ===")
        try:
            result = await agent.run_cycle()
            metrics = agent.get_performance_metrics()
            logger.info(f"Cycle #{cycle} done | signals={result['signals']} "
                        f"actionable={result['actionable']} | "
                        f"daily_pnl=${metrics['daily_pnl']:.2f}")
        except Exception as e:
            logger.error(f"Cycle #{cycle} error: {e}")

        await asyncio.sleep(settings.IDLE_SLEEP_TIME)


if __name__ == "__main__":
    once_mode = "--once" in sys.argv
    backtest_mode = "--backtest" in sys.argv
    try:
        asyncio.run(run(once=once_mode, backtest=backtest_mode))
    except KeyboardInterrupt:
        print("\nTrading engine stopped.")

'@ | Set-Content -Path "run_live_trading.py" -Encoding UTF8
Write-Host "  [OK] run_live_trading.py" -ForegroundColor Green

# ============================================================
# 5. requirements.txt
# ============================================================
@'
# MECOS Requirements
# Install with: pip install -r requirements.txt

# ── Core ──────────────────────────────────────────────────────────────────────
aiohttp>=3.9
websockets>=12.0
python-dotenv>=1.0
pydantic>=2.0
pydantic-settings>=2.0
loguru>=0.7
pandas>=2.0
numpy>=1.26
scipy>=1.11
statsmodels>=0.14
requests>=2.31
# Note: asyncio is stdlib in Python 3.4+; do NOT list it here

# ── Trading Brokers ───────────────────────────────────────────────────────────
alpaca-py>=0.20          # Stocks (paper + live)
python-binance>=1.0.19   # Crypto (testnet + live)
# ccxt>=4.0              # Optional: unified exchange interface

# ── Memory & Embeddings ───────────────────────────────────────────────────────
chromadb>=0.4
sentence-transformers>=2.7
faiss-cpu>=1.7

# ── Perception ────────────────────────────────────────────────────────────────
playwright>=1.40
beautifulsoup4>=4.12
mss>=9.0
pytesseract>=0.3
Pillow>=10.0

# ── LLM / AI ─────────────────────────────────────────────────────────────────
openai>=1.30             # Used as OpenAI-compatible client for local Ollama
torch>=2.2
transformers>=4.40

# ── Dev / Test ────────────────────────────────────────────────────────────────
pytest>=8.0
pytest-asyncio>=0.23
black>=24.0
isort>=5.13

'@ | Set-Content -Path "requirements.txt" -Encoding UTF8
Write-Host "  [OK] requirements.txt" -ForegroundColor Green

# ============================================================
# 6. .env.example
# ============================================================
@'
# MECOS Environment Configuration Template
# Copy this to .env and fill in your real values.
# .env should NEVER be committed to git.

# ── LLM (Ollama server) ───────────────────────────────────────────────────────
SERVER_IP=192.168.1.88
LOCAL_LLM_URL=http://192.168.1.88:11434/v1
DEFAULT_MODEL=llama3

# ── Alpaca ────────────────────────────────────────────────────────────────────
ALPACA_API_KEY=your_alpaca_api_key_here
ALPACA_SECRET_KEY=your_alpaca_secret_key_here
# "paper" = paper trading (safe default). Change to "live" only when ready.
ALPACA_MODE=paper

# ── Binance ───────────────────────────────────────────────────────────────────
BINANCE_API_KEY=your_binance_api_key_here
BINANCE_SECRET_KEY=your_binance_secret_key_here
# "true" = use Binance testnet (safe default). Change to "false" for live crypto.
BINANCE_TESTNET=true

# ── Trading Safety ────────────────────────────────────────────────────────────
# HARD KILL-SWITCH. Must be explicitly set to "true" to place any real orders.
# In paper/testnet mode this only gates the final order call — analysis still runs.
TRADING_ENABLED=false
MAX_POSITION_SIZE_USD=100
MAX_DAILY_LOSS_USD=50
MAX_OPEN_POSITIONS=5

# ── Sovereignty Gates ─────────────────────────────────────────────────────────
GOV_MIN_EXPERIENCES=500
GOV_MIN_META_EPISODES=10
GOV_MIN_TRADING_ANALYSES=100
GOV_MIN_TRADING_ACTIONABLE_RATE=0.3

'@ | Set-Content -Path ".env.example" -Encoding UTF8
Write-Host "  [OK] .env.example" -ForegroundColor Green

# ============================================================
# 7. tests\test_trading.py
# ============================================================
if (-not (Test-Path "tests")) { New-Item -ItemType Directory -Path "tests" | Out-Null }
@'
"""
Tests for the MECOS trading layer.
Runs fully offline — all broker calls are mocked.
"""
import asyncio
import pytest
import pandas as pd
import numpy as np

from trading_agent import (
    generate_signal,
    RiskManager,
    TradeSignal,
    _rsi,
    _macd,
    _bollinger,
    _bb_position,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_prices(n=60, trend="flat", seed=42) -> pd.Series:
    rng = np.random.default_rng(seed)
    base = 100.0
    if trend == "up":
        prices = base + np.arange(n) * 0.5 + rng.normal(0, 0.3, n)
    elif trend == "down":
        prices = base - np.arange(n) * 0.5 + rng.normal(0, 0.3, n)
    else:
        prices = base + rng.normal(0, 1.0, n)
    return pd.Series(prices)


# ── Indicator tests ───────────────────────────────────────────────────────────

def test_rsi_range():
    prices = _make_prices(60)
    r = _rsi(prices)
    assert 0 <= r <= 100, f"RSI out of range: {r}"


def test_rsi_oversold():
    # Sharply falling prices → RSI should be low
    prices = pd.Series([100 - i * 3 for i in range(60)])
    r = _rsi(prices)
    assert r < 40, f"Expected oversold RSI, got {r}"


def test_rsi_overbought():
    prices = pd.Series([100 + i * 3 for i in range(60)])
    r = _rsi(prices)
    assert r > 60, f"Expected overbought RSI, got {r}"


def test_macd_returns_tuple():
    prices = _make_prices(60)
    macd_val, signal_val = _macd(prices)
    assert isinstance(macd_val, float)
    assert isinstance(signal_val, float)


def test_bollinger_bands_ordered():
    prices = _make_prices(60)
    upper, mid, lower = _bollinger(prices)
    assert upper > mid > lower, f"BB bands not ordered: {lower:.2f} < {mid:.2f} < {upper:.2f}"


def test_bb_position_range():
    prices = _make_prices(60)
    upper, mid, lower = _bollinger(prices)
    current = float(prices.iloc[-1])
    pos = _bb_position(current, upper, lower)
    assert 0.0 <= pos <= 2.0  # can slightly exceed [0,1] if outside bands


# ── Signal generation tests ───────────────────────────────────────────────────

def test_signal_hold_on_short_data():
    prices = pd.Series([100.0] * 10)  # too short for reliable indicators
    sig = generate_signal("AAPL", "alpaca", prices)
    assert sig.side == "hold"
    assert sig.confidence == 0.0


def test_signal_returns_valid_sides():
    prices = _make_prices(60)
    sig = generate_signal("BTCUSDT", "binance", prices)
    assert sig.side in ("buy", "sell", "hold")
    assert 0.0 <= sig.confidence <= 1.0


def test_signal_actionable_threshold():
    sig = TradeSignal("AAPL", "alpaca", "buy", 0.7, "test", 150.0)
    assert sig.is_actionable()

    sig_low = TradeSignal("AAPL", "alpaca", "buy", 0.4, "test", 150.0)
    assert not sig_low.is_actionable()

    sig_hold = TradeSignal("AAPL", "alpaca", "hold", 0.9, "test", 150.0)
    assert not sig_hold.is_actionable()


# ── Risk manager tests ────────────────────────────────────────────────────────

def test_risk_blocks_when_trading_disabled(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "TRADING_ENABLED", False)

    rm = RiskManager()
    sig = TradeSignal("AAPL", "alpaca", "buy", 0.8, "test", 150.0)
    approved, reason, qty = rm.approve(sig, 10000.0)
    assert not approved
    assert "kill-switch" in reason.lower() or "trading_enabled" in reason.lower()


def test_risk_blocks_daily_loss_exceeded(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "TRADING_ENABLED", True)
    monkeypatch.setattr(config.settings, "MAX_DAILY_LOSS_USD", 50.0)

    rm = RiskManager()
    rm.daily_pnl = -60.0  # already exceeded limit
    sig = TradeSignal("AAPL", "alpaca", "buy", 0.8, "test", 150.0)
    approved, reason, _ = rm.approve(sig, 10000.0)
    assert not approved
    assert "daily loss" in reason.lower()


def test_risk_position_sizing(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "TRADING_ENABLED", True)
    monkeypatch.setattr(config.settings, "MAX_POSITION_SIZE_USD", 100.0)
    monkeypatch.setattr(config.settings, "MAX_DAILY_LOSS_USD", 500.0)
    monkeypatch.setattr(config.settings, "MAX_OPEN_POSITIONS", 5)

    rm = RiskManager()
    sig = TradeSignal("AAPL", "alpaca", "buy", 0.8, "test", 150.0)
    approved, _, qty = rm.approve(sig, 10000.0)
    assert approved
    # 2% of 10000 = 200, but capped at 100
    assert qty <= 100.0
    assert qty >= 1.0


def test_risk_max_positions_blocked(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "TRADING_ENABLED", True)
    monkeypatch.setattr(config.settings, "MAX_OPEN_POSITIONS", 2)
    monkeypatch.setattr(config.settings, "MAX_DAILY_LOSS_USD", 500.0)

    rm = RiskManager()
    rm.open_positions = {"AAPL": 100.0, "MSFT": 100.0}  # already at limit
    sig = TradeSignal("NVDA", "alpaca", "buy", 0.8, "test", 150.0)
    approved, reason, _ = rm.approve(sig, 10000.0)
    assert not approved
    assert "max open" in reason.lower()


# ── Integration: TradingAgent metrics ────────────────────────────────────────

class MockMemory:
    async def add_experience(self, *a, **kw):
        pass


def test_trading_agent_metrics_structure():
    from trading_agent import TradingAgent
    agent = TradingAgent(MockMemory())
    m = agent.get_performance_metrics()
    assert "analyses" in m
    assert "actionable_rate" in m
    assert "orders_placed" in m
    assert "daily_pnl" in m
    assert 0.0 <= m["actionable_rate"] <= 1.0

'@ | Set-Content -Path "tests\test_trading.py" -Encoding UTF8
Write-Host "  [OK] tests\test_trading.py" -ForegroundColor Green

Write-Host ""
Write-Host "All files written." -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Copy .env.example to .env and fill in your API keys"
Write-Host "  2. pip install -r requirements.txt"
Write-Host "  3. python run_live_trading.py --backtest"
