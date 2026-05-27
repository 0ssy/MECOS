"""
MECOS Coding Layer — Engineering + Sandbox execution.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Dict

from loguru import logger


class SandboxExecutor:
    def __init__(self, work_dir: str | None = None):
        base = Path(work_dir) if work_dir else Path(__file__).resolve().parent / "sandbox" / "runtime"
        self.work_dir = base
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def execute_code(self, code: str, filename: str = "experiment.py") -> Dict[str, Any]:
        file_path = self.work_dir / filename
        file_path.write_text(code, encoding="utf-8")
        try:
            proc = subprocess.run(
                ["python", str(file_path)],
                capture_output=True,
                text=True,
                timeout=15,
            )
            return {"success": proc.returncode == 0, "stdout": proc.stdout, "stderr": proc.stderr}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Execution timed out"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}


class CodingAgent:
    def __init__(self, sandbox: SandboxExecutor):
        self.sandbox = sandbox

    async def build_module(self, name: str, requirements: str) -> str:
        logger.info(f"Building module: {name}")
        code = (
            f"def {name}_function():\n"
            f"    return 'Generated for: {requirements}'\n\n"
            "if __name__ == '__main__':\n"
            f"    print({name}_function())\n"
        )
        result = self.sandbox.execute_code(code, f"{name}.py")
        if not result.get("success"):
            logger.error(f"Generated module failed sandbox: {result.get('stderr') or result.get('error')}")
            return ""
        return code

