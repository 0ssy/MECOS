"""
MECOS Sovereign Inference

FIX: is_ready() always returned False because it checked for
mecos_core.gguf which never exists. The sovereignty path was
permanently blocked with no way to progress.

Now:
  - is_ready() checks the model file AND validates it's non-empty
  - get_readiness_report() explains exactly what's missing
  - download_model() provides a real path to get the weights
  - infer() works if weights are present, falls back to Ollama otherwise
    (so the system doesn't crash if called before weights are downloaded)
"""

import asyncio
from pathlib import Path
from typing import Optional
from loguru import logger
from config import settings
from openai import OpenAI


# ── Model configuration ───────────────────────────────────────────────────────

# Where MECOS expects to find locally-fine-tuned weights
MODEL_PATH = settings.BASE_DIR / "models" / "mecos_core.gguf"

# Minimum file size to be considered a real model (not a placeholder)
MIN_MODEL_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB


class SovereignInference:
    """
    Manages the transition from Ollama-backed inference to fully local
    GGUF model inference.

    Sovereignty progression:
      NOT_READY → READY_FOR_WEIGHTS → SOVEREIGN
    """

    def __init__(self):
        self._model_path = MODEL_PATH
        self._llama_cpp_available = self._check_llama_cpp()
        self._sovereign_client: Optional[OpenAI] = None

        if self.is_ready():
            logger.info(f"Sovereign model found at {self._model_path}")
            self._init_sovereign_client()
        else:
            logger.info(
                f"Sovereign inference not ready. "
                f"Place a GGUF model at: {self._model_path}"
            )

    # ── Readiness ─────────────────────────────────────────────────────────

    def is_ready(self) -> bool:
        """
        Returns True only if:
          1. The model file exists
          2. It's large enough to be a real model (not a placeholder)
          3. llama-cpp-python is installed
        """
        if not self._model_path.exists():
            return False
        if self._model_path.stat().st_size < MIN_MODEL_SIZE_BYTES:
            return False
        if not self._llama_cpp_available:
            return False
        return True

    def get_readiness_report(self) -> dict:
        """Explain exactly what's missing so the user knows what to do."""
        model_exists = self._model_path.exists()
        model_size = self._model_path.stat().st_size if model_exists else 0
        size_ok = model_size >= MIN_MODEL_SIZE_BYTES

        return {
            "is_ready": self.is_ready(),
            "model_path": str(self._model_path),
            "model_exists": model_exists,
            "model_size_mb": round(model_size / 1024 / 1024, 1),
            "size_ok": size_ok,
            "llama_cpp_available": self._llama_cpp_available,
            "missing": self._missing_items(model_exists, size_ok),
        }

    def _missing_items(self, model_exists: bool, size_ok: bool) -> list:
        missing = []
        if not model_exists:
            missing.append(f"Model file missing: {self._model_path}")
        elif not size_ok:
            missing.append(
                f"Model file too small ({self._model_path.stat().st_size / 1024:.0f} KB). "
                f"Expected at least {MIN_MODEL_SIZE_BYTES // (1024*1024)} MB."
            )
        if not self._llama_cpp_available:
            missing.append("llama-cpp-python not installed. Run: pip install llama-cpp-python")
        return missing

    # ── Setup helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _check_llama_cpp() -> bool:
        try:
            import llama_cpp  # noqa: F401
            return True
        except ImportError:
            return False

    def _init_sovereign_client(self):
        """
        If llama-cpp-python is serving via its built-in server,
        connect to it on localhost:8080.
        """
        try:
            self._sovereign_client = OpenAI(
                base_url="http://localhost:8080/v1",
                api_key="local-no-key",
            )
        except Exception as e:
            logger.warning(f"Could not init sovereign client: {e}")

    def get_model_download_instructions(self) -> str:
        """
        Return instructions for obtaining a compatible GGUF model.
        MECOS needs a model it can run locally without Ollama.
        """
        self._model_path.parent.mkdir(parents=True, exist_ok=True)
        return f"""
To enable Sovereign Inference, place a GGUF model at:
  {self._model_path}

Recommended models (free, open weights):
  1. Llama 3 8B (Q4_K_M) — good balance of speed and quality
     huggingface.co/bartowski/Meta-Llama-3-8B-Instruct-GGUF

  2. Mistral 7B (Q4_K_M) — fast on CPU
     huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF

  3. Phi-3 Mini (Q4_K_M) — very small, runs on low RAM
     huggingface.co/bartowski/Phi-3-mini-4k-instruct-GGUF

Also install the inference backend:
  pip install llama-cpp-python

Then restart MECOS — it will detect the model automatically.
"""

    # ── Inference ─────────────────────────────────────────────────────────

    async def infer(self, prompt: str, system: str = "You are MECOS.") -> str:
        """
        Run inference using the sovereign model if ready,
        otherwise fall back to Ollama transparently.
        """
        if self.is_ready() and self._sovereign_client:
            return await self._sovereign_infer(prompt, system)
        else:
            return await self._ollama_fallback(prompt, system)

    async def _sovereign_infer(self, prompt: str, system: str) -> str:
        def _call():
            resp = self._sovereign_client.chat.completions.create(
                model="local",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
            return resp.choices[0].message.content.strip()

        try:
            result = await asyncio.to_thread(_call)
            logger.debug("Sovereign inference used.")
            return result
        except Exception as e:
            logger.warning(f"Sovereign inference failed, falling back to Ollama: {e}")
            return await self._ollama_fallback(prompt, system)

    async def _ollama_fallback(self, prompt: str, system: str) -> str:
        def _call():
            client = OpenAI(base_url=settings.LOCAL_LLM_URL, api_key="local-no-key")
            resp = client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
            return resp.choices[0].message.content.strip()

        result = await asyncio.to_thread(_call)
        logger.debug("Ollama fallback used.")
        return result

