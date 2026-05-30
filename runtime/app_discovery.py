"""
AppDiscovery & AppLearner — System Learning (MECOS v3.0 Phase 4)

Discovers installed applications, learns their capabilities and workflows,
and stores knowledge for future use. Implements Claude's cross-app integration.

Location: runtime/app_discovery.py
"""

import json
import subprocess
import os
import platform
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class AppCapability:
    """Represents an app's capability."""
    name: str
    description: str
    api_type: str  # "mcp", "rest", "python", "cli", "gui"
    endpoints: List[str] = field(default_factory=list)
    success_rate: float = 0.0


@dataclass
class DiscoveredApp:
    """Represents a discovered application."""
    name: str
    path: str
    type: str  # "office", "design", "dev", "data", "communication", "other"
    capabilities: List[AppCapability] = field(default_factory=list)
    discovered_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_used: Optional[str] = None
    usage_count: int = 0


@dataclass
class LearnedWorkflow:
    """Represents a learned workflow."""
    app_name: str
    task_description: str
    steps: List[str] = field(default_factory=list)
    success_rate: float = 0.0
    execution_count: int = 0
    last_executed: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


class AppDiscovery:
    """
    Discover installed applications and their capabilities.
    
    Responsibilities:
    - Scan system for installed apps
    - Detect available APIs (MCP, REST, Python, CLI)
    - Classify applications
    - Store discovery results
    """
    
    def __init__(self, cache_dir: str = "data/app_discovery"):
        """
        Initialize AppDiscovery.
        
        Args:
            cache_dir: Directory to cache discovery results
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.discovered_apps = {}
        self.system_type = platform.system()
        
        logger.info(f"AppDiscovery initialized (system: {self.system_type})")
    
    def scan_installed_apps(self) -> Dict[str, DiscoveredApp]:
        """
        Scan system for installed applications.
        
        Returns:
            Dictionary of {app_name: DiscoveredApp}
        """
        logger.info("Scanning for installed applications...")
        
        if self.system_type == "Darwin":  # macOS
            apps = self._scan_macos()
        elif self.system_type == "Windows":
            apps = self._scan_windows()
        elif self.system_type == "Linux":
            apps = self._scan_linux()
        else:
            logger.warning(f"Unsupported system: {self.system_type}")
            apps = {}
        
        self.discovered_apps = apps
        
        logger.info(f"Found {len(apps)} applications")
        
        return apps
    
    def _scan_macos(self) -> Dict[str, DiscoveredApp]:
        """Scan macOS for installed applications."""
        apps = {}
        
        app_dir = Path("/Applications")
        
        if app_dir.exists():
            for app_path in app_dir.glob("*.app"):
                app_name = app_path.stem
                
                app = DiscoveredApp(
                    name=app_name,
                    path=str(app_path),
                    type=self._classify_app(app_name),
                )
                
                # Detect capabilities
                app.capabilities = self._detect_capabilities(app_name, str(app_path))
                
                apps[app_name] = app
        
        return apps
    
    def _scan_windows(self) -> Dict[str, DiscoveredApp]:
        """Scan Windows for installed applications."""
        apps = {}
        
        # Common Windows app locations
        program_files = [
            Path("C:\\Program Files"),
            Path("C:\\Program Files (x86)"),
            Path(os.path.expandvars("%APPDATA%")),
        ]
        
        for program_dir in program_files:
            if program_dir.exists():
                for app_path in program_dir.iterdir():
                    if app_path.is_dir():
                        app_name = app_path.name
                        
                        app = DiscoveredApp(
                            name=app_name,
                            path=str(app_path),
                            type=self._classify_app(app_name),
                        )
                        
                        app.capabilities = self._detect_capabilities(app_name, str(app_path))
                        
                        apps[app_name] = app
        
        return apps
    
    def _scan_linux(self) -> Dict[str, DiscoveredApp]:
        """Scan Linux for installed applications."""
        apps = {}
        
        try:
            # Use dpkg or rpm to list installed packages
            if Path("/usr/bin/dpkg").exists():
                result = subprocess.run(
                    ["dpkg", "-l"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                
                for line in result.stdout.split("\n"):
                    if line.startswith("ii"):
                        parts = line.split()
                        if len(parts) >= 2:
                            app_name = parts[1]
                            
                            app = DiscoveredApp(
                                name=app_name,
                                path=f"/usr/bin/{app_name}",
                                type=self._classify_app(app_name),
                            )
                            
                            app.capabilities = self._detect_capabilities(app_name, "")
                            
                            apps[app_name] = app
        
        except Exception as e:
            logger.warning(f"Failed to scan Linux apps: {e}")
        
        return apps
    
    def _classify_app(self, app_name: str) -> str:
        """Classify application type."""
        app_lower = app_name.lower()
        
        office_keywords = ["excel", "word", "powerpoint", "outlook", "sheets", "docs"]
        design_keywords = ["photoshop", "blender", "figma", "illustrator", "sketch"]
        dev_keywords = ["vscode", "pycharm", "xcode", "visual studio", "git"]
        data_keywords = ["tableau", "power bi", "jupyter", "sql", "postgres"]
        comm_keywords = ["slack", "discord", "teams", "zoom", "telegram"]
        
        if any(kw in app_lower for kw in office_keywords):
            return "office"
        elif any(kw in app_lower for kw in design_keywords):
            return "design"
        elif any(kw in app_lower for kw in dev_keywords):
            return "dev"
        elif any(kw in app_lower for kw in data_keywords):
            return "data"
        elif any(kw in app_lower for kw in comm_keywords):
            return "communication"
        else:
            return "other"
    
    def _detect_capabilities(self, app_name: str, app_path: str) -> List[AppCapability]:
        """Detect available APIs for an application."""
        capabilities = []
        
        # Check for known MCP connectors
        mcp_apps = {
            "Blender": AppCapability(
                name="Blender MCP",
                description="3D modeling and rendering via Python API",
                api_type="mcp",
                endpoints=["create_scene", "render", "export"],
            ),
            "Excel": AppCapability(
                name="Excel MCP",
                description="Spreadsheet operations",
                api_type="mcp",
                endpoints=["read_cells", "write_cells", "create_chart"],
            ),
            "GitHub": AppCapability(
                name="GitHub MCP",
                description="Repository operations",
                api_type="mcp",
                endpoints=["list_repos", "create_issue", "push_code"],
            ),
        }
        
        if app_name in mcp_apps:
            capabilities.append(mcp_apps[app_name])
        
        # Check for REST APIs
        rest_apps = {
            "Slack": AppCapability(
                name="Slack REST API",
                description="Chat and notifications",
                api_type="rest",
                endpoints=["send_message", "create_channel", "list_users"],
            ),
            "Discord": AppCapability(
                name="Discord REST API",
                description="Chat and notifications",
                api_type="rest",
                endpoints=["send_message", "create_channel", "list_users"],
            ),
        }
        
        if app_name in rest_apps:
            capabilities.append(rest_apps[app_name])
        
        # Check for Python APIs
        python_apps = {
            "PostgreSQL": AppCapability(
                name="PostgreSQL Python API",
                description="Database operations",
                api_type="python",
                endpoints=["query", "insert", "update", "delete"],
            ),
            "MongoDB": AppCapability(
                name="MongoDB Python API",
                description="Document database operations",
                api_type="python",
                endpoints=["find", "insert", "update", "delete"],
            ),
        }
        
        if app_name in python_apps:
            capabilities.append(python_apps[app_name])
        
        return capabilities
    
    def save_discovery(self, filepath: str = None) -> None:
        """Save discovery results to file."""
        if filepath is None:
            filepath = self.cache_dir / "discovered_apps.json"
        
        data = {
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
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Discovery results saved to {filepath}")


class AppLearner:
    """
    Learn how to use discovered applications.
    
    Responsibilities:
    - Record successful workflows
    - Track success rates
    - Learn patterns and best practices
    - Store knowledge for reuse
    """
    
    def __init__(self, memory_dir: str = "data/app_workflows"):
        """
        Initialize AppLearner.
        
        Args:
            memory_dir: Directory to store learned workflows
        """
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        self.learned_workflows = {}
        
        logger.info(f"AppLearner initialized")
    
    def record_workflow(
        self,
        app_name: str,
        task_description: str,
        steps: List[str],
        success: bool = True,
    ) -> LearnedWorkflow:
        """
        Record a learned workflow.
        
        Args:
            app_name: Name of the application
            task_description: Description of the task
            steps: List of steps taken
            success: Whether the workflow succeeded
        
        Returns:
            LearnedWorkflow object
        """
        workflow_key = f"{app_name}:{task_description}"
        
        if workflow_key in self.learned_workflows:
            workflow = self.learned_workflows[workflow_key]
            workflow.execution_count += 1
            
            if success:
                workflow.success_rate = (
                    (workflow.success_rate * (workflow.execution_count - 1) + 1.0) /
                    workflow.execution_count
                )
            else:
                workflow.success_rate = (
                    (workflow.success_rate * (workflow.execution_count - 1) + 0.0) /
                    workflow.execution_count
                )
        else:
            workflow = LearnedWorkflow(
                app_name=app_name,
                task_description=task_description,
                steps=steps,
                success_rate=1.0 if success else 0.0,
                execution_count=1,
                last_executed=datetime.now().isoformat(),
            )
            
            self.learned_workflows[workflow_key] = workflow
        
        workflow.last_executed = datetime.now().isoformat()
        
        logger.info(
            f"Workflow recorded: {app_name} - {task_description} "
            f"(success_rate: {workflow.success_rate:.1%})"
        )
        
        return workflow
    
    def get_workflow(
        self,
        app_name: str,
        task_description: str,
    ) -> Optional[LearnedWorkflow]:
        """Get a learned workflow."""
        workflow_key = f"{app_name}:{task_description}"
        return self.learned_workflows.get(workflow_key)
    
    def get_best_workflows(self, app_name: str, top_n: int = 5) -> List[LearnedWorkflow]:
        """Get best workflows for an app."""
        app_workflows = [
            w for w in self.learned_workflows.values()
            if w.app_name == app_name
        ]
        
        return sorted(
            app_workflows,
            key=lambda w: w.success_rate,
            reverse=True,
        )[:top_n]
    
    def save_workflows(self, filepath: str = None) -> None:
        """Save learned workflows to file."""
        if filepath is None:
            filepath = self.memory_dir / "workflows.json"
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "workflows": {
                key: {
                    "app_name": w.app_name,
                    "task_description": w.task_description,
                    "steps": w.steps,
                    "success_rate": w.success_rate,
                    "execution_count": w.execution_count,
                    "last_executed": w.last_executed,
                }
                for key, w in self.learned_workflows.items()
            },
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Workflows saved to {filepath}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    # Example usage
    discovery = AppDiscovery()
    apps = discovery.scan_installed_apps()
    
    print(f"\nDiscovered {len(apps)} applications:")
    for app_name, app in list(apps.items())[:5]:
        print(f"\n  {app_name}")
        print(f"    Type: {app.type}")
        print(f"    Path: {app.path}")
        print(f"    Capabilities: {len(app.capabilities)}")
        for cap in app.capabilities:
            print(f"      - {cap.name} ({cap.api_type})")
    
    discovery.save_discovery()
    
    # Learn workflows
    learner = AppLearner()
    
    workflow = learner.record_workflow(
        app_name="Excel",
        task_description="Create daily P&L report",
        steps=[
            "Open Excel",
            "Create new workbook",
            "Add headers",
            "Insert data from database",
            "Create charts",
            "Save file",
        ],
        success=True,
    )
    
    print(f"\n\nLearned workflow:")
    print(f"  App: {workflow.app_name}")
    print(f"  Task: {workflow.task_description}")
    print(f"  Steps: {len(workflow.steps)}")
    print(f"  Success rate: {workflow.success_rate:.1%}")
    
    learner.save_workflows()
