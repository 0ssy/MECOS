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
from trading.stability_layer import StabilityLayer
from trading.trade_journal import TradeJournal
from trading.post_mortem import PostMortemEngine
from trading.signal_weighter import SignalWeighter
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


def test_stability_layer_data_sanitize_and_circuit_breaker(tmp_path: Path):
    layer = StabilityLayer(
        state_path=str(tmp_path / "state.json"),
        max_losses=2,
        window_hours=24,
        cooldown_minutes=30,
    )
    bars = [
        {"close": 100.0, "open": 99.5, "high": 101.0, "low": 99.0, "volume": 10.0},
        {"close": float("nan"), "open": 100.0, "high": 101.0, "low": 99.0, "volume": 8.0},
        {"close": 101.0, "open": 100.5, "high": 101.5, "low": 100.2, "volume": 12.0},
    ]
    cleaned = layer.sanitize_bars("BTC/USDT", bars, min_bars=2)
    assert len(cleaned) == 2
    layer.record_trade_close("BTC/USDT", pnl=-5.0)
    layer.record_trade_close("BTC/USDT", pnl=-2.0)
    assert layer.circuit_breaker.should_halt() is True


def test_trade_journal_post_mortem_and_signal_weighter(tmp_path: Path):
    journal_path = tmp_path / "trade_journal.jsonl"
    state_path = tmp_path / "trade_journal_state.json"
    weights_path = tmp_path / "signal_weights.json"

    journal = TradeJournal(journal_file=str(journal_path), state_file=str(state_path))
    trade_id_1 = journal.record_entry(
        ticker="BTC-USD",
        action="BUY",
        price=100.0,
        size=1.0,
        reasoning={"rsi": 32, "regime": "bull", "sentiment": 0.6},
    )
    journal.record_exit(trade_id_1, exit_price=105.0, exit_reason="take_profit", pnl=5.0, outcome="win")

    trade_id_2 = journal.record_entry(
        ticker="ETH-USD",
        action="BUY",
        price=50.0,
        size=2.0,
        reasoning={"rsi": 70, "regime": "bear", "sentiment": -0.4},
    )
    journal.record_exit(trade_id_2, exit_price=48.0, exit_reason="stop_loss", pnl=-4.0, outcome="loss")

    post = PostMortemEngine(journal_file=str(journal_path))
    accuracy = post.analyse_signal_accuracy()
    assert "rsi" in accuracy and accuracy["rsi"]["sample_size"] == 2
    worst = post.worst_trades(1)
    assert len(worst) == 1 and worst[0]["pnl"] < 0

    weighter = SignalWeighter(weights_file=str(weights_path))
    old_weights = dict(weighter.weights)
    weighter.update_from_postmortem(
        {
            "rsi": {"win_rate": 0.75, "sample_size": 25},
            "sentiment": {"win_rate": 0.30, "sample_size": 25},
        }
    )
    assert weighter.weights["rsi"] > old_weights["rsi"]
    assert weighter.weights["sentiment"] < old_weights["sentiment"]
    score = weighter.score_opportunity(
        {"rsi": 35, "regime": "bull", "sentiment": 0.7, "macro": "risk_on", "pattern": 0.4, "timeframe": 0.6}
    )
    assert 0.0 <= score <= 1.0
