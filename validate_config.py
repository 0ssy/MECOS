"""
MECOS Configuration Validator
Validates environment configuration at startup and runtime.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger


class ConfigValidator:
    """Validates MECOS configuration for correctness and safety."""

    ALPACA_KEY_PATTERN = re.compile(r"^[A-Z0-9]{20,50}$")
    BINANCE_KEY_PATTERN = re.compile(r"^[A-Z0-9]{20,50}$")

    def __init__(self, settings_module=None):
        self.settings = settings_module
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_all(self) -> Tuple[bool, List[str], List[str]]:
        """Run all validations. Returns (is_valid, errors, warnings)."""
        self.errors = []
        self.warnings = []

        self._validate_directories()
        self._validate_api_keys()
        self._validate_trading_config()
        self._validate_network_config()

        return len(self.errors) == 0, self.errors, self.warnings

    def _validate_directories(self) -> None:
        """Ensure required directories exist."""
        dirs_to_check = [
            ("DATA_DIR", Path("data")),
            ("MEMORY_DIR", Path("memory_db")),
            ("LOGS_DIR", Path("logs")),
        ]

        for name, default_path in dirs_to_check:
            path = getattr(self.settings, name, default_path) if self.settings else default_path
            if self.settings and hasattr(self.settings, name):
                actual_path = getattr(self.settings, name).value if hasattr(getattr(self.settings, name), 'value') else getattr(self.settings, name)
                path = Path(actual_path) if isinstance(actual_path, str) else actual_path

            if not path.exists():
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Created directory: {path}")
                except Exception as e:
                    self.errors.append(f"{name} does not exist and cannot be created: {e}")

    def _validate_api_keys(self) -> None:
        """Validate API key formats."""
        if not self.settings:
            return

        alpaca_key = getattr(self.settings, "ALPACA_API_KEY", None)
        alpaca_secret = getattr(self.settings, "ALPACA_SECRET_KEY", None)

        if alpaca_key and alpaca_secret:
            if not (alpaca_key and len(str(alpaca_key)) >= 20):
                self.warnings.append("ALPACA_API_KEY format may be invalid (too short)")
            if not (alpaca_secret and len(str(alpaca_secret)) >= 20):
                self.warnings.append("ALPACA_SECRET_KEY format may be invalid (too short)")

        binance_key = getattr(self.settings, "BINANCE_API_KEY", None)
        binance_secret = getattr(self.settings, "BINANCE_SECRET_KEY", None)

        if binance_key and binance_secret:
            if not (binance_key and len(str(binance_key)) >= 20):
                self.warnings.append("BINANCE_API_KEY format may be invalid (too short)")
            if not (binance_secret and len(str(binance_secret)) >= 20):
                self.warnings.append("BINANCE_SECRET_KEY format may be invalid (too short)")

    def _validate_trading_config(self) -> None:
        """Validate trading-specific configuration."""
        if not self.settings:
            return

        max_pos = float(getattr(self.settings, "MAX_POSITION_SIZE_USD", 100))
        max_daily = float(getattr(self.settings, "MAX_DAILY_LOSS_USD", 50))
        max_open = int(getattr(self.settings, "MAX_OPEN_POSITIONS", 5))

        if max_pos > 10000:
            self.warnings.append(f"MAX_POSITION_SIZE_USD ({max_pos}) is very high")
        if max_daily > max_pos * 3:
            self.warnings.append(f"MAX_DAILY_LOSS_USD ({max_daily}) exceeds 3x position size")
        if max_open < 1 or max_open > 20:
            self.errors.append(f"MAX_OPEN_POSITIONS ({max_open}) must be between 1 and 20")

    def _validate_network_config(self) -> None:
        """Validate network configuration."""
        if not self.settings:
            return

        server_ip = getattr(self.settings, "SERVER_IP", "127.0.0.1")
        if server_ip == "127.0.0.1":
            self.warnings.append("SERVER_IP is localhost - connect to remote server for distributed mode")

    async def probe_tool_availability(self, tool_name: str) -> Dict[str, Any]:
        """Check if a tool is available and working."""
        try:
            from agent_reach.probe import probe_command
            result = probe_command(tool_name)
            return {
                "tool": tool_name,
                "status": result.status,
                "hint": result.hint,
            }
        except Exception as e:
            return {"tool": tool_name, "status": "error", "error": str(e)}

    def get_config_summary(self) -> Dict[str, Any]:
        """Return a redacted summary of current configuration."""
        if not self.settings:
            return {"warning": "No settings module provided"}

        summary = {}
        for attr in dir(self.settings):
            if attr.startswith("_"):
                continue
            value = getattr(self.settings, attr, None)
            if isinstance(value, str) and any(s in attr.lower() for s in ("key", "secret", "token", "password")):
                summary[attr] = f"{str(value)[:8]}..." if value else None
            elif not callable(value):
                summary[attr] = value
        return summary


def validate_on_startup() -> bool:
    """Validate configuration at startup. Call from main.py."""
    from config import settings
    
    validator = ConfigValidator(settings)
    is_valid, errors, warnings = validator.validate_all()

    for warning in warnings:
        logger.warning(f"Config validation warning: {warning}")
    for error in errors:
        logger.error(f"Config validation error: {error}")

    logger.info(f"Configuration summary: {validator.get_config_summary()}")
    return is_valid