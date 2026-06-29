"""
Kilo Bridge - Phase 4
Subprocess wrapper for Kilo CLI with timeout and JSON parsing.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

from config import settings


KILO_TIMEOUT = int(os.getenv("KILO_TIMEOUT", "30"))


class KiloBridge:
    def __init__(self):
        self._kilo_cmd = self._find_kilo_cmd()
        self.available = self._kilo_cmd is not None

    def _find_kilo_cmd(self) -> Optional[str]:
        import shutil
        cmd = shutil.which("kilo")
        if cmd:
            return cmd
        if os.name == "nt":
            kilo_cmd = Path("kilo.cmd")
            if kilo_cmd.exists():
                return str(kilo_cmd.resolve())
        return None

    def _extract_json(self, text: str) -> Optional[str]:
        if not text:
            return None
        fence_match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
        candidate = fence_match.group(1) if fence_match else text
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start != -1 and end > start:
            try:
                return candidate[start:end + 1]
            except Exception:
                pass
        return None

    def _parse_output(self, stdout: str) -> Optional[str]:
        json_str = self._extract_json(stdout)
        if json_str:
            try:
                data = json.loads(json_str)
                return data.get("response") or data.get("answer") or json_str
            except json.JSONDecodeError:
                pass
        lines = [l for l in stdout.splitlines() if l.strip() and not l.startswith("\x1b")]
        return lines[-1] if lines else None

    def invoke(
        self,
        prompt: str,
        timeout: int = KILO_TIMEOUT,
    ) -> Optional[str]:
        if not self._kilo_cmd:
            logger.debug("Kilo CLI not available")
            return None

        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
                f.write(prompt)
                prompt_path = f.name

            cmd = [self._kilo_cmd, "--prompt-file", prompt_path]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(settings.BASE_DIR),
            )
            Path(prompt_path).unlink(missing_ok=True)

            if proc.returncode == 0 and proc.stdout:
                return self._parse_output(proc.stdout)
            logger.warning(f"Kilo invocation failed: {proc.stderr[:200]}")
            return None
        except subprocess.TimeoutExpired:
            logger.warning(f"Kilo timed out after {timeout}s")
            return None
        except Exception as e:
            logger.error(f"Kilo invocation error: {e}")
            return None

    async def ask(
        self,
        prompt: str,
        timeout: int = KILO_TIMEOUT,
    ) -> Optional[str]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.invoke, prompt, timeout)

    def build_code_prompt(self, question: str, context: str = "") -> str:
        return f"""Question: {question}

Context (if any):
{context[:500]}

Provide a concise answer with code examples if relevant. Focus on practical implementation.
Return JSON: {{ "response": "your answer here", "code": "optional code" }}
"""

    def format_response(self, raw: Optional[str], question: str) -> dict:
        if not raw:
            return {"response": None, "error": "Kilo unavailable or timed out"}
        return {"response": raw, "question": question, "timestamp": datetime.utcnow().isoformat()}