"""
MECOS Reinforcement Learning Engine
Tabular Q-learning with replay, persistence, and bounded exploration.
"""

import json
import random
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from loguru import logger

from config import settings
from memory_system import MemorySystem


class QTable:
    def __init__(self, learning_rate: float = 0.08, discount: float = 0.95):
        self.lr = float(learning_rate)
        self.gamma = float(discount)
        self.q_table: Dict[str, Dict[str, float]] = {}

    def get_q(self, state: str, action: str) -> float:
        return float(self.q_table.get(state, {}).get(action, 0.0))

    def predict(self, state: str, actions: List[str]) -> str:
        if not actions:
            return ""
        return max(actions, key=lambda action: self.get_q(state, action))

    def action_values(self, state: str, actions: List[str]) -> Dict[str, float]:
        return {action: self.get_q(state, action) for action in actions}

    def update(self, state: str, action: str, reward: float, next_state: str, actions: List[str]):
        current_q = self.get_q(state, action)
        max_next_q = max((self.get_q(next_state, a) for a in actions), default=0.0)
        new_q = current_q + self.lr * (reward + self.gamma * max_next_q - current_q)
        state_bucket = self.q_table.setdefault(state, {})
        state_bucket[action] = float(new_q)

    def save(self, path: Path):
        path.write_text(json.dumps(self.q_table))

    def load(self, path: Path):
        if path.exists():
            self.q_table = json.loads(path.read_text())
            logger.info(f"QTable loaded from {path}")
        else:
            logger.warning(f"QTable file not found: {path}")


class ReplayBuffer:
    def __init__(self, capacity: int = 10000):
        self.buffer: deque = deque(maxlen=capacity)
        self.capacity = int(capacity)

    def push(self, state: str, action: str, reward: float, next_state: str, done: bool):
        self.buffer.append(
            {
                "state": state,
                "action": action,
                "reward": float(reward),
                "next_state": next_state,
                "done": bool(done),
                "timestamp": datetime.now().isoformat(),
            }
        )

    def sample(self, batch_size: int) -> List[Dict[str, Any]]:
        return random.sample(self.buffer, min(int(batch_size), len(self.buffer)))

    def __len__(self) -> int:
        return len(self.buffer)

    def save(self, path: Path):
        path.write_text(json.dumps(list(self.buffer), default=str))

    def load(self, path: Path):
        if path.exists():
            data = json.loads(path.read_text())
            self.buffer = deque(data, maxlen=self.capacity)
            logger.info(f"Replay buffer loaded: {len(self.buffer)} experiences")


class RewardFunction:
    @staticmethod
    def trading(outcome: Dict[str, Any]) -> float:
        pnl = float(outcome.get("pnl", 0.0) or 0.0)
        reward = pnl / 100.0
        causal_penalty = float(outcome.get("causal_penalty", 0.0) or 0.0)
        if pnl < 0.0 and causal_penalty > 0.0:
            reward -= min(causal_penalty, 0.5)
        return float(max(min(reward, 1.0), -1.0))

    @staticmethod
    def coding(outcome: Dict[str, Any]) -> float:
        passed = float(outcome.get("tests_passed", 0) or 0)
        total = float(outcome.get("tests_total", 1) or 1)
        return float(max(min(passed / max(total, 1.0), 1.0), 0.0))

    @staticmethod
    def planning(outcome: Dict[str, Any]) -> float:
        done = float(outcome.get("steps_completed", 0) or 0)
        total = float(outcome.get("total_steps", 1) or 1)
        return float(max(min(done / max(total, 1.0), 1.0), 0.0))

    @staticmethod
    def general(outcome: Dict[str, Any]) -> float:
        if outcome.get("success"):
            return 1.0
        if outcome.get("partial"):
            return 0.3
        return -0.5


class RLTrainer:
    def __init__(self, memory: MemorySystem, domain: str = "general"):
        self.memory = memory
        self.domain = domain
        self.q_table = QTable()
        self.replay_buffer = ReplayBuffer(capacity=10000)
        self.reward_fn = getattr(RewardFunction, domain, RewardFunction.general)

        # Stabilized exploration schedule.
        if domain == "trading":
            self.epsilon = 0.12
            self.epsilon_min = 0.02
            self.epsilon_decay = 0.999
            self.min_buffer_for_explore = 128
        else:
            self.epsilon = 0.25
            self.epsilon_min = 0.05
            self.epsilon_decay = 0.995
            self.min_buffer_for_explore = 32

        self.episode = 0
        self.total_reward = 0.0

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

    def choose_action(self, state: str, available_actions: List[str], allow_exploration: bool = True) -> str:
        if not available_actions:
            return ""

        can_explore = allow_exploration and len(self.replay_buffer) >= self.min_buffer_for_explore
        if can_explore and random.random() < self.epsilon:
            return random.choice(available_actions)
        return self.q_table.predict(state, available_actions)

    def q_values(self, state: str, actions: List[str]) -> Dict[str, float]:
        return self.q_table.action_values(state, actions)

    def record_experience(
        self,
        state: str,
        action: str,
        outcome: Dict[str, Any],
        next_state: str,
        done: bool = False,
    ):
        reward = float(self.reward_fn(outcome))
        self.replay_buffer.push(state, action, reward, next_state, done)
        self.total_reward += reward

        available_actions = list(self.q_table.q_table.get(next_state, {}).keys()) or [action]
        self.q_table.update(state, action, reward, next_state, available_actions)

        if self.epsilon > self.epsilon_min:
            self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

    async def train_from_replay(self, batch_size: int = 32):
        if len(self.replay_buffer) < batch_size:
            return

        for exp in self.replay_buffer.sample(batch_size):
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

    def get_stats(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "episode": self.episode,
            "epsilon": round(self.epsilon, 4),
            "total_reward": round(self.total_reward, 2),
            "buffer_size": len(self.replay_buffer),
            "q_states": len(self.q_table.q_table),
            "min_buffer_for_explore": self.min_buffer_for_explore,
        }
