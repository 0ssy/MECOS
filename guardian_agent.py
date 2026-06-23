"""
MECOS Special Agent - Guardian Agent
Safety oversight, operation approval, and intervention when anomalies detected.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger

from memory_system import MemorySystem
from health_monitor import HealthMonitor, HealthCheck


class GuardianAgent:
    """
    Safety oversight agent for MECOS.
    Monitors operations, intervenes when anomalies detected, and maintains kill switch.
    """

    def __init__(self, memory: MemorySystem, health_monitor: Optional[HealthMonitor] = None):
        self.memory = memory
        self.health = health_monitor
        self._intervention_log: List[Dict] = []
        self._kill_switch_triggered = False
        self._safety_rules = {
            "max_position_size_multiplier": 10,
            "daily_loss_limit_multiplier": 2,
            "max_consecutive_failures": 5,
        }
        logger.info("GuardianAgent initialized.")

    async def pre_execution_check(self, action: str, context: Dict) -> Tuple[bool, str]:
        """Check if action should proceed based on safety rules."""
        if self._kill_switch_triggered:
            return False, "Kill switch activated by GuardianAgent"

        # Check health status
        if self.health:
            health = self.health.get_degradation_alert()
            if health:
                return False, f"Health alert: {health}"

        # Check for high-risk patterns
        if "delete" in action.lower() and "all" in str(context).lower():
            return False, "Refused to execute destructive bulk operation"

        return True, "approved"

    async def post_execution_check(self, action: str, result: Any, expected: Optional[Dict] = None) -> Optional[str]:
        """Check execution result and trigger interventions if needed."""
        if expected:
            for key, expected_val in expected.items():
                actual = self._deep_get(result, key)
                if actual != expected_val:
                    msg = f"Intervention: {key} mismatch (expected {expected_val}, got {actual})"
                    await self._intervene(msg, action, result)
                    return msg

        return None

    async def _intervene(self, reason: str, action: str, context: Any) -> None:
        """Log and potentially halt on intervention."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "action": action,
            "context_preview": str(context)[:200],
        }
        self._intervention_log.append(entry)
        
        await self.memory.add_experience(
            f"GUARDIAN INTERVENTION: {reason}",
            source="guardian_agent",
        )
        logger.warning(f"Guardian intervention: {reason}")

    def _deep_get(self, obj: Any, path: str) -> Any:
        """Get nested value from dict/list using dot notation."""
        keys = path.split(".")
        for key in keys:
            if isinstance(obj, dict):
                obj = obj.get(key)
            elif isinstance(obj, list):
                try:
                    obj = obj[int(key)]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return obj

    def get_intervention_history(self, limit: int = 10) -> List[Dict]:
        """Return recent interventions."""
        return self._intervention_log[-limit:]

    def trigger_kill_switch(self, reason: str) -> None:
        """Activate the kill switch."""
        self._kill_switch_triggered = True
        logger.critical(f"Kill switch triggered: {reason}")

    def reset_kill_switch(self) -> None:
        """Reset kill switch after manual review."""
        self._kill_switch_triggered = False
        logger.info("Kill switch reset")

    def is_kill_switch_active(self) -> bool:
        """Check if kill switch is active."""
        return self._kill_switch_triggered

    async def safety_check(self) -> Dict[str, Any]:
        """Run full safety assessment."""
        status = {
            "kill_switch": self._kill_switch_triggered,
            "interventions_today": len([i for i in self._intervention_log 
                                      if datetime.fromisoformat(i["timestamp"]).date() == datetime.now().date()]),
            "health_status": "ok",
        }

        if self.health:
            health_results = await self.health.run_checks()
            degraded = [c for c in health_results.values() if c.status != "ok"]
            if degraded:
                status["health_status"] = "degraded"
                status["health_issues"] = [c.name for c in degraded]

        return status