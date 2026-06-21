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

    # ── OANDA (Forex) ──────────────────────────────────────────────────────
    OANDA_API_KEY: str = os.getenv("OANDA_API_KEY", "")
    OANDA_ACCOUNT_ID: str = os.getenv("OANDA_ACCOUNT_ID", "")
    OANDA_ENV: str = os.getenv("OANDA_ENV", "practice")
    OANDA_BASE_URL: str = os.getenv(
        "OANDA_BASE_URL",
        "https://api-fxpractice.oanda.com/v3"
        if os.getenv("OANDA_ENV", "practice").lower() == "practice"
        else "https://api-fxtrade.oanda.com/v3",
    )
    OANDA_STREAM_URL: str = os.getenv(
        "OANDA_STREAM_URL",
        "https://stream-fxpractice.oanda.com/v3"
        if os.getenv("OANDA_ENV", "practice").lower() == "practice"
        else "https://stream-fxtrade.oanda.com/v3",
    )

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

    # ── Skill Configuration ──────────────────────────────────────────────────
    KILO_SKILLS_DIR: Path = BASE_DIR / ".kilo"
    ENABLED_SKILLS: list = [
        "marketing-skills", "gstack", "social-media-skills", "superpowers",
        "kilocode", "financial-services", "legal-workflow", "front-end-design",
        "humanizer", "ai-second-brain", "notebook-llm", "seo-tools",
        "hyperframes", "doc-skills", "caveman", "obsidian", "last30days",
    ]

    # ── MCP Servers ───────────────────────────────────────────────────────────
    MCP_SERVERS: dict = {
        "notion": {"command": "npx", "args": ["-y", "@notionhq/notion-mcp-server"]},
        "slack": {"command": "npx", "args": ["-y", "slack-mcp-server"]},
        "granola": {"command": "uvx", "args": ["granola-mcp-server"]},
        "zapier": {"command": "npx", "args": ["-y", "zapier-mcp-server"]},
    }

    # ── LLM Provider Configuration (FREE TIER) ─────────────────────────────────────
    LLM_ROUTER: str = os.getenv("LLM_ROUTER", "local")  # local | free_remote
    LLM_PROVIDERS: dict = {
        "local": {
            "base_url": os.getenv("LOCAL_LLM_URL", "http://127.0.0.1:11434/v1"),
            "model": os.getenv("DEFAULT_MODEL", "llama3"),
            "api_key": "local-no-key",
            "cost": "$0 (local Ollama)",
        },
        "ollama-phi3": {
            "base_url": os.getenv("LOCAL_LLM_URL", "http://127.0.0.1:11434/v1"),
            "model": os.getenv("PHI3_MODEL", "phi3:mini"),
            "api_key": "local-no-key",
            "cost": "$0 (local Ollama - Microsoft phi3:mini)",
        },
        "groq-free": {
            "base_url": "https://api.groq.com/v1",
            "model": os.getenv("GROQ_MODEL", "llama3-8b-8192"),
            "api_key": os.getenv("GROQ_API_KEY", ""),
            "cost": "$0 (Groq free tier - limited daily)",
        },
        "huggingface-free": {
            "base_url": "https://api-inference.huggingface.co/v1",
            "model": os.getenv("HF_MODEL", "microsoft/phi-3-mini-4k-instruct"),
            "api_key": os.getenv("HF_API_KEY", ""),
            "cost": "$0 (HF Inference API - rate limited)",
        },
        # PAID TIER - Uncomment when MECOS generates revenue ($0-$1000)
        # "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini", "api_key": os.getenv("OPENAI_API_KEY", ""), "cost": "$"},
        # "anthropic": {"base_url": "https://api.anthropic.com/v1", "model": "claude-3-haiku-20240307", "api_key": os.getenv("ANTHROPIC_API_KEY", ""), "cost": "$"},
        # "google": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "model": "gemini-1.5-flash", "api_key": os.getenv("GOOGLE_API_KEY", ""), "cost": "$"},
    }

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()

# Ensure required directories exist
for _path in [settings.DATA_DIR, settings.MEMORY_DIR, settings.LOGS_DIR]:
    _path.mkdir(parents=True, exist_ok=True)

