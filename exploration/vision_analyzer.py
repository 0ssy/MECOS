import base64
import io
import requests
from PIL import Image
from loguru import logger
from exploration.config import config

class VisionAnalyzer:
    def __init__(self):
        self.server_url = config.MECOS_SERVER_URL

    def encode_image(self, image):
        img_copy = image.copy()
        img_copy.thumbnail((config.BROWSER_WINDOW_WIDTH, config.BROWSER_WINDOW_HEIGHT))
        buffered = io.BytesIO()
        img_copy.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()

    async def analyze_screenshot(self, image, prompt="What is happening?"):
        try:
            img_base64 = self.encode_image(image)
            response = requests.post(
                f"{self.server_url}/analyze_screen",
                json={"image": img_base64, "prompt": prompt},
                timeout=config.VISION_TIMEOUT
            )
            return response.json().get("analysis", "") if response.status_code == 200 else ""
        except Exception as e:
            logger.error(f"Vision error: {e}")
            return ""
