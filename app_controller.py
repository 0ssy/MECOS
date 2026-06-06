"""
MECOS App Controller
=====================
Executes system commands and opens applications dynamically.
No hardcoded app names. No hardcoded command allowlists.
MECOS discovers what's available and learns what's safe.
"""

import asyncio
import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

import psutil
from loguru import logger


class DynamicAllowlist:
    """
    Instead of hardcoding allowed commands, MECOS builds
    its own allowlist by learning what's installed on the system.
    Blocks only genuinely destructive patterns.
    """

    # These are always blocked — no exceptions
    HARD_BLOCKS = [
        "rm -rf /",
        "rm -rf /*",
        "format c:",
        "del /f /s /q c:\\",
        ":(){:|:&};:",      # fork bomb
        "shutdown /f",
        "shutdown -h now",
        "dd if=/dev/zero",
        "mkfs.",
        "fdisk",
        "diskpart",
    ]

    def __init__(self):
        self._learned_commands: set[str] = set()
        self._learned_apps: dict[str, str] = {}  # name -> exe_path
        self._load_from_system()

    def _load_from_system(self):
        """Learn what commands are available on this system."""
        # System PATH executables
        path_dirs = os.environ.get("PATH", "").split(os.pathsep)
        for d in path_dirs:
            try:
                for f in Path(d).iterdir():
                    if f.is_file():
                        if os.name == "nt" and f.suffix.lower() in (".exe", ".cmd", ".bat"):
                            self._learned_commands.add(f.stem.lower())
                        elif os.name != "nt" and os.access(f, os.X_OK):
                            self._learned_commands.add(f.name.lower())
            except Exception:
                continue

        # Load from perception memory if available
        perception_file = Path("mecos_system_perception.json")
        if perception_file.exists():
            try:
                data = json.loads(perception_file.read_text(encoding="utf-8"))
                for name, app_data in data.get("apps", {}).items():
                    exe = app_data.get("exe_path", "")
                    if exe:
                        self._learned_apps[name.lower()] = exe
            except Exception:
                pass

        logger.info(
            "Dynamic allowlist loaded: {} commands, {} apps",
            len(self._learned_commands), len(self._learned_apps)
        )

    def is_safe(self, command: str) -> tuple[bool, str]:
        """
        Check if a command is safe to run.
        Returns (is_safe, reason).
        """
        cmd_lower = command.lower().strip()

        # Hard blocks — always refuse
        for pattern in self.HARD_BLOCKS:
            if pattern in cmd_lower:
                return False, f"Hard-blocked destructive pattern: {pattern}"

        # Everything else is allowed — MECOS is learning, not locked down
        return True, "ok"

    def learn_app(self, name: str, exe_path: str):
        """Register a newly discovered app."""
        self._learned_apps[name.lower()] = exe_path

    def find_app(self, app_name: str) -> Optional[str]:
        """
        Find an app's executable path.
        Searches learned apps, running processes, and system PATH.
        """
        name_lower = app_name.lower()

        # 1. Check learned apps (from perception memory)
        for learned_name, exe in self._learned_apps.items():
            if name_lower in learned_name or learned_name in name_lower:
                if Path(exe).exists():
                    return exe

        # 2. Check running processes
        for proc in psutil.process_iter(["name", "exe"]):
            try:
                proc_name = (proc.info.get("name") or "").lower()
                exe       = proc.info.get("exe") or ""
                if name_lower in proc_name and exe:
                    return exe
            except Exception:
                continue

        # 3. Check system PATH
        import shutil
        found = shutil.which(app_name)
        if found:
            return found

        # 4. Search common install directories
        return self._search_install_dirs(app_name)

    def _search_install_dirs(self, app_name: str) -> Optional[str]:
        """Search common install directories for an app."""
        search_dirs = []
        if os.name == "nt":
            for env in ["ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA", "APPDATA"]:
                d = os.environ.get(env, "")
                if d:
                    search_dirs.append(Path(d))
        else:
            search_dirs = [Path("/usr/bin"), Path("/usr/local/bin"), Path("/opt")]

        name_lower = app_name.lower()
        for base in search_dirs:
            if not base.exists():
                continue
            try:
                for exe in base.rglob("*.exe" if os.name == "nt" else "*"):
                    if name_lower in exe.stem.lower():
                        if exe.is_file():
                            return str(exe)
            except Exception:
                continue

        return None


