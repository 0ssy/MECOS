"""
MECOS Phase 4 - App Controller
Process launching, management, and system automation with permission guardrails.
"""

import asyncio
import subprocess
import os
from pathlib import Path
import psutil
from typing import Optional, List, Dict
from loguru import logger


class AppController:
    """
    Controls application launching, process management, and system automation.
    Maintains an allowlist of safe applications and enforces resource limits.
    """

    # Default allowlist of safe commands/applications
    ALLOWED_COMMANDS = {
        "python", "python3", "node", "npm", "git", "curl", "wget",
        "cat", "ls", "find", "grep", "echo", "mkdir", "cp", "mv",
        "head", "tail", "wc", "sort", "uniq", "awk", "sed",
        "powershell", "cmd", "tasklist", "where", "winget",
    }

    def __init__(self, allowed_commands: Optional[List[str]] = None):
        self._processes: Dict[int, subprocess.Popen] = {}
        self.allowed_commands = set(allowed_commands or self.ALLOWED_COMMANDS)
        logger.info("AppController initialized.")

    def _is_allowed(self, command: str) -> bool:
        """Check if the base command is in the allowlist."""
        base = command.strip().split()[0].split("/")[-1]
        return base in self.allowed_commands

    async def run_command(
        self,
        command: str,
        timeout: int = 30,
        cwd: Optional[str] = None,
        capture: bool = True,
    ) -> Dict[str, str]:
        """
        Run a shell command asynchronously.
        Returns dict with stdout, stderr, and exit_code.
        """
        if not self._is_allowed(command):
            msg = f"Command not in allowlist: '{command.split()[0]}'"
            logger.warning(msg)
            return {"stdout": "", "stderr": msg, "exit_code": "-1"}

        logger.info(f"Running command: {command}")
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE if capture else None,
                stderr=asyncio.subprocess.PIPE if capture else None,
                cwd=cwd,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return {
                    "stdout": "",
                    "stderr": f"Command timed out after {timeout}s",
                    "exit_code": "-1",
                }

            stdout = (stdout_b or b"").decode("utf-8", errors="replace")
            stderr = (stderr_b or b"").decode("utf-8", errors="replace")
            logger.debug(f"Command exit code: {proc.returncode}")
            return {
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": str(proc.returncode),
            }
        except Exception as e:
            logger.error(f"Command execution error: {e}")
            return {"stdout": "", "stderr": str(e), "exit_code": "-1"}

    async def launch_background(self, command: str, cwd: Optional[str] = None) -> Optional[int]:
        """Launch a process in the background and track its PID."""
        if not self._is_allowed(command):
            logger.warning(f"Background launch blocked: {command}")
            return None
        try:
            proc = subprocess.Popen(
                command,
                shell=True,
                cwd=cwd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._processes[proc.pid] = proc
            logger.info(f"Launched background process PID {proc.pid}: {command}")
            return proc.pid
        except Exception as e:
            logger.error(f"Background launch failed: {e}")
            return None

    def kill_process(self, pid: int) -> bool:
        """Kill a tracked background process."""
        proc = self._processes.get(pid)
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=5)
                del self._processes[pid]
                logger.info(f"Killed process PID {pid}")
                return True
            except Exception as e:
                logger.error(f"Failed to kill PID {pid}: {e}")
        return False

    def list_processes(self) -> List[Dict[str, str]]:
        """List all tracked background processes and their status."""
        result = []
        for pid, proc in list(self._processes.items()):
            status = "running" if proc.poll() is None else "terminated"
            result.append({"pid": str(pid), "status": status})
        return result

    def get_system_info(self) -> Dict[str, str]:
        """Return basic system resource information."""
        try:
            cpu = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            return {
                "cpu_percent": f"{cpu:.1f}%",
                "memory_used": f"{mem.used // (1024**2)} MB",
                "memory_total": f"{mem.total // (1024**2)} MB",
                "memory_percent": f"{mem.percent:.1f}%",
                "disk_used": f"{disk.used // (1024**3)} GB",
                "disk_total": f"{disk.total // (1024**3)} GB",
                "disk_percent": f"{disk.percent:.1f}%",
            }
        except Exception as e:
            return {"error": str(e)}

    def list_running_processes(self, limit: int = 50) -> List[Dict[str, str]]:
        """Return lightweight metadata for running processes."""
        processes = []
        try:
            for proc in psutil.process_iter(["pid", "name", "username", "exe"]):
                info = proc.info
                processes.append({
                    "pid": str(info.get("pid", "")),
                    "name": str(info.get("name") or ""),
                    "user": str(info.get("username") or ""),
                    "exe": str(info.get("exe") or ""),
                })
        except Exception as e:
            logger.error(f"Failed to list running processes: {e}")
        return processes[:max(1, int(limit))]

    def list_installed_executables(self, limit: int = 150) -> List[str]:
        """Scan common install directories and return executable paths."""
        candidates = []
        seen = set()
        search_roots = [
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        ]
        for root in search_roots:
            if not root or not Path(root).exists():
                continue
            try:
                for dirpath, _, filenames in os.walk(root):
                    for filename in filenames:
                        if not filename.lower().endswith(".exe"):
                            continue
                        full_path = str(Path(dirpath) / filename)
                        if full_path in seen:
                            continue
                        seen.add(full_path)
                        candidates.append(full_path)
                        if len(candidates) >= max(1, int(limit)):
                            return candidates
            except Exception as e:
                logger.warning(f"Executable scan skipped for {root}: {e}")
        return candidates

    def map_computer(self, process_limit: int = 50, executable_limit: int = 150) -> Dict[str, object]:
        """Build a compact machine map for perception and planning."""
        return {
            "system_info": self.get_system_info(),
            "running_processes": self.list_running_processes(limit=process_limit),
            "installed_executables": self.list_installed_executables(limit=executable_limit),
        }
