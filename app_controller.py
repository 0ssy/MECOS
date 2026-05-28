import asyncio
import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger
import psutil


class AppController:
    def __init__(self, knowledge_base_path: Optional[str] = None):
        self.kb_path = knowledge_base_path or "exploration/discoveries/knowledge.json"
        self._allowed_prefixes = (
            "echo",
            "python",
            "python3",
            "pip",
            "git",
            "pytest",
            "ls",
            "dir",
            "type",
            "cat",
            "findstr",
            "grep",
        )
        self._blocked_patterns = (
            "rm -rf",
            "shutdown",
            "reboot",
            "format ",
            "del /f /s /q",
        )
        logger.info(f"AppController initialized. Using KB: {self.kb_path}")

    def _get_app_path(self, app_name: str) -> Optional[str]:
        try:
            if os.path.exists(self.kb_path):
                with open(self.kb_path, "r", encoding="utf-8") as f:
                    kb = json.load(f)
                    apps = kb.get("system_apps", {}) or kb.get("apps", {})
                    for name, path in apps.items():
                        if app_name.lower() in str(name).lower():
                            return str(path)
        except Exception as e:
            logger.error(f"Error reading Knowledge Base: {e}")
        return None

    def map_computer(self, process_limit: int = 50, executable_limit: int = 150) -> Dict[str, Any]:
        process_limit = max(1, int(process_limit))
        executable_limit = max(1, int(executable_limit))

        running_processes = []
        for proc in psutil.process_iter(["pid", "name", "exe"]):
            try:
                info = proc.info
                running_processes.append(
                    {
                        "pid": int(info.get("pid") or 0),
                        "name": str(info.get("name") or ""),
                        "exe": str(info.get("exe") or ""),
                    }
                )
            except Exception:
                continue
            if len(running_processes) >= process_limit:
                break

        known_execs = []
        candidates = []
        if os.name == "nt":
            candidates.extend(
                [
                    Path(os.environ.get("WINDIR", "C:\\Windows")) / "System32",
                    Path(os.environ.get("ProgramFiles", "C:\\Program Files")),
                    Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")),
                ]
            )
        else:
            candidates.extend([Path("/usr/bin"), Path("/usr/local/bin")])

        for base in candidates:
            if not base.exists():
                continue
            try:
                for child in base.rglob("*"):
                    if not child.is_file():
                        continue
                    name = child.name.lower()
                    if os.name == "nt":
                        if not name.endswith(".exe"):
                            continue
                    elif not os.access(child, os.X_OK):
                        continue
                    known_execs.append(str(child))
                    if len(known_execs) >= executable_limit:
                        break
            except Exception:
                continue
            if len(known_execs) >= executable_limit:
                break

        return {
            "os": os.name,
            "working_directory": os.getcwd(),
            "running_processes": running_processes,
            "installed_executables": known_execs,
            "status": "HEALTHY",
        }

    def get_system_info(self) -> Dict[str, Any]:
        vm = psutil.virtual_memory()
        disk = psutil.disk_usage(str(Path.cwd().anchor or Path.cwd()))
        return {
            "cpu_percent": float(psutil.cpu_percent(interval=0.1)),
            "memory_used": int(vm.used),
            "memory_total": int(vm.total),
            "disk_used": int(disk.used),
            "disk_total": int(disk.total),
        }

    async def run_command(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        command = str(command or "").strip()
        if not command:
            return {"command": command, "exit_code": "-1", "stdout": "", "stderr": "Empty command"}

        lowered = command.lower()
        if any(p in lowered for p in self._blocked_patterns):
            return {
                "command": command,
                "exit_code": "-1",
                "stdout": "",
                "stderr": "Command blocked by allowlist policy",
            }

        if command.lower().startswith("open "):
            app_name = command[5:].strip()
            app_path = self._get_app_path(app_name)
            if not app_path:
                return {
                    "command": command,
                    "exit_code": "-1",
                    "stdout": "",
                    "stderr": f"Unknown app: {app_name}",
                }
            if os.name == "nt":
                command = f'start "" "{app_path}"'
            else:
                command = f'xdg-open "{app_path}"'
        else:
            first = shlex.split(command)[0].lower() if command else ""
            if not any(first.startswith(prefix) for prefix in self._allowed_prefixes):
                return {
                    "command": command,
                    "exit_code": "-1",
                    "stdout": "",
                    "stderr": "Command blocked by allowlist policy",
                }

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=max(1, int(timeout)))
            return {
                "command": command,
                "exit_code": str(proc.returncode),
                "stdout": stdout.decode(errors="replace").strip(),
                "stderr": stderr.decode(errors="replace").strip(),
            }
        except asyncio.TimeoutError:
            return {
                "command": command,
                "exit_code": "-1",
                "stdout": "",
                "stderr": f"Timeout after {timeout}s",
            }
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return {"command": command, "exit_code": "-1", "stdout": "", "stderr": str(e)}

    async def execute_command(self, command: str) -> str:
        result = await self.run_command(command)
        return result.get("stdout") or result.get("stderr", "")
