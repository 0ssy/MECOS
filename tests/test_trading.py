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

