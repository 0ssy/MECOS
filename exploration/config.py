import os
from pathlib import Path

class ExplorationConfig:
    BASE_DIR = Path.cwd() / "exploration"
    DISCOVERIES_DIR = BASE_DIR / "discoveries"
    DISCOVERIES_DIR.mkdir(parents=True, exist_ok=True)
    MECOS_SERVER_URL = os.getenv("MECOS_SERVER_URL", "http://192.168.1.88:5001" )
    GMAIL_EMAIL = os.getenv("MECOS_GMAIL_EMAIL", "jiganihizu@gmail.com")
    GMAIL_APP_PASSWORD = os.getenv("MECOS_GMAIL_APP_PASSWORD", "")
    BROWSER_HEADLESS = True
    BROWSER_WINDOW_WIDTH = 1280
    BROWSER_WINDOW_HEIGHT = 720
    BROWSER_SESSION_DIR = BASE_DIR / "browser_sessions"
    BROWSER_SESSION_DIR.mkdir(parents=True, exist_ok=True)
    VISION_MODEL = "llava:7b"
    VISION_TIMEOUT = 180 
    EXPLORATION_INTERVAL = 30
    CURIOSITY_LEVEL = 0.8 

config = ExplorationConfig()
