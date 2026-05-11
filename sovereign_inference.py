"""
MECOS Sovereign Inference Engine
Directly loads and runs model weights using llama-cpp-python.
This allows MECOS to stop depending on Ollama once it is ready.
"""

import os
from loguru import logger
from config import settings

try:
    from llama_cpp import Llama
except ImportError:
    logger.warning("llama-cpp-python not installed. Run 'pip install llama-cpp-python' for Sovereign Inference.")

class SovereignInference:
    def __init__(self, model_path: str = None):
        self.model_path = model_path or str(settings.BASE_DIR / "models" / "mecos_core.gguf")
        self.llm = None
        
        if os.path.exists(self.model_path):
            logger.info(f"Loading Sovereign Model from {self.model_path}...")
            self.llm = Llama(
                model_path=self.model_path,
                n_ctx=4096,
                n_threads=os.cpu_count(),
                n_gpu_layers=-1 if settings.USE_GPU else 0
            )
        else:
            logger.warning(f"Sovereign model not found at {self.model_path}. Still dependent on external engine.")

    def generate(self, prompt: str, max_tokens: int = 512):
        if not self.llm:
            raise RuntimeError("Sovereign Inference Engine not initialized. Model weights missing.")
        
        output = self.llm(
            f"Q: {prompt} A: ",
            max_tokens=max_tokens,
            stop=["Q:", "\n"],
            echo=False
        )
        return output["choices"][0]["text"]

    def is_ready(self):
        return self.llm is not None
