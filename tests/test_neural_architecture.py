import pytest

torch = pytest.importorskip("torch")

from mecos_brain import MECOSBrain
from mecos_transformer import MarketTransformer
from neural_brain_service import NeuralBrainService
from neural_memory import NeuralMemoryBank
from ppo_trainer import PPOTrainer
from temporal_fusion import TemporalFusionTransformer


def test_market_transformer_forward_shapes():
    model = MarketTransformer(n_signals=32, d_model=64, n_heads=4, n_layers=2, d_ff=128, n_actions=5)
    signal_vals = torch.randn(2, 32, 1)
    signal_ids = torch.randint(0, 32, (2, 32))
    out = model(signal_vals, signal_ids)
    assert out["action_logits"].shape == (2, 5)
    assert out["uncertainty"].shape == (2, 1)
    assert out["signal_repr"].shape == (2, 64)


def test_temporal_fusion_forward_shapes():
    model = TemporalFusionTransformer(
        n_past_vars=10,
        n_static_vars=5,
        d_model=16,
        hidden_size=32,
        n_heads=4,
        n_horizons=4,
        n_quantiles=3,
    )
    past_x = torch.randn(2, 30, 10)
    static_x = torch.randn(2, 5)
    out = model(past_x, static_x)
    assert out["predictions"].shape == (2, 4, 3)
    assert out["past_importance"].shape == (2, 10)
    assert out["static_importance"].shape == (2, 5)


def test_neural_memory_read_write():
    bank = NeuralMemoryBank(memory_size=16, key_size=32, value_size=8)
    key = torch.randn(1, 32)
    val = torch.randn(1, 8)
    bank.write(key, val)
    retrieved, weights = bank.read(key, top_k=4)
    assert retrieved.shape == (1, 8)
    assert weights.shape == (1, 16)


def test_ppo_update_runs():
    trainer = PPOTrainer(state_dim=32, n_actions=5, batch_size=8, k_epochs=2)
    for _ in range(8):
        state = torch.randn(32)
        action, log_prob, _, _ = trainer.policy.get_action(state.unsqueeze(0))
        trainer.store_transition(state, action, log_prob, reward=0.1, done=False)
    loss = trainer.update()
    assert loss is not None


def test_mecos_brain_process_smoke():
    brain = MECOSBrain()
    bars = [{"close": 100 + i, "high": 101 + i, "low": 99 + i, "volume": 1000 + i} for i in range(80)]
    signals = {"rsi": 42.0, "macd": 0.1, "regime": "trending", "news_sentiment": 0.2, "fed_rate": 5.2, "vix": 18.0}
    out = brain.process("AAPL", signals, bars)
    assert out["action"] in {"strong_buy", "buy", "hold", "sell", "strong_sell"}
    assert 0.0 <= float(out["uncertainty"]) <= 1.0


def test_neural_brain_service_disabled_mode():
    service = NeuralBrainService(memory_system=None, enabled=False)
    assert service.is_available is False
    assert service.process("SYS", {}, []) == {}
    assert service.runtime_insight({}) == {}
