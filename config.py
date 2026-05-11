"""
MECOS Configuration
Centralized settings for the MECOS engine.
Refactored for 100% local-first operation.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # Project Identity
    PROJECT_NAME: str = "MECOS"
    VERSION: str = "0.7.0-local"

    # Paths
    BASE_DIR: Path = Path(__file__).parent
    DATA_DIR: Path = BASE_DIR / "data"
    MEMORY_DIR: Path = BASE_DIR / "memory_db"
    VECTOR_DB_PATH: str = str(MEMORY_DIR / "vector_db")
    LOGS_DIR: Path = BASE_DIR / "logs"

    # Distributed LLM Configuration (No API Keys Required)
    # Set SERVER_IP to the IP address of your server laptop.
    SERVER_IP: str = "192.168.1.88"  # Replace with your Server Laptop's IP address
    LOCAL_LLM_URL: str = f"http://{SERVER_IP}:11434/v1"
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "llama3") # Or mistral, phi3, etc.
    
    # Embedding Configuration (Local)
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2" # Runs locally via sentence-transformers

    # Agent Settings
    MAX_PLAN_STEPS: int = 10
    RETRY_ATTEMPTS: int = 3
    
    # Security
    ENABLE_SANDBOX: bool = True
    ALLOWED_COMMANDS: list = ["ls", "cat", "echo", "grep", "find", "mkdir", "rm", "cp", "mv", "python3", "pip", "git"]

    # Hardware Optimization (for Laptop-Server)
    LOW_RESOURCE_MODE: bool = True
    MAX_CONCURRENT_AGENTS: int = 2
    CPU_LIMIT_PERCENT: int = 80
    IDLE_SLEEP_TIME: int = 60 # Seconds between cognitive cycles when idle

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()

# Ensure directories exist
for path in [settings.DATA_DIR, settings.MEMORY_DIR, settings.LOGS_DIR]:
    path.mkdir(parents=True, exist_ok=True)
