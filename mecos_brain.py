from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F

from mecos_transformer import MarketTransformer
from neural_memory import NeuralMemoryBank
from ppo_trainer import PPOTrainer, TradingEnvironment
from temporal_fusion import TemporalFusionTransformer

logger = logging.getLogger("mecos.brain")


class MECOSBrain:
    """
    Optional neural cognition stack for trading:
    transformer + TFT + memory bank + PPO.
    """

    ACTIONS = ["strong_buy", "buy", "hold", "sell", "strong_sell"]

    def __init__(self, memory_system: Any = None):
        self.memory_system = memory_system
        self.transformer = MarketTransformer()
        self.tft = TemporalFusionTransformer()
        self.memory = NeuralMemoryBank(memory_size=10_000, key_size=256, value_size=64)
        self.ppo = PPOTrainer(state_dim=256, n_actions=len(self.ACTIONS))
        self._load_all()
        logger.info("MECOS Brain initialized (memory slots=%d)", 10_000)

    def _load_all(self) -> None:
        self.memory.load()

    def process(self, ticker: str, signals: Dict[str, Any], bars: Any) -> Dict[str, Any]:
        signal_vals, signal_ids = self._encode_signals(signals)
        t_out = self.transformer(signal_vals, signal_ids)
        state_repr = t_out["signal_repr"]
        uncertainty = float(t_out["uncertainty"].squeeze().item())
        expected_value = float(t_out["expected_value"].squeeze().item())

        _, mem_weights = self.memory.read(state_repr)
        past_x, static_x = self._build_tft_inputs(bars, signals)
        tft_out = self.tft(past_x, static_x)
        forecasts = tft_out["predictions"].detach()

        ppo_action, _, _, value = self.ppo.policy.get_action(state_repr)
        action_name = self.ACTIONS[int(ppo_action.item())]
        action_probs = F.softmax(t_out["action_logits"], dim=-1).detach().cpu().numpy()[0].tolist()

        self.memory.write(state_repr.detach(), torch.zeros((1, 64), dtype=state_repr.dtype))
        explanation = self._reason(ticker, signals, action_name, uncertainty)
        return {
            "action": action_name,
            "uncertainty": round(uncertainty, 4),
            "state_value": round(float(value.squeeze().item()), 4),
            "expected_value": round(expected_value, 4),
            "action_probs": action_probs,
            "forecasts": {
                "1h": {"low": float(forecasts[0, 0, 0]), "mid": float(forecasts[0, 0, 1]), "high": float(forecasts[0, 0, 2])},
                "4h": {"low": float(forecasts[0, 1, 0]), "mid": float(forecasts[0, 1, 1]), "high": float(forecasts[0, 1, 2])},
                "1d": {"low": float(forecasts[0, 2, 0]), "mid": float(forecasts[0, 2, 1]), "high": float(forecasts[0, 2, 2])},
                "1w": {"low": float(forecasts[0, 3, 0]), "mid": float(forecasts[0, 3, 1]), "high": float(forecasts[0, 3, 2])},
            },
            "variable_importance": tft_out["past_importance"].detach().cpu().numpy().tolist(),
            "memory_similarity": float(mem_weights.max().item()),
            "explanation": explanation,
        }

    def learn_from_trade(self, state: torch.Tensor, action: int, reward: float, done: bool) -> Optional[float]:
        action_tensor = torch.LongTensor([int(action)])
        if state.dim() == 1:
            state = state.unsqueeze(0)
        _, log_prob, _, _ = self.ppo.policy.get_action(state)
        self.ppo.store_transition(state.squeeze(0), action_tensor, log_prob, float(reward), bool(done))
        if len(self.ppo.buffer_states) >= self.ppo.batch_size:
            return self.ppo.update()
        return None

    def pretrain_on_history(self, price_df, n_episodes: int = 200) -> None:
        env = TradingEnvironment(price_df)
        logger.info("Pretraining PPO for %d episodes", int(n_episodes))
        for episode in range(int(n_episodes)):
            state = env.reset()
            total_reward = 0.0
            while True:
                state_tensor = torch.FloatTensor(state).unsqueeze(0)
                if state_tensor.size(1) < 256:
                    state_tensor = F.pad(state_tensor, (0, 256 - state_tensor.size(1)))
                action, log_prob, _, _ = self.ppo.policy.get_action(state_tensor)
                next_state, reward, done = env.step(int(action.item()))
                self.ppo.store_transition(state_tensor.squeeze(0), action, log_prob, reward, done)
                state = next_state
                total_reward += reward
                if done:
                    break
            if len(self.ppo.buffer_states) >= self.ppo.batch_size:
                self.ppo.update()
            if episode % 50 == 0:
                logger.info("PPO pretrain episode %d/%d | reward=%.4f", episode, n_episodes, total_reward)
        self.memory.save()

    @staticmethod
    def _as_dataframe(bars: Any) -> pd.DataFrame:
        if isinstance(bars, pd.DataFrame):
            return bars.copy()
        if isinstance(bars, list):
            return pd.DataFrame(bars)
        return pd.DataFrame([])

    def _encode_signals(self, signals: Dict[str, Any]) -> Tuple[torch.Tensor, torch.Tensor]:
        signal_map = {
            "rsi": 0,
            "macd": 1,
            "bb_position": 2,
            "fed_rate": 3,
            "inflation": 4,
            "gdp_growth": 5,
            "vix": 6,
            "news_sentiment": 7,
            "social_sentiment": 8,
            "regime_bull": 9,
            "regime_bear": 10,
            "regime_sideways": 11,
            "rsi_1d": 12,
            "rsi_4h": 13,
            "rsi_1h": 14,
            "portfolio_heat": 15,
            "drawdown": 16,
            "win_rate": 17,
            "atr": 18,
            "volume_ratio": 19,
        }
        vals: List[List[float]] = []
        ids: List[int] = []
        for name, idx in signal_map.items():
            raw = signals.get(name, 0.0)
            try:
                vals.append([float(raw)])
            except (TypeError, ValueError):
                vals.append([0.0])
            ids.append(idx)
        while len(vals) < 32:
            vals.append([0.0])
            ids.append(len(signal_map))
        return torch.FloatTensor(vals).unsqueeze(0), torch.LongTensor(ids).unsqueeze(0)

    def _build_tft_inputs(self, bars: Any, signals: Dict[str, Any]) -> Tuple[torch.Tensor, torch.Tensor]:
        df = self._as_dataframe(bars)
        seq_len = min(60, len(df)) if len(df) > 0 else 1
        past = torch.zeros(1, seq_len, 10)
        static = torch.FloatTensor(
            [
                [
                    float(signals.get("portfolio_heat", 0.0)) / 100.0,
                    float(signals.get("drawdown", 0.0)),
                    float(signals.get("win_rate", 0.5)),
                    float(signals.get("fed_rate", 5.0)) / 10.0,
                    float(signals.get("vix", 20.0)) / 100.0,
                ]
            ]
        )
        if len(df) == 0:
            return past, static

        start_idx = max(0, len(df) - seq_len)
        for i, idx in enumerate(range(start_idx, len(df))):
            row = df.iloc[idx]
            close = float(row.get("close", row.get("Close", 0.0)) or 0.0)
            volume = float(row.get("volume", row.get("Volume", 0.0)) or 0.0)
            high = float(row.get("high", row.get("High", close)) or close)
            low = float(row.get("low", row.get("Low", close)) or close)
            past[0, i, :5] = torch.FloatTensor(
                [
                    close,
                    volume,
                    float(signals.get("rsi", 50.0)) / 100.0,
                    float(signals.get("macd", 0.0)),
                    high - low,
                ]
            )
        return past, static

    @staticmethod
    def _reason(ticker: str, signals: Dict[str, Any], action: str, uncertainty: float) -> str:
        rsi = float(signals.get("rsi", 50.0) or 50.0)
        regime = str(signals.get("regime", "unknown"))
        if uncertainty > 0.7:
            return f"{ticker}: high uncertainty, treat {action} as low conviction."
        return f"{ticker}: action={action} based on regime={regime}, rsi={rsi:.1f} and multi-source fusion."
