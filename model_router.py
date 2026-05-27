"""
MECOS Evolution Layer — Local-first model router.
"""
from __future__ import annotations

from typing import Any, Dict

from loguru import logger


class ModelRouter:
    def __init__(self, main_brain_url: str = "http://192.168.1.88:11434"):
        self.main_brain_url = main_brain_url
        self.local_ollama_url = "http://localhost:11434"
        self.stats: Dict[str, Any] = {"main_brain": 0, "ollama": 0}

    async def route_request(self, prompt: str, task_type: str) -> str:
        if task_type in {"reasoning", "long_term_planning", "architecture"}:
            self.stats["main_brain"] += 1
            logger.info(f"Routing {task_type} to main brain ({self.main_brain_url})")
            return "main_brain_response"
        self.stats["ollama"] += 1
        logger.info(f"Routing {task_type} to local ollama ({self.local_ollama_url})")
        return "local_ollama_response"

    def get_routing_stats(self) -> Dict[str, Any]:
        return dict(self.stats)

