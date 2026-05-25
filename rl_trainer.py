"""
MECOS Phase 6 - Reinforcement Learning Engine
Q-learning implementation, state representation, domain-specific reward functions,
policy optimization, experience replay buffer, and exploration/exploitation balance.
"""

import asyncio
import json
import random
import math
from collections import deque
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from loguru import logger

from memory_system import MemorySystem
from config import settings


class QTable:
    """
    Tabular Q-learning implementation.
    Suitable for discrete state/action spaces.
    """

    def __init__(self, learning_rate: float = 0.1, discount: float = 0.95):
        self.lr = learning_rate
        self.gamma = discount
        self.q_table: Dict[str, Dict[str, float]] = {}

    def get_q(self, state: str, action: str) -> float:
        return self.q_table.get(state, {}).get(action, 0.0)

    def update(self, state: str, action: str, reward: float, next_state: str, actions: List[str]):
        """Q-learning update: Q(s,a) ← Q(s,a) + α[r + γ·max Q(s',a') - Q(s,a)]"""
        current_q = self.get_q(state, action)
        max_next_q = max(self.get_q(next_state, a) for a in actions) if actions else 0.0
        new_q = current_q + self.lr * (reward + self.gamma * max_next_q - current_q)

        if state not in self.q_table:
            self.q_table[state] = {}
        self.q_table[state][action] = new_q

    def load(self, path: Path):
        """Load Q-table from a file."""
        if path.exists():
            with path.open('r') as f:
                self.q_table = json.load(f)
                logger.info(f"QTable loaded from {path}")
        else:
            logger.warning(f"QTable file not found: {path}")


class ReplayBuffer:
    """
    Experience replay buffer for RL training.
    Stores (state, action, reward, next_state, done) tuples.
    """

    def __init__(self, capacity: int = 10000):
        self.buffer: deque = deque(maxlen=capacity)
        self.capacity = capacity

    def push(self, state: str, action: str, reward: float, next_state: str, done: bool):
        self.buffer.append({
            "state": state,
            "action": action,
            "reward": reward,
            "next_state": next_state,
            "done": done,
            "timestamp": datetime.now().isoformat(),
        })

    def sample(self, batch_size: int) -> List[Dict]:
        return random.sample(self.buffer, min(batch_size, len(self.buffer)))

    def __len__(self) -> int:
        return len(self.buffer)

    def save(self, path: Path):
        path.write_text(json.dumps(list(self.buffer), default=str))

    def load(self, path: Path):
        if path.exists():
            data = json.loads(path.read_text())
            self.buffer = deque(data, maxlen=self.capacity)
            logger.info(f"Replay buffer loaded: {len(self.buffer)} experiences")


class RLTrainer:
    """
    RL agent for tabular Q-learning with experience replay.
    """

    def __init__(self, memory: MemorySystem, domain: str = "general"):
        self.memory = memory
        self.domain = domain
        self.q_table = QTable()
        self.replay = ReplayBuffer(capacity=20000)
        self.epsilon = 0.5  # More aggressive exploration
        self.epsilon_min = 0.05
        self.epsilon_decay = 0.995
        self.stats = {
            "episodes": 0,
            "total_reward": 0.0,
            "buffer_size": 0,
            "epsilon": self.epsilon,
        }
        logger.info(f"RLTrainer initialized for domain: {domain} (ε={self.epsilon:.3f})")
        if state not in self.q_table:
            self.q_table[state] = {}
        self.q_table[state][action] = new_q

    def get_action(self, state: str, actions: List[str]) -> str:
        """Return the action with highest Q-value for the given state."""
        if not actions:
            return ""
        return max(actions, key=lambda a: self.get_q(state, a))

    def save(self, path: Path):
        path.write_text(json.dumps(self.q_table))

    def load(self, path: Path):
        if path.exists():
            self.q_table = json.loads(path.read_text())
            logger.info(f"Q-table loaded: {len(self.q_table)} states")


