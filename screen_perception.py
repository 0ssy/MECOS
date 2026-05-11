import mss
from PIL import Image
import pytesseract
from loguru import logger
from memory_system import MemorySystem
import time
from pathlib import Path

class ScreenPerception:
    def __init__(self, memory_system: MemorySystem):
        self.memory = memory_system
        self.output_dir = Path("/home/ubuntu/cognitive_os/data/screenshots")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def capture_and_ocr(self):
        """Capture screenshot and perform OCR."""
        try:
            with mss.mss() as sct:
                # Get the first monitor
                monitor = sct.monitors[1]
                screenshot_path = self.output_dir / f"screen_{int(time.time())}.png"
                
                # Capture
                sct.shot(mon=1, output=str(screenshot_path))
                logger.info(f"Screenshot captured: {screenshot_path}")
                
                # OCR (Requires tesseract-ocr installed on system)
                img = Image.open(screenshot_path)
                text = pytesseract.image_to_string(img)
                
                if text.strip():
                    await self.memory.add_experience(
                        content=f"SCREEN OBSERVATION:\n{text}",
                        source="screen_perception"
                    )
                    logger.success("Screen text captured and stored.")
                else:
                    logger.debug("No text detected in screenshot.")
                    
        except Exception as e:
            logger.error(f"Screen capture failed: {e}")

    async def collect(self):
        """Perform a screen collection cycle."""
        logger.info("Starting screen perception cycle...")
        await self.capture_and_ocr()
