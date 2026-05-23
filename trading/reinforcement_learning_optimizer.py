import numpy as np
from typing import Dict, Any
from loguru import logger

class ReinforcementLearningOptimizer:
    def __init__(self, memory):
        self.memory = memory

        self.q_table = {}

        self.alpha = 0.1
        self.gamma = 0.95
        self.epsilon = 0.1

        logger.info("RL Optimizer initialized")

    def _state_key(self, state: Dict) -> str:
        return str(sorted(state.items()))

    def choose_action(self, state: Dict):

        key = self._state_key(state)

        if np.random.rand() < self.epsilon:
            return np.random.choice(["BUY", "SELL", "HOLD"])

        values = self.q_table.get(
            key,
            {"BUY": 0, "SELL": 0, "HOLD": 0}
        )

        return max(values, key=values.get)

    def update(self,
               state: Dict,
               action: str,
               reward: float,
               next_state: Dict):

        state_key = self._state_key(state)
        next_key = self._state_key(next_state)

        if state_key not in self.q_table:
            self.q_table[state_key] = {
                "BUY": 0,
                "SELL": 0,
                "HOLD": 0
            }

        if next_key not in self.q_table:
            self.q_table[next_key] = {
                "BUY": 0,
                "SELL": 0,
                "HOLD": 0
            }

        current_q = self.q_table[state_key][action]

        next_max = max(self.q_table[next_key].values())

        updated_q = current_q + self.alpha * (
            reward + self.gamma * next_max - current_q
        )

        self.q_table[state_key][action] = updated_q
