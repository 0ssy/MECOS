"""
MECOS Phase 6 - Self-Supervised Learning Engine
Next-token prediction, sequence completion, masked language modeling,
action-outcome prediction, and contrastive learning from raw data.
"""

import asyncio
import json
import random
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from loguru import logger

from memory_system import MemorySystem
from config import settings
from openai import OpenAI


class SelfSupervisedTrainer:
    """
    Self-supervised learning engine for MECOS.
    Learns from raw unlabeled data through prediction tasks.
    Generates synthetic training examples and evaluates prediction accuracy.
    """

    def __init__(self, memory: MemorySystem):
        self.memory = memory
        self.client = OpenAI(base_url=settings.LOCAL_LLM_URL, api_key="local-no-key")
        self.training_log: List[Dict] = []
        self.accuracy_history: List[float] = []
        self.save_dir = settings.MEMORY_DIR / "ssl"
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self._load_log()
        logger.info("SelfSupervisedTrainer initialized.")

    def _load_log(self):
        log_path = self.save_dir / "training_log.json"
        if log_path.exists():
            self.training_log = json.loads(log_path.read_text())
            logger.info(f"SSL training log loaded: {len(self.training_log)} entries")

    def _save_log(self):
        log_path = self.save_dir / "training_log.json"
        log_path.write_text(json.dumps(self.training_log[-1000:], default=str))

    def _mask_text(self, text: str, mask_ratio: float = 0.15) -> Tuple[str, List[Tuple[int, str]]]:
        """Mask random words in text for masked language modeling."""
        words = text.split()
        masked = []
        targets = []
        for i, word in enumerate(words):
            if random.random() < mask_ratio and len(word) > 3:
                targets.append((i, word))
                masked.append("[MASK]")
            else:
                masked.append(word)
        return " ".join(masked), targets

    def _create_next_token_task(self, text: str, context_ratio: float = 0.7) -> Tuple[str, str]:
        """Create a next-token prediction task from text."""
        words = text.split()
        if len(words) < 5:
            return text, ""
        split = max(3, int(len(words) * context_ratio))
        context = " ".join(words[:split])
        target = " ".join(words[split:split + 5])  # Predict next 5 words
        return context, target

    def _create_sequence_task(self, steps: List[str]) -> Tuple[str, str]:
        """Create a sequence prediction task from a list of steps."""
        if len(steps) < 2:
            return "", ""
        split = len(steps) // 2
        context = " → ".join(steps[:split])
        target = " → ".join(steps[split:])
        return context, target

    async def train_on_text(self, text: str, task_type: str = "next_token") -> Dict[str, Any]:
        """
        Run a self-supervised training iteration on a piece of text.
        Generates a prediction task, evaluates the model, and logs accuracy.
        """
        if task_type == "next_token":
            context, target = self._create_next_token_task(text)
        elif task_type == "masked":
            masked, targets = self._mask_text(text)
            context = masked
            target = " ".join(w for _, w in targets)
        else:
            context, target = self._create_next_token_task(text)

        if not context or not target:
            return {"task_type": task_type, "accuracy": 0.0, "skipped": True}

        # Ask the model to predict
        prompt = f"""Complete the following text naturally:

{context}

Continue with the next few words (be concise):"""

        try:
            response = self.client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            prediction = response.choices[0].message.content.strip()

            # Evaluate accuracy (word overlap)
            target_words = set(target.lower().split())
            pred_words = set(prediction.lower().split())
            overlap = len(target_words & pred_words)
            accuracy = overlap / max(len(target_words), 1)

            record = {
                "task_type": task_type,
                "context_length": len(context),
                "target": target[:100],
                "prediction": prediction[:100],
                "accuracy": round(accuracy, 3),
                "timestamp": datetime.now().isoformat(),
            }
            self.training_log.append(record)
            self.accuracy_history.append(accuracy)
            self._save_log()

            await self.memory.add_experience(
                f"SSL TRAINING [{task_type}]: accuracy={accuracy:.3f}",
                source="ssl_trainer",
            )
            logger.debug(f"SSL [{task_type}]: accuracy={accuracy:.3f}")
            return record

        except Exception as e:
            logger.error(f"SSL training failed: {e}")
            return {"task_type": task_type, "accuracy": 0.0, "error": str(e)}

    async def train_from_memory(self, n_samples: int = 10) -> Dict[str, Any]:
        """
        Pull recent experiences from memory and train on them.
        """
        context_results = await self.memory.retrieve_context("learning experience", n_results=n_samples)
        docs = context_results.get("documents", [[]])[0] if context_results else []

        if not docs:
            return {"trained": 0, "avg_accuracy": 0.0}

        accuracies = []
        for doc in docs[:n_samples]:
            if len(doc.split()) > 10:
                result = await self.train_on_text(doc)
                if not result.get("skipped"):
                    accuracies.append(result.get("accuracy", 0.0))

        avg_accuracy = sum(accuracies) / max(len(accuracies), 1)
        logger.info(f"SSL training from memory: {len(accuracies)} samples, avg accuracy={avg_accuracy:.3f}")

        await self.memory.add_experience(
            f"SSL BATCH TRAINING: {len(accuracies)} samples, avg_accuracy={avg_accuracy:.3f}",
            source="ssl_trainer",
        )
        return {"trained": len(accuracies), "avg_accuracy": round(avg_accuracy, 3)}

    async def predict_action_outcome(self, action: str, context: str) -> str:
        """Predict the likely outcome of an action given context."""
        prompt = f"""Given this context and action, predict the most likely outcome.

Context: {context[:500]}
Action: {action}

Predicted outcome (1-2 sentences):"""
        try:
            response = self.client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            prediction = response.choices[0].message.content.strip()
            await self.memory.add_experience(
                f"ACTION PREDICTION: {action[:80]} → {prediction[:150]}",
                source="ssl_trainer",
            )
            return prediction
        except Exception as e:
            return f"Prediction failed: {e}"

    def get_stats(self) -> Dict[str, Any]:
        recent = self.accuracy_history[-100:]
        return {
            "total_training_runs": len(self.training_log),
            "recent_avg_accuracy": round(sum(recent) / max(len(recent), 1), 3),
            "best_accuracy": round(max(self.accuracy_history, default=0.0), 3),
        }
