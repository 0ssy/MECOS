from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn


class ActorCritic(nn.Module):
    """Shared-backbone actor-critic for PPO."""

    def __init__(self, state_dim: int = 256, n_actions: int = 5):
        super().__init__()
        self.backbone = nn.Sequential(
            nn.Linear(state_dim, 512),
            nn.LayerNorm(512),
            nn.GELU(),
            nn.Linear(512, 256),
            nn.LayerNorm(256),
            nn.GELU(),
        )
        self.actor = nn.Sequential(
            nn.Linear(256, 128),
            nn.GELU(),
            nn.Linear(128, n_actions),
            nn.Softmax(dim=-1),
        )
        self.critic = nn.Sequential(
            nn.Linear(256, 128),
            nn.GELU(),
            nn.Linear(128, 1),
        )

    def forward(self, state: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        shared = self.backbone(state)
        return self.actor(shared), self.critic(shared)

    def get_action(self, state: torch.Tensor):
        probs, value = self.forward(state)
        dist = torch.distributions.Categorical(probs)
        action = dist.sample()
        return action, dist.log_prob(action), dist.entropy(), value


class PPOTrainer:
    """Proximal Policy Optimization for simulated trading practice."""

    def __init__(
        self,
        state_dim: int = 256,
        n_actions: int = 5,
        lr: float = 3e-4,
        gamma: float = 0.99,
        eps_clip: float = 0.2,
        k_epochs: int = 10,
        batch_size: int = 64,
    ):
        self.gamma = float(gamma)
        self.eps_clip = float(eps_clip)
        self.k_epochs = int(k_epochs)
        self.batch_size = int(batch_size)

        self.policy = ActorCritic(state_dim=state_dim, n_actions=n_actions)
        self.policy_old = ActorCritic(state_dim=state_dim, n_actions=n_actions)
        self.policy_old.load_state_dict(self.policy.state_dict())

        self.optimizer = torch.optim.Adam(self.policy.parameters(), lr=lr)
        self.mse = nn.MSELoss()

        self.buffer_states: List[torch.Tensor] = []
        self.buffer_actions: List[torch.Tensor] = []
        self.buffer_log_probs: List[torch.Tensor] = []
        self.buffer_rewards: List[float] = []
        self.buffer_dones: List[bool] = []

    def store_transition(self, state: torch.Tensor, action: torch.Tensor, log_prob: torch.Tensor, reward: float, done: bool):
        self.buffer_states.append(state.detach())
        self.buffer_actions.append(action.detach())
        self.buffer_log_probs.append(log_prob.detach())
        self.buffer_rewards.append(float(reward))
        self.buffer_dones.append(bool(done))

    def compute_returns(self) -> torch.Tensor:
        returns = []
        accum = 0.0
        for reward, done in zip(reversed(self.buffer_rewards), reversed(self.buffer_dones)):
            accum = reward + self.gamma * accum * (1.0 - float(done))
            returns.insert(0, accum)
        returns_t = torch.tensor(returns, dtype=torch.float32)
        return (returns_t - returns_t.mean()) / (returns_t.std() + 1e-8)

    def update(self) -> Optional[float]:
        if len(self.buffer_states) < self.batch_size:
            return None
        returns = self.compute_returns()
        old_states = torch.stack(self.buffer_states).detach()
        old_actions = torch.stack(self.buffer_actions).detach().long().squeeze(-1)
        old_log_probs = torch.stack(self.buffer_log_probs).detach().squeeze(-1)

        total_loss = 0.0
        for _ in range(self.k_epochs):
            probs, values = self.policy(old_states)
            dist = torch.distributions.Categorical(probs)
            log_probs = dist.log_prob(old_actions)
            entropy = dist.entropy()
            values = values.squeeze(-1)

            ratios = torch.exp(log_probs - old_log_probs)
            advantages = returns - values.detach()
            advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

            surr1 = ratios * advantages
            surr2 = torch.clamp(ratios, 1.0 - self.eps_clip, 1.0 + self.eps_clip) * advantages
            actor_loss = -torch.min(surr1, surr2).mean()
            critic_loss = self.mse(values, returns)
            entropy_loss = -0.01 * entropy.mean()
            loss = actor_loss + 0.5 * critic_loss + entropy_loss

            self.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.policy.parameters(), 0.5)
            self.optimizer.step()
            total_loss += float(loss.item())

        self.policy_old.load_state_dict(self.policy.state_dict())
        self.buffer_states.clear()
        self.buffer_actions.clear()
        self.buffer_log_probs.clear()
        self.buffer_rewards.clear()
        self.buffer_dones.clear()
        return total_loss / float(self.k_epochs)


class TradingEnvironment:
    """Simple historical market simulator for PPO."""

    ACTIONS = ["strong_buy", "buy", "hold", "sell", "strong_sell"]

    def __init__(self, price_df, initial_balance: float = 10_000.0):
        self.df = price_df.reset_index(drop=True)
        self.initial = float(initial_balance)
        self.reset()

    def reset(self) -> np.ndarray:
        self.balance = float(self.initial)
        self.position = 0.0
        self.step_idx = 60
        self.peak = float(self.initial)
        return self._get_state()

    def _get_state(self) -> np.ndarray:
        row = self.df.iloc[self.step_idx]
        close_window = self.df["Close"].iloc[max(0, self.step_idx - 20) : self.step_idx]
        close_ma = float(close_window.mean() or 1.0)
        return np.array(
            [
                float(row.get("RSI", 50.0)) / 100.0,
                float(row.get("MACD", 0.0)),
                float(row.get("Close", 1.0)) / max(close_ma, 1e-6),
                float(self.balance) / max(self.initial, 1e-6),
                float(self.position),
                float(self.peak - self.balance) / max(self.peak, 1e-6),
            ],
            dtype=np.float32,
        )

    def step(self, action: int):
        price = float(self.df["Close"].iloc[self.step_idx])
        next_price = float(self.df["Close"].iloc[min(self.step_idx + 1, len(self.df) - 1)])

        if action == 0 and self.balance > 0.0:
            self.position = (self.balance * 0.95) / max(price, 1e-6)
            self.balance *= 0.05
        elif action == 1 and self.balance > 0.0:
            invest = self.balance * 0.5
            self.position += invest / max(price, 1e-6)
            self.balance -= invest
        elif action == 3 and self.position > 0.0:
            self.balance += self.position * 0.5 * price
            self.position *= 0.5
        elif action == 4 and self.position > 0.0:
            self.balance += self.position * price * 0.95
            self.position = 0.0

        pre_value = self.balance + self.position * price
        portfolio_value = self.balance + self.position * next_price
        self.peak = max(self.peak, portfolio_value)
        reward = (portfolio_value - pre_value) / max(self.initial, 1e-6)
        drawdown = (self.peak - portfolio_value) / max(self.peak, 1e-6)
        reward -= drawdown * 0.1

        self.step_idx += 1
        done = self.step_idx >= len(self.df) - 1
        return self._get_state(), float(reward), bool(done)
