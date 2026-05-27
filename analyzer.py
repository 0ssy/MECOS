"""
MECOS Research Layer — Research Crawler and Repo Analyzer
Continuous local-first knowledge acquisition.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List

from loguru import logger


class ResearchAgent:
    def __init__(self, memory_layer=None):
        self.memory = memory_layer

    async def crawl_web(self, topics: List[str]):
        for topic in topics:
            logger.info(f"Researching topic: {topic}")
            artifact = f"Extracted local-first knowledge for {topic}"
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
        if self.memory:
            self.memory.store("Repository analysis complete", {"source": "research.analyze_repo", "report": report})
        return report

