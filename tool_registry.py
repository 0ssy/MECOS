"""
MECOS Phase 4 - Tool Registry
Dynamic tool discovery, registration, capability introspection, and permission management.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Callable, Any, Optional, List, Dict
from loguru import logger


@dataclass
class ToolPermission:
    """Defines what a tool is allowed to do."""
    can_write_files: bool = False
    can_execute_code: bool = False
    can_access_network: bool = False
    can_launch_apps: bool = False
    requires_confirmation: bool = False
    allowed_paths: List[str] = field(default_factory=list)


@dataclass
class ToolSpec:
    """Full specification for a registered tool."""
    name: str
    description: str
    func: Callable
    parameters: Dict[str, str]  # param_name -> description
    permissions: ToolPermission = field(default_factory=ToolPermission)
    version: str = "1.0.0"
    category: str = "general"
    enabled: bool = True


class ToolRegistry:
    """
    Central registry for all MECOS tools.
    Supports dynamic registration, introspection, and permission management.
    """

    def __init__(self):
        self._tools: Dict[str, ToolSpec] = {}
        logger.info("ToolRegistry initialized.")

    def register(self, spec: ToolSpec):
        """Register a tool with full specification."""
        self._tools[spec.name] = spec
        logger.info(f"Tool registered: [{spec.category}] {spec.name} v{spec.version}")

    def unregister(self, name: str):
        """Remove a tool from the registry."""
        if name in self._tools:
            del self._tools[name]
            logger.info(f"Tool unregistered: {name}")

    def get(self, name: str) -> Optional[ToolSpec]:
        """Retrieve a tool specification by name."""
        return self._tools.get(name)

    def list_tools(self, category: Optional[str] = None) -> List[ToolSpec]:
        """List all registered tools, optionally filtered by category."""
        tools = [t for t in self._tools.values() if t.enabled]
        if category:
            tools = [t for t in tools if t.category == category]
        return tools

    def describe_all(self) -> str:
        """Return a human-readable description of all available tools."""
        lines = []
        for spec in self.list_tools():
            params = ", ".join(f"{k}: {v}" for k, v in spec.parameters.items())
            lines.append(f"- {spec.name}({params}): {spec.description}")
        return "\n".join(lines)

    def enable(self, name: str):
        if name in self._tools:
            self._tools[name].enabled = True

    def disable(self, name: str):
        if name in self._tools:
            self._tools[name].enabled = False
            logger.warning(f"Tool disabled: {name}")

    def check_permission(self, name: str, action: str) -> bool:
        """Check if a tool has permission for a given action type."""
        spec = self.get(name)
        if not spec:
            return False
        perm = spec.permissions
        mapping = {
            "write_files": perm.can_write_files,
            "execute_code": perm.can_execute_code,
            "access_network": perm.can_access_network,
            "launch_apps": perm.can_launch_apps,
        }
        return mapping.get(action, False)
