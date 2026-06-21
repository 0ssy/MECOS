"""
MECOS Health Monitoring System
Monitors system components, detects degradation, and provides recovery suggestions.
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from loguru import logger

from config import settings
from memory_system import MemorySystem


class HealthCheck:
    """Result of a health check."""

    def __init__(self, name: str, status: str, message: str = "", latency: float = 0.0, details: Optional[Dict] = None):
        self.name = name
        self.status = status  # "ok", "warn", "error"
        self.message = message
        self.latency = latency
        self.details = details or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "latency": self.latency,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class HealthMonitor:
    """Central health monitoring for MECOS components."""

    def __init__(self, memory: MemorySystem):
        self.memory = memory
        self.checks: Dict[str, HealthCheck] = {}
        self._start_time = time.time()
        self._failure_history: List[Dict[str, Any]] = []
        self.save_dir = settings.MEMORY_DIR / "health"
        self.save_dir.mkdir(parents=True, exist_ok=True)

    async def run_checks(self) -> Dict[str, HealthCheck]:
        """Run all registered health checks."""
        checks = {
            "memory": self._check_memory,
            "llm": self._check_llm,
            "brokers": self._check_brokers,
            "disk_space": self._check_disk_space,
        }

        results = {}
        for name, check_func in checks.items():
            try:
                result = await check_func()
                results[name] = result
                self.checks[name] = result
            except Exception as e:
                logger.error(f"Health check {name} failed: {e}")
                results[name] = HealthCheck(name, "error", str(e))

        self._save_results()
        return results

    async def _check_memory(self) -> HealthCheck:
        """Check memory system health."""
        start = time.time()
        try:
            stats = await self.memory.get_stats()
            count = stats.get("experience_count", 0)
            if count == 0:
                return HealthCheck("memory", "warn", "No experiences stored yet", time.time() - start, stats)
            return HealthCheck("memory", "ok", f"{count} experiences", time.time() - start, stats)
        except Exception as e:
            return HealthCheck("memory", "error", str(e), time.time() - start)

    async def _check_llm(self) -> HealthCheck:
        """Check LLM connectivity."""
        start = time.time()
        try:
            from mecos_llm import get_mecos_llm
            llm = get_mecos_llm()
            # Quick health check
            result = await llm.think_and_act("Test", "Respond with 'ok'")
            if result.get("response"):
                return HealthCheck("llm", "ok", "LLM responding", time.time() - start)
            return HealthCheck("llm", "warn", "LLM returned empty", time.time() - start)
        except Exception as e:
            return HealthCheck("llm", "error", f"LLM unavailable: {e}", time.time() - start)

    async def _check_brokers(self) -> HealthCheck:
        """Check broker connectivity."""
        start = time.time()
        details = {}
        
        if settings.ALPACA_API_KEY:
            try:
                from alpaca.trading.client import TradingClient
                client = TradingClient(api_key=settings.ALPACA_API_KEY, secret_key=settings.ALPACA_SECRET_KEY, paper=True)
                account = client.get_account()
                details["alpaca"] = "ok"
            except Exception as e:
                details["alpaca"] = f"error: {e}"
        else:
            details["alpaca"] = "disabled"

        if settings.BINANCE_API_KEY:
            try:
                from binance.client import Client
                client = Client(api_key=settings.BINANCE_API_KEY, api_secret=settings.BINANCE_SECRET_KEY)
                client.get_account()
                details["binance"] = "ok"
            except Exception as e:
                details["binance"] = f"error: {e}"
        else:
            details["binance"] = "disabled"

        error_count = sum(1 for v in details.values() if "error" in str(v))
        status = "ok" if error_count == 0 else "warn"
        return HealthCheck("brokers", status, f"{error_count} errors", time.time() - start, details)

    def _check_disk_space(self) -> HealthCheck:
        """Check available disk space."""
        import shutil
        start = time.time()
        
        try:
            usage = shutil.disk_usage(settings.MEMORY_DIR)
            free_gb = usage.free / (1024 ** 3)
            total_gb = usage.total / (1024 ** 3)
            pct_free = (usage.free / usage.total) * 100

            if pct_free < 5:
                return HealthCheck("disk_space", "error", f"Low disk space: {free_gb:.1f}GB free", time.time() - start, {"free_gb": free_gb})
            if pct_free < 10:
                return HealthCheck("disk_space", "warn", f"Disk space low: {free_gb:.1f}GB free", time.time() - start, {"free_gb": free_gb})
            return HealthCheck("disk_space", "ok", f"{free_gb:.1f}GB free", time.time() - start, {"free_gb": free_gb})
        except Exception as e:
            return HealthCheck("disk_space", "error", str(e), time.time() - start)

    def _save_results(self) -> None:
        """Save health check results to disk."""
        path = self.save_dir / "health_log.jsonl"
        with open(path, "a", encoding="utf-8") as f:
            for check in self.checks.values():
                f.write(json.dumps(check.to_dict()) + "\n")

    def get_uptime_seconds(self) -> float:
        """Return system uptime in seconds."""
        return time.time() - self._start_time

    def get_degradation_alert(self) -> Optional[str]:
        """Detect performance degradation patterns."""
        if len(self.checks) < 2:
            return None

        degraded = [name for name, check in self.checks.items() if check.status in ("error", "warn")]
        if degraded:
            return f"Degraded components detected: {', '.join(degraded)}"
        return None

    def suggest_recovery(self) -> List[str]:
        """Suggest recovery actions based on current health."""
        suggestions = []

        for name, check in self.checks.items():
            if check.status == "error":
                if name == "memory":
                    suggestions.append("Restart memory system or check disk permissions")
                elif name == "llm":
                    suggestions.append("Verify Ollama is running: ollama serve")
                elif name == "brokers":
                    suggestions.append("Check API keys and network connectivity")
                elif name == "disk_space":
                    suggestions.append("Free disk space or archive old logs")

        return suggestions

    async def periodic_check(self, interval: float = 60.0) -> None:
        """Run health checks periodically."""
        while True:
            results = await self.run_checks()
            for check in results.values():
                if check.status != "ok":
                    logger.warning(f"Health alert [{check.name}]: {check.message}")

            degradation = self.get_degradation_alert()
            if degradation:
                logger.warning(degradation)

            await asyncio.sleep(interval)