"""
MECOS Phase 7 - World Model
Internal model of the environment: predicts action outcomes,
models state transitions, simulates future scenarios,
and supports planning through mental simulation.
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from loguru import logger

from memory_system import MemorySystem
from config import settings
from openai import OpenAI


class StateTransition:
    """Records a (state, action, outcome, next_state) tuple."""

    def __init__(self, state: str, action: str, outcome: str, next_state: str, reward: float = 0.0):
        self.state = state
        self.action = action
        self.outcome = outcome
        self.next_state = next_state
        self.reward = reward
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "action": self.action,
            "outcome": self.outcome,
            "next_state": self.next_state,
            "reward": self.reward,
            "timestamp": self.timestamp,
        }


class WorldModel:
    """
    Internal world model for MECOS.
    Learns state transition dynamics from experience,
    predicts outcomes of actions, and enables mental simulation
    for planning without executing real actions.
    """

    def __init__(self, memory: MemorySystem):
        self.memory = memory
        self.client = OpenAI(base_url=settings.LOCAL_LLM_URL, api_key="local-no-key")
        self.transitions: List[StateTransition] = []
        self.state_action_outcomes: Dict[str, Dict[str, List[str]]] = {}
        self.save_dir = settings.MEMORY_DIR / "world_model"
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self._load()
        logger.info("WorldModel initialized.")

    def _load(self):
        path = self.save_dir / "transitions.json"
        if path.exists():
            data = json.loads(path.read_text())
            self.transitions = [
                StateTransition(
                    d["state"], d["action"], d["outcome"], d["next_state"], d.get("reward", 0.0)
                )
                for d in data
            ]
            # Rebuild state-action-outcome index
            for t in self.transitions:
                self._index_transition(t)
            logger.info(f"World model loaded: {len(self.transitions)} transitions")

    def _save(self):
        path = self.save_dir / "transitions.json"
        data = [t.to_dict() for t in self.transitions[-2000:]]
        path.write_text(json.dumps(data, default=str))

    def _index_transition(self, t: StateTransition):
        """Index a transition for fast lookup."""
        state_key = t.state[:100]  # Truncate for key
        if state_key not in self.state_action_outcomes:
            self.state_action_outcomes[state_key] = {}
        if t.action not in self.state_action_outcomes[state_key]:
            self.state_action_outcomes[state_key][t.action] = []
        self.state_action_outcomes[state_key][t.action].append(t.outcome)

    def record_transition(self, state: str, action: str, outcome: str, next_state: str, reward: float = 0.0):
        """Record a new state transition into the world model."""
        t = StateTransition(state, action, outcome, next_state, reward)
        self.transitions.append(t)
        self._index_transition(t)
        if len(self.transitions) % 50 == 0:
            self._save()
        logger.debug(f"World model: recorded transition ({action[:40]})")

    def lookup_outcomes(self, state: str, action: str) -> List[str]:
        """Look up historical outcomes for a (state, action) pair."""
        state_key = state[:100]
        return self.state_action_outcomes.get(state_key, {}).get(action, [])

    async def predict_outcome(self, state: str, action: str, context: str = "") -> str:
        """
        Predict the likely outcome of taking an action in a given state.
        Uses historical data if available, otherwise uses LLM.
        """
        # Check historical data first
        historical = self.lookup_outcomes(state, action)
        if historical:
            # Return the most common historical outcome
            from collections import Counter
            most_common = Counter(historical).most_common(1)[0][0]
            logger.debug(f"World model prediction (historical): {most_common[:80]}")
            return most_common

        # Fall back to LLM prediction
        prompt = f"""Predict the most likely outcome of this action.

Current state: {state[:300]}
Action to take: {action}
Additional context: {context[:200]}

Predict the outcome in 1-2 sentences. Be specific and realistic."""

        try:
            response = self.client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            prediction = response.choices[0].message.content.strip()
            logger.debug(f"World model prediction (LLM): {prediction[:80]}")
            return prediction
        except Exception as e:
            return f"Prediction unavailable: {e}"

    async def simulate_plan(self, initial_state: str, plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Mentally simulate executing a plan and predict outcomes for each step.
        Returns a list of predicted step results.
        """
        logger.info(f"Simulating plan: {len(plan)} steps")
        current_state = initial_state
        simulation_results = []

        for i, step in enumerate(plan, start=1):
            tool = step.get("tool", "unknown")
            args = step.get("args", {})
            action_desc = f"{tool}({', '.join(f'{k}={v}' for k, v in args.items())})"

            predicted_outcome = await self.predict_outcome(current_state, action_desc)
            predicted_success = not any(
                kw in predicted_outcome.lower()
                for kw in ["fail", "error", "unable", "cannot", "impossible"]
            )

            result = {
                "step": i,
                "action": action_desc,
                "predicted_outcome": predicted_outcome,
                "predicted_success": predicted_success,
            }
            simulation_results.append(result)

            # Update simulated state
            current_state = f"{current_state} | After step {i}: {predicted_outcome[:100]}"

        await self.memory.add_experience(
            f"PLAN SIMULATION: {len(plan)} steps, "
            f"predicted_success={sum(1 for r in simulation_results if r['predicted_success'])}/{len(plan)}",
            source="world_model",
        )
        return simulation_results

    async def evaluate_plan_risk(self, plan: List[Dict[str, Any]], state: str) -> Dict[str, Any]:
        """Evaluate the risk level of a plan before execution."""
        simulation = await self.simulate_plan(state, plan)
        failure_count = sum(1 for r in simulation if not r["predicted_success"])
        risk_score = failure_count / max(len(simulation), 1)

        risk_level = "LOW" if risk_score < 0.2 else "MEDIUM" if risk_score < 0.5 else "HIGH"

        return {
            "risk_level": risk_level,
            "risk_score": round(risk_score, 2),
            "predicted_failures": failure_count,
            "total_steps": len(plan),
            "simulation": simulation,
        }

    def get_model_stats(self) -> Dict[str, Any]:
        return {
            "total_transitions": len(self.transitions),
            "unique_states": len(self.state_action_outcomes),
            "total_actions": sum(len(actions) for actions in self.state_action_outcomes.values()),
        }
