"""
MECOS Coding Layer — Self-debug and autonomous repair scaffold.
"""
from __future__ import annotations

from typing import Any, Dict

from loguru import logger

from engineer import SandboxExecutor


class SelfDebugger:
    def __init__(self, sandbox: SandboxExecutor):
        self.sandbox = sandbox

    async def verify_and_repair(self, code: str, filename: str) -> Dict[str, Any]:
        result = self.sandbox.execute_code(code, filename)
        if result.get("success"):
            return {"success": True, "code": code}

        logger.warning(f"Verification failed for {filename}: {result.get('stderr') or result.get('error')}")
        repaired = self._attempt_repair(code, result.get("stderr", ""))
        retry = self.sandbox.execute_code(repaired, filename)
        if retry.get("success"):
            return {"success": True, "code": repaired}
        return {"success": False, "error": retry.get("stderr") or retry.get("error")}

    def _attempt_repair(self, code: str, error_msg: str) -> str:
        if "NameError" in error_msg:
            return "import os\n" + code
        return code

