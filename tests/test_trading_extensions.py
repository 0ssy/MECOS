import json
from pathlib import Path

import pytest

from trading.backtester import SimpleBacktester
from trading.market_data_stream import MarketDataStream
from trading.options_pricing import OptionsEngine
from trading.pipeline_runner import PipelineRunner
from trading.portfolio_optimizer import PortfolioOptimizer
from trading.regime_detector import RegimeDetector
from trading.risk_manager import RiskManager
from trading.terminal_ui import render_signal_dashboard


def test_options_engine_black_scholes_and_iv():
    engine = OptionsEngine()
    call = engine.black_scholes(100, 100, 0.5, 0.05, 0.2, "call")
    iv = engine.implied_volatility(call, 100, 100, 0.5, 0.05, "call")
    greeks = engine.greeks(100, 100, 0.5, 0.05, 0.2, "call")
    assert call > 0
    assert 0.05 <= iv <= 0.40
    assert 0.0 < greeks["delta"] < 1.0


def test_simple_backtester_executes():
    bars = [{"close": 100 + i} for i in range(40)]
    signals = ["BUY"] * 10 + ["HOLD"] * 20 + ["SELL"] * 10
    out = SimpleBacktester().run(bars, signals, size_fraction=0.2)
    assert out["status"] == "OK"
    assert out["trades"] >= 2
    assert "equity_curve" in out and len(out["equity_curve"]) > 0


def test_pipeline_runner_decision():
    cfg = {
        "pipeline": "demo",
        "nodes": [
            {"id": "1", "type": "data_source"},
            {"id": "2", "type": "indicator", "params": {"period": 14}},
            {"id": "3", "type": "signal", "params": {"buy_rsi": 40, "sell_rsi": 60}},
            {"id": "4", "type": "risk_manager", "params": {"max_position": 0.1}},
            {"id": "5", "type": "executor"},
        ],
    }
    bars = [{"open": 100 + i, "high": 101 + i, "low": 99 + i, "close": 100 + i, "volume": 1000 + i} for i in range(80)]
    out = PipelineRunner().run(cfg, bars)
    assert out["status"] == "OK"
    assert out["decision"] in {"BUY", "SELL", "HOLD"}


def test_terminal_ui_output():
    txt = render_signal_dashboard(
        {"AAPL": {"decision": "BUY", "confidence": 0.8, "edge": 0.2, "regime": "trending", "risk_gate_reason": ""}}
    )
    assert "SYMBOL" in txt
    assert "AAPL" in txt


def test_regime_and_optimizer_and_risk_manager():
    prices = [100 + i * 0.2 for i in range(120)]
    regime = RegimeDetector().detect_from_bars(prices)
    opt = PortfolioOptimizer().recommend_single_asset(prices, 0.7, 0.1, regime["regime"])
    rm = RiskManager(10_000, 0.01)
    size = rm.position_size(100, 95)
    assert regime["regime"] in {"bull", "bear", "panic", "sideways", "unknown"}
    assert 0.2 <= float(opt["allocation_multiplier"]) <= 1.3
    assert size > 0


def test_pipeline_runner_load(tmp_path: Path):
    cfg = {"pipeline": "x", "nodes": [{"id": "1", "type": "data_source"}]}
    p = tmp_path / "pipeline.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    loaded = PipelineRunner().load(str(p))
    assert loaded["pipeline"] == "x"


@pytest.mark.asyncio
async def test_public_price_stream_routes_to_market_cache(monkeypatch):
    async def fake_stream(symbols, callback):
        await callback({"symbol": "BTCUSDT", "price": 101.5, "change_pct": 0.2, "volume": 1234.0})

    monkeypatch.setattr("trading.market_data_stream.stream_binance_prices", fake_stream)
    stream = MarketDataStream()
    await stream.stream_public_crypto_data(["BTC/USDT"])
    cache = stream.get_historical_cache("BTC/USDT", lookback=1)
    assert len(cache) == 1
    assert float(cache[0]["close"]) == 101.5
    assert float(cache[0]["volume"]) > 0
