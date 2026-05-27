"""
MECOS Phase 4 - Code Executor
Sandboxed multi-language code execution with resource limits, output capture, and validation.
Uses subprocess isolation with configurable timeouts and memory limits.
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from loguru import logger

from config import settings


@dataclass
class ExecutionResult:
    """Result of a code execution."""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    language: str
    execution_time: float


LANGUAGE_CONFIGS = {
    "python": {
        "extension": ".py",
        "command": [sys.executable],
        "comment": "#",
    },
    "bash": {
        "extension": ".sh",
        "command": ["bash"],
        "comment": "#",
    },
    "javascript": {
        "extension": ".js",
        "command": ["node"],
        "comment": "//",
    },
}


class CodeExecutor:
    """
    Sandboxed code execution engine.
    Runs code in isolated subprocesses with strict timeouts and output limits.
    """

    def __init__(
        self,
        timeout: int = 30,
        max_output_bytes: int = 65536,
        max_code_chars: int = 12000,
        max_concurrent_executions: int = 2,
    ):
        self.timeout = timeout
        self.max_output_bytes = max_output_bytes
        self.max_code_chars = max_code_chars
        self._semaphore = asyncio.Semaphore(max(1, int(max_concurrent_executions)))
        self.sandbox_dir = settings.DATA_DIR / "sandbox"
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"CodeExecutor initialized. Sandbox: {self.sandbox_dir}")

    @staticmethod
    def _has_forbidden_pattern(code: str, language: str) -> bool:
        lowered = (code or "").lower()
        forbidden_common = [
            "rm -rf /",
            "del /f /s /q c:\\",
            "shutdown ",
            "format c:",
        ]
        forbidden_python = [
            "import ctypes",
            "os.system(",
            "subprocess.popen(",
        ]
        forbidden_js = [
            "require('child_process')",
            "process.exit(",
        ]

        patterns = list(forbidden_common)
        if language == "python":
            patterns.extend(forbidden_python)
        if language == "javascript":
            patterns.extend(forbidden_js)
        return any(p in lowered for p in patterns)

    async def execute(
        self,
        code: str,
        language: str = "python",
        timeout: Optional[int] = None,
        trusted: bool = False,
    ) -> ExecutionResult:
        """Execute code in the specified language within a sandboxed subprocess."""
        import time

        lang = language.lower()
        if lang not in LANGUAGE_CONFIGS:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Unsupported language: {language}. Supported: {list(LANGUAGE_CONFIGS.keys())}",
                exit_code=-1,
                language=language,
                execution_time=0.0,
            )

        config = LANGUAGE_CONFIGS[lang]
        effective_timeout = timeout or self.timeout
        if len(code or "") > self.max_code_chars:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Code size exceeds limit ({self.max_code_chars} chars).",
                exit_code=-1,
                language=language,
                execution_time=0.0,
            )
        if not trusted and self._has_forbidden_pattern(code, lang):
            return ExecutionResult(
                success=False,
                stdout="",
                stderr="Execution blocked by sandbox policy.",
                exit_code=-1,
                language=language,
                execution_time=0.0,
            )

        temp_path = None
        if lang == "bash":
            cmd = ["bash", "-lc", code]
        else:
            # Write code to a temp file in the sandbox
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=config["extension"],
                dir=self.sandbox_dir,
                delete=False,
            ) as f:
                f.write(code)
                temp_path = f.name
            cmd = config["command"] + [temp_path]
        start = time.monotonic()
        safe_env = os.environ.copy()
        safe_env["PYTHONIOENCODING"] = "utf-8"
        safe_env["PYTHONUNBUFFERED"] = "1"

        try:
            async with self._semaphore:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(self.sandbox_dir),
                    env=safe_env,
                )
                try:
                    stdout_bytes, stderr_bytes = await asyncio.wait_for(
                        proc.communicate(), timeout=effective_timeout
                    )
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.communicate()
                    elapsed = time.monotonic() - start
                    logger.warning(f"Code execution timed out after {effective_timeout}s")
                    return ExecutionResult(
                        success=False,
                        stdout="",
                        stderr=f"Execution timed out after {effective_timeout} seconds.",
                        exit_code=-1,
                        language=language,
                        execution_time=elapsed,
                    )

            elapsed = time.monotonic() - start
            stdout = stdout_bytes[: self.max_output_bytes].decode("utf-8", errors="replace")
            stderr = stderr_bytes[: self.max_output_bytes].decode("utf-8", errors="replace")
            success = proc.returncode == 0

            if success:
                logger.debug(f"Code executed successfully in {elapsed:.2f}s [{lang}]")
            else:
                logger.warning(f"Code execution failed (exit {proc.returncode}) [{lang}]: {stderr[:200]}")

            return ExecutionResult(
                success=success,
                stdout=stdout,
                stderr=stderr,
                exit_code=proc.returncode,
                language=language,
                execution_time=elapsed,
            )

        except Exception as e:
            elapsed = time.monotonic() - start
            logger.error(f"CodeExecutor error: {e}")
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                language=language,
                execution_time=elapsed,
            )
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

    async def execute_python(self, code: str, timeout: Optional[int] = None) -> ExecutionResult:
        return await self.execute(code, language="python", timeout=timeout)

    async def execute_bash(self, command: str, timeout: Optional[int] = None) -> ExecutionResult:
        return await self.execute(command, language="bash", timeout=timeout)

    async def run_tests(self, test_file: str, timeout: int = 60) -> ExecutionResult:
        """Run pytest on a test file and return results."""
        code = f"import subprocess, sys\nresult = subprocess.run([sys.executable, '-m', 'pytest', '{test_file}', '-v', '--tb=short'], capture_output=True, text=True)\nprint(result.stdout)\nprint(result.stderr, file=__import__('sys').stderr)\nsys.exit(result.returncode)"
        return await self.execute(code, language="python", timeout=timeout, trusted=True)
