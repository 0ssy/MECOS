import asyncio
import random
from loguru import logger
from exploration.config import config
from exploration.browser_explorer import BrowserExplorer
from exploration.system_explorer import SystemExplorer
from exploration.knowledge_base import KnowledgeBase
from exploration.vision_analyzer import VisionAnalyzer
from exploration.app_discovery_agent import AppDiscoveryAgent
from exploration.autonomous_browser_explorer import AutonomousBrowserExplorer

class ExplorationEngine:
    def __init__(self):
        self.kb = KnowledgeBase()
        self.vision = VisionAnalyzer()
        self.browser_base = BrowserExplorer(self.kb, self.vision)
        self.browser = AutonomousBrowserExplorer(self.browser_base, self.kb)
        self.system = SystemExplorer(self.kb, self.vision)
        self.app_discovery = AppDiscoveryAgent(None, self.kb) # Memory placeholder

    async def run(self):
        await self.browser_base.startup()
        logger.info("MECOS Exploration Engine Active. Smart mode enabled.")
        
        # Initial App Discovery
        await self.app_discovery.discover_apps()
        
        try:
            while True:
                # Alternate between Smart Web Exploration and System/App Discovery
                if random.random() < 0.7:
                    # Smart Browser Exploration
                    await self.browser.explore(
                        current_goals=["coding", "automation"], 
                        curiosity_topics=["machine learning", "trading"]
                    )
                else:
                    # System & App Discovery
                    await self.system.explore_system()
                    await self.app_discovery.discover_apps()
                
                logger.info(f"Cycle complete. Resting for {config.EXPLORATION_INTERVAL}s...")
                await asyncio.sleep(config.EXPLORATION_INTERVAL)
        except Exception as e:
            logger.error(f"Exploration Engine Error: {e}")
        finally:
            await self.browser_base.shutdown()
