"""
MECOS Configuration
Centralized settings for the MECOS engine.
Reads all secrets from environment / .env file — never hardcoded.
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv(override=True)


class Settings(BaseSettings):
    # ── Project Identity ──────────────────────────────────────────────────
    PROJECT_NAME: str = "MECOS"
    VERSION: str = "1.0.0-trading"

    # ── Paths ─────────────────────────────────────────────────────────────
    BASE_DIR: Path = Path(__file__).parent
    DATA_DIR: Path = BASE_DIR / "data"
    MEMORY_DIR: Path = BASE_DIR / "memory_db"
    VECTOR_DB_PATH: str = str(BASE_DIR / "memory_db" / "vector_db")
    LOGS_DIR: Path = BASE_DIR / "logs"

    # ── LLM (Ollama / local) ──────────────────────────────────────────────
    SERVER_IP: str = os.getenv("SERVER_IP", "127.0.0.1")
    LOCAL_LLM_URL: str = os.getenv("LOCAL_LLM_URL", f"http://127.0.0.1:11434/v1")
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "llama3")

    # ── Embeddings ────────────────────────────────────────────────────────
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # ── Alpaca (Stocks & Crypto via Alpaca) ──────────────────────────────
    ALPACA_API_KEY: str = os.getenv("ALPACA_API_KEY", "")
    ALPACA_SECRET_KEY: str = os.getenv("ALPACA_SECRET_KEY", "")
    # "paper" uses paper trading endpoint; "live" uses real money
    ALPACA_MODE: str = os.getenv("ALPACA_MODE", "paper")
    ALPACA_BASE_URL: str = (
        "https://paper-api.alpaca.markets"
        if os.getenv("ALPACA_MODE", "paper") == "paper"
        else "https://api.alpaca.markets"
    )

    # ── Binance ───────────────────────────────────────────────────────────
    BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
    BINANCE_SECRET_KEY: str = os.getenv("BINANCE_SECRET_KEY", "")
    # True = use Binance testnet (paper crypto trading)
    BINANCE_TESTNET: bool = os.getenv("BINANCE_TESTNET", "true").lower() == "true"

    # ── Trading Safety ────────────────────────────────────────────────────
    # Hard kill-switch: if False, NO real orders are ever placed regardless of mode
    TRADING_ENABLED: bool = os.getenv("TRADING_ENABLED", "false").lower() == "true"
    MAX_POSITION_SIZE_USD: float = float(os.getenv("MAX_POSITION_SIZE_USD", "100"))
    MAX_DAILY_LOSS_USD: float = float(os.getenv("MAX_DAILY_LOSS_USD", "50"))
    MAX_OPEN_POSITIONS: int = int(os.getenv("MAX_OPEN_POSITIONS", "5"))

    # ── Agent Settings ────────────────────────────────────────────────────
    MAX_PLAN_STEPS: int = 10
    RETRY_ATTEMPTS: int = 3

    # ── Security ─────────────────────────────────────────────────────────
    ENABLE_SANDBOX: bool = True
    ALLOWED_COMMANDS: list = [
        "ls", "cat", "echo", "grep", "find",
        "mkdir", "rm", "cp", "mv", "python3", "pip", "git",
    ]

    # ── Hardware ──────────────────────────────────────────────────────────
    LOW_RESOURCE_MODE: bool = True
    MAX_CONCURRENT_AGENTS: int = 2
    CPU_LIMIT_PERCENT: int = 80
    IDLE_SLEEP_TIME: int = 60
    USE_GPU: bool = False

    # ── Sovereignty / Independence gates ─────────────────────────────────
    GOV_MIN_EXPERIENCES: int = int(os.getenv("GOV_MIN_EXPERIENCES", "500"))
    GOV_MIN_META_EPISODES: int = int(os.getenv("GOV_MIN_META_EPISODES", "10"))
    GOV_MIN_TRADING_ANALYSES: int = int(os.getenv("GOV_MIN_TRADING_ANALYSES", "100"))
    GOV_MIN_TRADING_ACTIONABLE_RATE: float = float(
        os.getenv("GOV_MIN_TRADING_ACTIONABLE_RATE", "0.3")
    )

    # ── Meta-learning acceleration ────────────────────────────────────────
    # Multiplier for batch sizes in meta-learning cycles.
    # 1 = normal, 2 = double batches (faster but heavier on RAM/CPU)
    TRAINING_ACCELERATION_FACTOR: int = int(
        __import__('os').getenv("TRAINING_ACCELERATION_FACTOR", "1")
    )

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()

# Ensure required directories exist
for _path in [settings.DATA_DIR, settings.MEMORY_DIR, settings.LOGS_DIR]:
    _path.mkdir(parents=True, exist_ok=True)