class RewardFunction:
    """Domain-specific reward functions."""

    @staticmethod
    def trading(outcome: Dict[str, Any]) -> float:
        """Reward based on trade profit/loss."""
        pnl = outcome.get("pnl", 0.0)
        if pnl > 0:
            return min(pnl / 100.0, 1.0)  # Normalize
        return max(pnl / 100.0, -1.0)

    @staticmethod
    def coding(outcome: Dict[str, Any]) -> float:
        """Reward based on test pass rate."""
        passed = outcome.get("tests_passed", 0)
        total = outcome.get("tests_total", 1)
        return passed / max(total, 1)

    @staticmethod
    def planning(outcome: Dict[str, Any]) -> float:
        """Reward based on goal completion."""
        steps_completed = outcome.get("steps_completed", 0)
        total_steps = outcome.get("total_steps", 1)
        return steps_completed / max(total_steps, 1)

    @staticmethod
    def general(outcome: Dict[str, Any]) -> float:
        """General reward: success=1, failure=-0.5, partial=0.0-0.5."""
        if outcome.get("success"):
            return 1.0
        if outcome.get("partial"):
            return 0.3
        return -0.5


class RLTrainer:
    """
    Reinforcement Learning trainer for MECOS.
    Manages Q-learning, experience replay, policy optimization,
    and exploration/exploitation balance.
    """

    def __init__(self, memory: MemorySystem, domain: str = "general"):
        self.memory = memory
        self.domain = domain
        self.q_table = QTable()
        self.replay_buffer = ReplayBuffer(capacity=10000)
        self.reward_fn = getattr(RewardFunction, domain, RewardFunction.general)

        # Exploration parameters
        self.epsilon = 1.0          # Start with full exploration
        self.epsilon_min = 0.05
        self.epsilon_decay = 0.995
        self.episode = 0
        self.total_reward = 0.0

        # Persistence
        self.save_dir = settings.MEMORY_DIR / "rl" / domain
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self._load()

        logger.info(f"RLTrainer initialized for domain: {domain} (ε={self.epsilon:.3f})")

    def _load(self):
        self.q_table.load(self.save_dir / "q_table.json")
        self.replay_buffer.load(self.save_dir / "replay_buffer.json")

    def _save(self):
        self.q_table.save(self.save_dir / "q_table.json")
        self.replay_buffer.save(self.save_dir / "replay_buffer.json")

    def choose_action(self, state: str, available_actions: List[str]) -> str:
        """Epsilon-greedy action selection."""
        if not available_actions:
            return ""
        if random.random() < self.epsilon:
            return random.choice(available_actions)  # Explore
        return self.q_table.predict(state, available_actions)  # Exploit

    def record_experience(
        self,
        state: str,
        action: str,
        outcome: Dict[str, Any],
        next_state: str,
        done: bool = False,
    ):
        """Record an experience and update the Q-table."""
        reward = self.reward_fn(outcome)
        self.replay_buffer.push(state, action, reward, next_state, done)
        self.total_reward += reward

        # Immediate Q-update
        available_actions = list(self.q_table.q_table.get(next_state, {}).keys()) or [action]
        self.q_table.update(state, action, reward, next_state, available_actions)

        # Decay exploration
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

        logger.debug(f"RL [{self.domain}]: action={action}, reward={reward:.3f}, ε={self.epsilon:.3f}")

    async def train_from_replay(self, batch_size: int = 32):
        """Sample from replay buffer and perform batch Q-updates."""
        if len(self.replay_buffer) < batch_size:
            return

        batch = self.replay_buffer.sample(batch_size)
        for exp in batch:
            state = exp["state"]
            action = exp["action"]
            reward = exp["reward"]
            next_state = exp["next_state"]
            available_actions = list(self.q_table.q_table.get(next_state, {}).keys()) or [action]
            self.q_table.update(state, action, reward, next_state, available_actions)

        self.episode += 1
        self._save()

        await self.memory.add_experience(
            f"RL TRAINING [{self.domain}]: Episode {self.episode}, "
            f"Buffer={len(self.replay_buffer)}, ε={self.epsilon:.3f}, "
            f"Total Reward={self.total_reward:.2f}",
            source="rl_trainer",
        )
        logger.info(f"RL training episode {self.episode} complete [{self.domain}]")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "episode": self.episode,
            "epsilon": round(self.epsilon, 4),
            "total_reward": round(self.total_reward, 2),
            "buffer_size": len(self.replay_buffer),
            "q_states": len(self.q_table.q_table),
        }
