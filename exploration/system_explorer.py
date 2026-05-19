from PIL import ImageGrab
from loguru import logger
from exploration.config import config

class SystemExplorer:
    def __init__(self, knowledge_base, vision_analyzer):
        self.kb = knowledge_base
        self.vision = vision_analyzer

    async def explore_system(self):
        logger.info("Exploring laptop environment...")
        screenshot = ImageGrab.grab()
        analysis = await self.vision.analyze_screenshot(screenshot, "Analyze this Windows desktop.")
        self.kb.add_log("laptop_desktop", {"analysis": analysis})
