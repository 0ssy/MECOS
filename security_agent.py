"""
MECOS Special Agent - Security Agent
Handles threat detection, system security scanning, safe operation validation,
and security event monitoring.
"""

import asyncio
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from loguru import logger

from memory_system import MemorySystem
from tool_registry import ToolRegistry, ToolSpec, ToolPermission


class SecurityAgent:
    """
    Security oversight agent for MECOS.
    Scans for threats, validates operations, and maintains security posture.
    """

    THREAT_PATTERNS = {
        "file_exfiltration": re.compile(r"(send|upload|post).*\.?(txt|json|csv|db|sqlite)", re.IGNORECASE),
        "privilege_escalation": re.compile(r"(sudo|runas|elevate).*password", re.IGNORECASE),
        "network_scan": re.compile(r"(scan|portscan|nmap).*network", re.IGNORECASE),
        "sensitive_access": re.compile(r"(key|token|password|secret).*store|retrieve", re.IGNORECASE),
    }

    def __init__(self, memory: MemorySystem, registry: Optional[ToolRegistry] = None):
        self.memory = memory
        self.registry = registry
        self.threat_log: List[Dict] = []
        self._blocked_patterns: List[str] = []
        logger.info("SecurityAgent initialized.")

    async def validate_operation(self, tool: str, args: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate a tool operation for security concerns."""
        # Check tool exists and is enabled
        if self.registry:
            spec = self.registry.get(tool)
            if not spec:
                return False, f"Unknown tool: {tool}"
            if not spec.enabled:
                return False, f"Tool {tool} is disabled"

        # Check for blocked patterns in arguments
        args_str = str(args).lower()
        for threat_type, pattern in self.THREAT_PATTERNS.items():
            if pattern.search(args_str):
                threat_msg = f"Blocked: potential {threat_type} in {tool}"
                await self._log_threat("blocked", tool, args, threat_msg)
                return False, threat_msg

        return True, "approved"

    async def scan_system_security(self) -> Dict[str, Any]:
        """Run basic security scans on the system."""
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {},
        }

        # Check for suspicious processes
        try:
            import psutil
            suspicious = []
            for proc in psutil.process_iter(["name", "cmdline"]):
                try:
                    cmdline = " ".join(proc.info.get("cmdline", [])).lower()
                    if any(s in cmdline for s in ("nc -l", "ncat", "reverse shell", "backdoor")):
                        suspicious.append(proc.info)
                except Exception:
                    pass
            results["checks"]["suspicious_processes"] = suspicious
        except ImportError:
            results["checks"]["suspicious_processes"] = "psutil not available"

        # Check file permissions
        sensitive_files = list(Path(".").glob(".env*")) + list(Path(".").glob("*secret*"))
        results["checks"]["sensitive_file_permissions"] = [
            {"file": str(f), "mode": oct(f.stat().st_mode)[-3:]} for f in sensitive_files if f.exists()
        ]

        await self.memory.add_experience(
            f"SECURITY SCAN: {len(results['checks'])} checks performed",
            source="security_agent",
        )
        return results

    async def _log_threat(self, threat_type: str, tool: str, args: Dict, message: str) -> None:
        """Log security threat to memory and internal log."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": threat_type,
            "tool": tool,
            "args": args,
            "message": message,
        }
        self.threat_log.append(entry)
        await self.memory.add_experience(
            f"SECURITY THREAT [{threat_type}]: {message}",
            source="security_agent",
        )

    def get_security_status(self) -> Dict[str, Any]:
        """Return current security status."""
        return {
            "threats_detected": len([t for t in self.threat_log if t["type"] != "info"]),
            "recent_threats": [t for t in self.threat_log[-5:]],
            "blocked_patterns": self._blocked_patterns,
        }

    async def audit_tool_usage(self, days: int = 7) -> Dict[str, Any]:
        """Audit tool usage patterns for anomalies."""
        context = await self.memory.retrieve_context("tool execution", n_results=100)
        docs = context.get("documents", [[]])[0] if context else []

        audit = {
            "total_executions": len(docs),
            "tools_used": {},
            "anomalies": [],
        }

        for doc in docs:
            # Extract tool names from log entries
            matches = re.findall(r"tool[=:]\s*(\w+)", doc.lower())
            for tool in matches:
                audit["tools_used"][tool] = audit["tools_used"].get(tool, 0) + 1

        # Detect anomalies (unusual tool combinations)
        for tool, count in audit["tools_used"].items():
            if tool in ("terminal_command", "execute_bash") and count > 50:
                audit["anomalies"].append(f"High {tool} usage: {count} times")

        return audit


# Type hints
from typing import Tuple