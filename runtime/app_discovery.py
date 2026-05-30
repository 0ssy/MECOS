from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import json
import logging
import os
import platform
import subprocess

logger = logging.getLogger(__name__)


@dataclass
class AppCapability:
    name: str
    description: str
    api_type: str
    endpoints: List[str] = field(default_factory=list)
    success_rate: float = 0.0


@dataclass
class DiscoveredApp:
    name: str
    path: str
    type: str
    capabilities: List[AppCapability] = field(default_factory=list)
    discovered_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class LearnedWorkflow:
    app_name: str
    task_description: str
    steps: List[str] = field(default_factory=list)
    success_rate: float = 0.0
    execution_count: int = 0
    last_executed: Optional[str] = None


class AppDiscovery:
    def __init__(self, cache_dir: str = "data/app_discovery"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.discovered_apps: Dict[str, DiscoveredApp] = {}
        self.system_type = platform.system()

    def scan_installed_apps(self) -> Dict[str, DiscoveredApp]:
        if self.system_type == "Windows":
            apps = self._scan_windows()
        elif self.system_type == "Darwin":
            apps = self._scan_macos()
        elif self.system_type == "Linux":
            apps = self._scan_linux()
        else:
            apps = {}
        self.discovered_apps = apps
        return apps

    def _scan_windows(self) -> Dict[str, DiscoveredApp]:
        roots = [
            Path("C:\\Program Files"),
            Path("C:\\Program Files (x86)"),
            Path(os.path.expandvars("%APPDATA%")),
        ]
        apps: Dict[str, DiscoveredApp] = {}
        for root in roots:
            if not root.exists():
                continue
            try:
                for app_dir in root.iterdir():
                    if not app_dir.is_dir():
                        continue
                    app_name = app_dir.name
                    apps[app_name] = DiscoveredApp(
                        name=app_name,
                        path=str(app_dir),
                        type=self._classify_app(app_name),
                        capabilities=self._detect_capabilities(app_name),
                    )
            except OSError:
                continue
        return apps

    def _scan_macos(self) -> Dict[str, DiscoveredApp]:
        apps: Dict[str, DiscoveredApp] = {}
        root = Path("/Applications")
        if not root.exists():
            return apps
        for app_path in root.glob("*.app"):
            app_name = app_path.stem
            apps[app_name] = DiscoveredApp(
                name=app_name,
                path=str(app_path),
                type=self._classify_app(app_name),
                capabilities=self._detect_capabilities(app_name),
            )
        return apps

    def _scan_linux(self) -> Dict[str, DiscoveredApp]:
        apps: Dict[str, DiscoveredApp] = {}
        try:
            if Path("/usr/bin/dpkg").exists():
                result = subprocess.run(
                    ["dpkg", "-l"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                for line in result.stdout.splitlines():
                    if not line.startswith("ii"):
                        continue
                    parts = line.split()
                    if len(parts) < 2:
                        continue
                    app_name = parts[1]
                    apps[app_name] = DiscoveredApp(
                        name=app_name,
                        path=f"/usr/bin/{app_name}",
                        type=self._classify_app(app_name),
                        capabilities=self._detect_capabilities(app_name),
                    )
        except Exception as exc:
            logger.warning(f"Linux app scan failed: {exc}")
        return apps

    def _classify_app(self, app_name: str) -> str:
        lowered = app_name.lower()
        if any(word in lowered for word in ("excel", "word", "powerpoint", "outlook")):
            return "office"
        if any(word in lowered for word in ("photoshop", "blender", "figma", "illustrator", "sketch")):
            return "design"
        if any(word in lowered for word in ("vscode", "visual studio", "pycharm", "xcode", "git")):
            return "dev"
        if any(word in lowered for word in ("tableau", "power bi", "jupyter", "sql", "postgres")):
            return "data"
        if any(word in lowered for word in ("slack", "discord", "teams", "zoom", "telegram")):
            return "communication"
        return "other"

    def _detect_capabilities(self, app_name: str) -> List[AppCapability]:
        known_capabilities: Dict[str, List[AppCapability]] = {
            "Blender": [
                AppCapability(
                    name="Blender MCP",
                    description="3D modeling and rendering via Python API",
                    api_type="mcp",
                    endpoints=["create_scene", "render", "export"],
                )
            ],
            "Slack": [
                AppCapability(
                    name="Slack REST API",
                    description="Messaging and notifications",
                    api_type="rest",
                    endpoints=["send_message", "create_channel", "list_users"],
                )
            ],
            "Discord": [
                AppCapability(
                    name="Discord REST API",
                    description="Messaging and notifications",
                    api_type="rest",
                    endpoints=["send_message", "create_channel", "list_users"],
                )
            ],
        }
        return known_capabilities.get(app_name, [])

    def save_discovery(self, filepath: Optional[str] = None) -> str:
        output = Path(filepath) if filepath else (self.cache_dir / "discovered_apps.json")
        payload = {
            "timestamp": datetime.now().isoformat(),
            "system": self.system_type,
            "apps": {
                name: {
                    "name": app.name,
                    "path": app.path,
                    "type": app.type,
                    "capabilities": [
                        {
                            "name": cap.name,
                            "description": cap.description,
                            "api_type": cap.api_type,
                            "endpoints": cap.endpoints,
                        }
                        for cap in app.capabilities
                    ],
                    "discovered_at": app.discovered_at,
                }
                for name, app in self.discovered_apps.items()
            },
        }
        with open(output, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        return str(output)


class AppLearner:
    def __init__(self, memory_dir: str = "data/app_workflows"):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.learned_workflows: Dict[str, LearnedWorkflow] = {}

    def record_workflow(
        self,
        app_name: str,
        task_description: str,
        steps: List[str],
        success: bool = True,
    ) -> LearnedWorkflow:
        key = f"{app_name}:{task_description}"
        workflow = self.learned_workflows.get(key)
        if workflow is None:
            workflow = LearnedWorkflow(
                app_name=app_name,
                task_description=task_description,
                steps=list(steps),
                success_rate=1.0 if success else 0.0,
                execution_count=1,
                last_executed=datetime.now().isoformat(),
            )
            self.learned_workflows[key] = workflow
            return workflow

        workflow.execution_count += 1
        workflow.success_rate = (
            ((workflow.success_rate * (workflow.execution_count - 1)) + (1.0 if success else 0.0))
            / workflow.execution_count
        )
        workflow.last_executed = datetime.now().isoformat()
        return workflow

    def save_workflows(self, filepath: Optional[str] = None) -> str:
        output = Path(filepath) if filepath else (self.memory_dir / "workflows.json")
        payload = {
            "timestamp": datetime.now().isoformat(),
            "workflows": {
                key: {
                    "app_name": item.app_name,
                    "task_description": item.task_description,
                    "steps": item.steps,
                    "success_rate": item.success_rate,
                    "execution_count": item.execution_count,
                    "last_executed": item.last_executed,
                }
                for key, item in self.learned_workflows.items()
            },
        }
        with open(output, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        return str(output)
