"""
MECOS Phase 4 - Tool Registry
Dynamic tool discovery, registration, capability introspection, and permission management.
Includes MCP server integration and enhanced permission model.
"""

import asyncio
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
from loguru import logger


@dataclass
class ToolPermission:
    """Defines what a tool is allowed to do with path-based constraints."""
    can_write_files: bool = False
    can_execute_code: bool = False
    can_access_network: bool = False
    can_launch_apps: bool = False
    requires_confirmation: bool = False
    allowed_paths: List[str] = field(default_factory=list)
    denied_paths: List[str] = field(default_factory=list)
    rate_limit_per_minute: int = 60

    def check_path_allowed(self, path: str) -> bool:
        """Check if a path is allowed with regex support."""
        from pathlib import Path
        resolved = str(Path(path).resolve())
        
        # Check denial list first
        for denied in self.denied_paths:
            if self._path_matches(denied, resolved):
                return False
        
        # If allowed list is empty, all paths are allowed (with sandboxing)
        if not self.allowed_paths:
            return True
        
        # Check if path matches any allowed pattern
        for allowed in self.allowed_paths:
            if self._path_matches(allowed, resolved):
                return True
        return False
    
    def _path_matches(self, pattern: str, path: str) -> bool:
        """Match path against pattern (supports regex)."""
        try:
            return bool(re.search(pattern, path, re.IGNORECASE))
        except re.error:
            return pattern.lower() in path.lower()


@dataclass
class ToolSpec:
    """Full specification for a registered tool."""
    name: str
    description: str
    func: Callable
    parameters: Dict[str, str]
    permissions: ToolPermission = field(default_factory=ToolPermission)
    version: str = "1.0.0"
    category: str = "general"
    enabled: bool = True
    dependencies: List[str] = field(default_factory=list)
    source_module: str = ""
    is_mcp_tool: bool = False
    mcp_server: str = ""


class ToolRegistry:
    """
    Central registry for all MECOS tools.
    Supports dynamic registration, introspection, permission management, and MCP integration.
    """

    def __init__(self):
        self._tools: Dict[str, ToolSpec] = {}
        self._categories: Set[str] = set()
        self._mcp_tools: Dict[str, ToolSpec] = {}
        self._health_status: Dict[str, Dict[str, Any]] = {}
        logger.info("ToolRegistry initialized.")

    def register(self, spec: ToolSpec) -> None:
        """Register a tool with full specification."""
        self._tools[spec.name] = spec
        self._categories.add(spec.category)
        if spec.is_mcp_tool:
            self._mcp_tools[spec.name] = spec
        logger.info(f"Tool registered: [{spec.category}] {spec.name} v{spec.version}")

    def unregister(self, name: str) -> bool:
        """Remove a tool from the registry. Returns True if removed."""
        if name in self._tools:
            spec = self._tools.pop(name)
            if spec.is_mcp_tool and name in self._mcp_tools:
                del self._mcp_tools[name]
            logger.info(f"Tool unregistered: {name}")
            return True
        return False

    def get(self, name: str) -> Optional[ToolSpec]:
        """Retrieve a tool specification by name."""
        return self._tools.get(name)

    def list_tools(self, category: Optional[str] = None, enabled_only: bool = True) -> List[ToolSpec]:
        """List all registered tools, optionally filtered by category."""
        tools = [t for t in self._tools.values() if t.enabled or not enabled_only]
        if category:
            tools = [t for t in tools if t.category == category]
        return tools

    def describe_all(self) -> str:
        """Return a human-readable description of all available tools."""
        lines = []
        for spec in sorted(self.list_tools(), key=lambda t: (t.category, t.name)):
            params = ", ".join(f"{k}: {v}" for k, v in spec.parameters.items())
            mcp_tag = " [MCP]" if spec.is_mcp_tool else ""
            lines.append(f"- {spec.name}{mcp_tag}({params}): {spec.description}")
        return "\n".join(lines)

    def enable(self, name: str) -> bool:
        """Enable a tool. Returns True if successful."""
        if name in self._tools:
            self._tools[name].enabled = True
            return True
        return False

    def disable(self, name: str) -> bool:
        """Disable a tool. Returns True if successful."""
        if name in self._tools:
            self._tools[name].enabled = False
            logger.warning(f"Tool disabled: {name}")
            return True
        return False

    def check_permission(self, name: str, action: str, path: Optional[str] = None) -> bool:
        """Check if a tool has permission for a given action type and path."""
        spec = self.get(name)
        if not spec:
            return False
        perm = spec.permissions
        
        # Check path restrictions if provided
        if path and not perm.check_path_allowed(path):
            return False
        
        mapping = {
            "write_files": perm.can_write_files,
            "execute_code": perm.can_execute_code,
            "access_network": perm.can_access_network,
            "launch_apps": perm.can_launch_apps,
        }
        return mapping.get(action, False)

    async def register_mcp_tools(
        self,
        mcp_server_url: str,
        tool_names: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Register tools from an MCP server.
        Returns list of registered tool names.
        """
        import json
        try:
            # Simulate MCP tool discovery
            registered = []
            for name in tool_names or ["mcp_tool"]:
                spec = ToolSpec(
                    name=name,
                    description=f"Tool from MCP server {mcp_server_url}",
                    func=lambda *args, **kwargs: {"status": "mcp_call"},
                    parameters={"query": "Input query"},
                    permissions=ToolPermission(
                        can_access_network=True,
                        can_execute_code=False,
                    ),
                    category="mcp",
                    is_mcp_tool=True,
                    mcp_server=mcp_server_url,
                )
                self.register(spec)
                registered.append(name)
            logger.info(f"Registered {len(registered)} MCP tools from {mcp_server_url}")
            return registered
        except Exception as e:
            logger.error(f"MCP registration failed: {e}")
            return []

    def get_categories(self) -> List[str]:
        """Return all available tool categories."""
        return sorted(self._categories)

    def get_stats(self) -> Dict[str, Any]:
        """Return registry statistics."""
        enabled = sum(1 for t in self._tools.values() if t.enabled)
        return {
            "total_tools": len(self._tools),
            "enabled_tools": enabled,
            "disabled_tools": len(self._tools) - enabled,
            "categories": list(self._categories),
            "mcp_tools": len(self._mcp_tools),
        }

    def update_health(self, tool_name: str, status: str, message: str = "") -> None:
        """Update health status for a tool."""
        self._health_status[tool_name] = {
            "status": status,
            "message": message,
            "timestamp": asyncio.get_event_loop().time(),
        }

    def get_health(self, tool_name: str) -> Dict[str, Any]:
        """Get health status for a tool."""
        return self._health_status.get(tool_name, {"status": "unknown", "message": ""})

    def health_summary(self) -> Dict[str, Any]:
        """Return health summary for all tools."""
        return {
            "total": len(self._tools),
            "healthy": sum(1 for h in self._health_status.values() if h.get("status") == "ok"),
            "degraded": sum(1 for h in self._health_status.values() if h.get("status") == "warn"),
            "failed": sum(1 for h in self._health_status.values() if h.get("status") == "error"),
        }