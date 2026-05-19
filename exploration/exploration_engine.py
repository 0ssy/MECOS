import asyncio
import random
from loguru import logger
from exploration.config import config
from exploration.browser_explorer import BrowserExplorer
from exploration.system_explorer import SystemExplorer
from exploration.knowledge_base import KnowledgeBase
from exploration.vision_analyzer import VisionAnalyzer

class ExplorationEngine:
    def __init__(self):
        self.kb = KnowledgeBase()
        self.vision = VisionAnalyzer()
        self.browser = BrowserExplorer(self.kb, self.vision)
        self.system = SystemExplorer(self.kb, self.vision)

    async def run(self):
        await self.browser.startup()
        try:
            while True:
                if random.random() < 0.7:
                    await self.browser.explore("https://github.com", "github" )
                else:
                    await self.system.explore_system()
                await asyncio.sleep(config.EXPLORATION_INTERVAL)
        finally:
            await self.browser.shutdown()
