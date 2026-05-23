import numpy as np
from typing import Dict, Any, List
from loguru import logger


class TradingEnv:
    def __init__(self, market_data: List[Dict[str, Any]]):
        self.market_data = market_data
        self.current_step = 0
        self.max_steps = len(market_data) - 1

    def reset(self) -> Dict[str, Any]:
        self.current_step = 0
        return self.market_data[self.current_step]

    def step(self, action: str):
        self.current_step += 1
        if self.current_step > self.max_steps:
            return None, 0.0, True, {}

        reward = 0.0
        done = False
        previous_close = self.market_data[self.current_step - 1]["close"]
        current_close = self.market_data[self.current_step]["close"]

        if action == "BUY":
            reward = current_close - previous_close
        elif action == "SELL":
            reward = previous_close - current_close

        done = self.current_step == self.max_steps
        next_state = self.market_data[self.current_step] if not done else None
        return next_state, float(reward), done, {}


class SimpleRLAgent:
    def __init__(self, action_space: List[str] = None):
        self.action_space = action_space or ["HOLD", "BUY", "SELL"]
        self.q_table: Dict[str, np.ndarray] = {}
        self.epsilon = 0.9
        self.alpha = 0.1
        self.gamma = 0.99

    def get_action(self, state_key: str) -> str:
        if np.random.rand() < self.epsilon or state_key not in self.q_table:
            return str(np.random.choice(self.action_space))
        return self.action_space[int(np.argmax(self.q_table[state_key]))]

    def update_q_table(self, state_key: str, action: str, reward: float, next_state_key: str):
        if state_key not in self.q_table:
            self.q_table[state_key] = np.zeros(len(self.action_space), dtype=float)
        if next_state_key not in self.q_table:
            self.q_table[next_state_key] = np.zeros(len(self.action_space), dtype=float)

        action_idx = self.action_space.index(action)
        old_value = self.q_table[state_key][action_idx]
        next_max = float(np.max(self.q_table[next_state_key]))

        new_value = old_value + self.alpha * (reward + self.gamma * next_max - old_value)
        self.q_table[state_key][action_idx] = new_value


class ReinforcementLearningAgent:
    def __init__(self, memory_system):
        self.memory = memory_system
        self.rl_agent = SimpleRLAgent()
        logger.info("ReinforcementLearningAgent initialized.")

    async def optimize(self, market_data: List[Dict], params: Dict = None) -> Dict[str, Any]:
        """Optimizes trading strategy using a simple RL approach."""
        params = params or {}
        if not market_data:
            return {"signal": "HOLD", "confidence": 0, "reason": "No market data for RL"}
        if len(market_data) < 2:
            return {"signal": "HOLD", "confidence": 0, "reason": "Insufficient market data for RL"}
        if any("close" not in row for row in market_data):
            return {"signal": "HOLD", "confidence": 0, "reason": "Invalid market data: missing close"}

        env = TradingEnv(market_data)
        state = env.reset()
        done = False
        total_reward = 0.0
        z_threshold = float(params.get("confidence_threshold", 0.7))

        def get_state_key(s):
            if s is None:
                return "terminal"
            close = float(s["close"])
            ma = float(np.mean([d["close"] for d in market_data[: env.current_step + 1]])) if env.current_step > 0 else close
            return f"close_{int(close)}_ma_{int(ma)}"

        while not done:
            state_key = get_state_key(state)
            action = self.rl_agent.get_action(state_key)
            next_state, reward, done, _ = env.step(action)
            next_state_key = get_state_key(next_state)
            self.rl_agent.update_q_table(state_key, action, reward, next_state_key)
            state = next_state
            total_reward += reward

        final_state_key = get_state_key(market_data[-1])
        final_action = self.rl_agent.get_action(final_state_key)

        logger.info(
            f"RL Optimization complete. Total Reward: {total_reward:.2f}, Final Action: {final_action}"
        )

        return {
            "signal": final_action,
            "confidence": z_threshold,
            "total_reward": float(total_reward),
        }