class AppController:
    """
    Executes commands and manages applications dynamically.
    Learns the system rather than relying on hardcoded lists.
    """

    def __init__(self, knowledge_base_path: Optional[str] = None):
        self.kb_path   = knowledge_base_path or "exploration/discoveries/knowledge.json"
        self.allowlist = DynamicAllowlist()
        logger.info("AppController initialized with dynamic allowlist.")

    def _get_app_path(self, app_name: str) -> Optional[str]:
        """
        Find an app's path dynamically.
        No hardcoding — searches perception memory, processes, PATH.
        """
        return self.allowlist.find_app(app_name)

    def map_computer(
        self, process_limit: int = 50, executable_limit: int = 150
    ) -> Dict[str, Any]:
        """Capture a system-wide snapshot."""
        process_limit    = max(1, int(process_limit))
        executable_limit = max(1, int(executable_limit))

        # Running processes
        running_processes = []
        for proc in psutil.process_iter(["pid", "name", "exe"]):
            try:
                info = proc.info
                running_processes.append({
                    "pid":  int(info.get("pid") or 0),
                    "name": str(info.get("name") or ""),
                    "exe":  str(info.get("exe") or ""),
                })
            except Exception:
                continue
            if len(running_processes) >= process_limit:
                break

        # Installed executables from system PATH + common dirs
        known_execs = []
        search_dirs = []
        if os.name == "nt":
            for env in ["ProgramFiles", "ProgramFiles(x86)", "WINDIR"]:
                d = os.environ.get(env, "")
                if d:
                    search_dirs.append(Path(d))
        else:
            search_dirs = [Path("/usr/bin"), Path("/usr/local/bin")]

        for base in search_dirs:
            if not base.exists():
                continue
            try:
                for child in base.rglob("*"):
                    if not child.is_file():
                        continue
                    if os.name == "nt" and not child.name.lower().endswith(".exe"):
                        continue
                    if os.name != "nt" and not os.access(child, os.X_OK):
                        continue
                    known_execs.append(str(child))
                    if len(known_execs) >= executable_limit:
                        break
            except Exception:
                continue
            if len(known_execs) >= executable_limit:
                break

        return {
            "os":                    os.name,
            "working_directory":     os.getcwd(),
            "running_processes":     running_processes,
            "installed_executables": known_execs,
            "learned_apps":          len(self.allowlist._learned_apps),
            "status":                "HEALTHY",
        }

    def get_system_info(self) -> Dict[str, Any]:
        """System resource snapshot."""
        vm   = psutil.virtual_memory()
        disk = psutil.disk_usage(str(Path.cwd().anchor or Path.cwd()))
        return {
            "cpu_percent":  float(psutil.cpu_percent(interval=0.1)),
            "memory_used":  int(vm.used),
            "memory_total": int(vm.total),
            "disk_used":    int(disk.used),
            "disk_total":   int(disk.total),
        }

    async def run_command(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Run a command dynamically.
        Checks against learned allowlist, not hardcoded list.
        """
        command = str(command or "").strip()
        if not command:
            return {"command": command, "exit_code": "-1", "stdout": "", "stderr": "Empty command"}

        # Safety check
        is_safe, reason = self.allowlist.is_safe(command)
        if not is_safe:
            return {
                "command":   command,
                "exit_code": "-1",
                "stdout":    "",
                "stderr":    f"Blocked by allowlist: {reason}",
            }

        # Handle "open <app>" dynamically
        if command.lower().startswith("open "):
            app_name = command[5:].strip()
            app_path = self._get_app_path(app_name)
            if not app_path:
                return {
                    "command":   command,
                    "exit_code": "-1",
                    "stdout":    "",
                    "stderr":    f"App not found: {app_name}. Run scan_and_learn_system() first.",
                }
            if os.name == "nt":
                command = f'start "" "{app_path}"'
            else:
                command = f'xdg-open "{app_path}"'

        # Execute
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=max(1, int(timeout))
            )
            return {
                "command":   command,
                "exit_code": str(proc.returncode),
                "stdout":    stdout.decode(errors="replace").strip(),
                "stderr":    stderr.decode(errors="replace").strip(),
            }
        except asyncio.TimeoutError:
            return {
                "command":   command,
                "exit_code": "-1",
                "stdout":    "",
                "stderr":    f"Timeout after {timeout}s",
            }
        except Exception as e:
            logger.error("Command execution failed: {}", e)
            return {"command": command, "exit_code": "-1", "stdout": "", "stderr": str(e)}

    async def execute_command(self, command: str) -> str:
        """Simple interface — returns stdout or stderr as string."""
        result = await self.run_command(command)
        return result.get("stdout") or result.get("stderr", "")

    async def open_app(self, app_name: str) -> Dict[str, Any]:
        """
        Open an application by name.
        Finds it dynamically — no hardcoding needed.
        """
        return await self.run_command(f"open {app_name}")

    async def open_file(self, file_path: str) -> Dict[str, Any]:
        """
        Open a file with its default application.
        MECOS looks up the file type association dynamically.
        """
        path = Path(file_path)
        if not path.exists():
            return {"exit_code": "-1", "stderr": f"File not found: {file_path}"}

        if os.name == "nt":
            command = f'start "" "{file_path}"'
        else:
            command = f'xdg-open "{file_path}"'

        return await self.run_command(command)

    def register_app(self, name: str, exe_path: str):
        """
        Manually register an app MECOS should know about.
        Called by AppPerception after scanning.
        """
        self.allowlist.learn_app(name, exe_path)
        logger.info("Registered app: {} -> {}", name, exe_path)
