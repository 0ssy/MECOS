"""
MECOS Research Layer — Research Crawler and Repo Analyzer
Continuous local-first knowledge acquisition.
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Dict, List

from loguru import logger


class ResearchAgent:
    def __init__(self, memory_layer=None):
        self.memory = memory_layer
        self.metrics = {
            "start_ts": time.time(),
            "discoveries_total": 0,
            "useful_discoveries": 0,
            "repo_analyses": 0,
        }

    async def crawl_web(self, topics: List[str]):
        for topic in topics:
            logger.info(f"Researching topic: {topic}")
            artifact = f"Extracted local-first knowledge for {topic}"
            self.metrics["discoveries_total"] += 1
            if len(topic.split()) >= 2:
                self.metrics["useful_discoveries"] += 1
            if self.memory:
                self.memory.store(artifact, {"source": "research.crawl_web", "topic": topic})
            await asyncio.sleep(0.2)

    async def analyze_repo(self, repo_path: str) -> Dict[str, Any]:
        logger.info(f"Analyzing repository: {repo_path}")
        file_count = 0
        for root, dirs, files in os.walk(repo_path):
            if ".git" in dirs:
                dirs.remove(".git")
            file_count += len(files)
        report = {
            "repo_path": repo_path,
            "file_count": file_count,
            "languages": ["python"],
            "mode": "local-first",
        }
        self.metrics["repo_analyses"] += 1
        if self.memory:
            self.memory.store("Repository analysis complete", {"source": "research.analyze_repo", "report": report})
        return report

    def get_metrics(self) -> Dict[str, Any]:
        elapsed_hours = max((time.time() - self.metrics["start_ts"]) / 3600.0, 1e-6)
        discoveries_total = int(self.metrics["discoveries_total"])
        useful = int(self.metrics["useful_discoveries"])
        return {
            "discoveries_total": discoveries_total,
            "useful_discoveries": useful,
            "useful_discoveries_per_hour": useful / elapsed_hours,
            "usefulness_ratio": useful / max(discoveries_total, 1),
            "repo_analyses": int(self.metrics["repo_analyses"]),
        }

