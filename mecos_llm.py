"""
MECOS LLM Inference Engine
Handles the 'Internal Monologue' and 'Final Response' cognitive cycle.

FIX: think_and_act was declared async but made synchronous blocking OpenAI
calls directly, which freezes the event loop under any concurrency.
All blocking calls are now wrapped in asyncio.to_thread().
"""

import asyncio
import json
import time
from loguru import logger
from openai import OpenAI
from config import settings


class MECOSLLM:
    def __init__(self):
        self.client = OpenAI(base_url=settings.LOCAL_LLM_URL, api_key="local-no-key")
        self.model = settings.DEFAULT_MODEL
        logger.info(f"MECOS LLM connected to {settings.LOCAL_LLM_URL} (model={self.model})")

    # ── Internal sync helpers (run in thread pool) ────────────────────────

    def _chat(self, messages: list) -> str:
        """Blocking OpenAI call — always run via asyncio.to_thread."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return response.choices[0].message.content

    def _save_experience_sync(self, prompt: str, monologue: str, response: str):
        """Blocking file write — always run via asyncio.to_thread."""
        log_file = settings.DATA_DIR / "llm_experiences.jsonl"
        experience = {
            "timestamp": time.time(),
            "prompt": prompt,
            "monologue": monologue,
            "response": response,
        }
        with open(log_file, "a") as f:
            f.write(json.dumps(experience) + "\n")

    # ── Public async API ──────────────────────────────────────────────────

    async def think_and_act(
        self,
        prompt: str,
        system_prompt: str = "You are the MECOS AI.",
    ) -> dict:
        """
        Two-stage cognitive cycle:
          1. Internal monologue  (think step-by-step)
          2. Final response      (act on the thinking)

        Both OpenAI calls are non-blocking — event loop stays free.
        """
        start = time.time()

        # Stage 1: internal monologue
        thinking_messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"{prompt}\n\n[INTERNAL MONOLOGUE]: Think step-by-step.",
            },
        ]
        logger.debug("MECOS LLM: generating monologue...")
        try:
            monologue = await asyncio.to_thread(self._chat, thinking_messages)
        except Exception as e:
            logger.error(f"Monologue generation failed: {e}")
            monologue = f"Error: {e}"

        # Stage 2: final response
        final_messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"{prompt}\n\n[MY THOUGHTS]: {monologue}\n\n[FINAL RESPONSE]:",
            },
        ]
        logger.debug("MECOS LLM: generating final response...")
        try:
            response = await asyncio.to_thread(self._chat, final_messages)
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            response = f"Error: {e}"

        # Persist experience (non-blocking)
        await asyncio.to_thread(self._save_experience_sync, prompt, monologue, response)

        duration = time.time() - start
        logger.info(f"MECOS LLM cycle complete in {duration:.2f}s")

        return {
            "monologue": monologue,
            "response": response,
            "stats": {"duration": duration, "model": self.model},
        }

    async def save_experience(self, prompt: str, monologue: str, response: str):
        """Async wrapper for experience saving (keeps old call sites working)."""
        await asyncio.to_thread(self._save_experience_sync, prompt, monologue, response)


# ── Singleton ─────────────────────────────────────────────────────────────────

_mecos_llm: "MECOSLLM | None" = None


def get_mecos_llm() -> MECOSLLM:
    global _mecos_llm
    if _mecos_llm is None:
        _mecos_llm = MECOSLLM()
    return _mecos_llm

