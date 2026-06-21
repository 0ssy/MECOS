"""
MECOS MCP Client
Connects to MCP (Model Context Protocol) servers for extended tool capabilities.
"""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from loguru import logger


MCP_CONFIG_PATH = Path("data/mcp_servers.json")


def get_recommended_mcp_servers() -> Dict[str, Dict[str, Any]]:
    """Recommended MCP servers for MECOS."""
    return {
        "github": {
            "description": "Repository operations, issue management, PR creation",
            "command": ["npx", "-y", "@modelcontextprotocol/server-github"],
            "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"},
            "enabled": True,
        },
        "sqlite": {
            "description": "Structured data storage for app schemas and logs",
            "command": ["npx", "-y", "@modelcontextprotocol/server-sqlite", "--db-path", "data/mecos.db"],
            "env": {},
            "enabled": True,
        },
        "brave-search": {
            "description": "Web search via Brave API",
            "command": ["npx", "-y", "@modelcontextprotocol/server-brave-search"],
            "env": {"BRAVE_API_KEY": "${BRAVE_API_KEY}"},
            "enabled": True,
        },
        "memory": {
            "description": "Persistent vector storage across sessions",
            "command": ["npx", "-y", "@modelcontextprotocol/server-memory"],
            "env": {},
            "enabled": True,
        },
        "sequential-thinking": {
            "description": "Enhanced reasoning chains for complex problems",
            "command": ["npx", "-y", "@modelcontextprotocol/server-sequential-thinking"],
            "env": {},
            "enabled": True,
        },
        "filesystem": {
            "description": "Enhanced file operations",
            "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem", "--root-dir", "."],
            "env": {},
            "enabled": True,
        },
        "time": {
            "description": "Timezone-aware scheduling and time operations",
            "command": ["npx", "-y", "@modelcontextprotocol/server-time"],
            "env": {},
            "enabled": True,
        },
        "fetch": {
            "description": "Web content extraction",
            "command": ["npx", "-y", "@modelcontextprotocol/server-fetch"],
            "env": {},
            "enabled": True,
        },
    }


class MCPClient:
    """Manages MCP server connections and tool registration."""

    def __init__(self, registry):
        self.registry = registry
        self._processes: Dict[str, subprocess.Popen] = {}
        self._configs = self._load_or_create_config()

    def _load_or_create_config(self) -> Dict[str, Dict[str, Any]]:
        """Load MCP server configuration or create default."""
        if MCP_CONFIG_PATH.exists():
            with open(MCP_CONFIG_PATH) as f:
                return json.load(f)
        
        MCP_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        configs = get_recommended_mcp_servers()
        with open(MCP_CONFIG_PATH, "w") as f:
            json.dump(configs, f, indent=2)
        return configs

    async def start_server(self, server_name: str) -> bool:
        """Start an MCP server process."""
        if server_name not in self._configs:
            logger.error(f"Unknown MCP server: {server_name}")
            return False

        config = self._configs[server_name]
        if not config.get("enabled", False):
            logger.info(f"MCP server {server_name} is disabled")
            return False

        if server_name in self._processes:
            return True

        try:
            cmd = config["command"].copy()
            # Resolve env variables
            env = {}
            for key, value in config.get("env", {}).items():
                if value.startswith("${") and value.endswith("}"):
                    env_key = value[2:-1]
                    env[key] = Path.cwd().parent.parent.parent / env_key  # placeholder
                else:
                    env[key] = value
            
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**subprocess.os.environ, **env},
            )
            self._processes[server_name] = proc
            logger.info(f"Started MCP server: {server_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to start MCP server {server_name}: {e}")
            return False

    async def discover_tools(self, server_name: str) -> List[str]:
        """Discover tools available from an MCP server."""
        # For simulation (actual MCP uses JSON-RPC)
        known_tools = {
            "github": ["github_create_repo", "github_create_issue", "github_list_issues", "github_create_pull_request"],
            "sqlite": ["sqlite_query", "sqlite_execute", "sqlite_tables"],
            "brave-search": ["brave_search", "brave_image_search"],
            "memory": ["memory_store", "memory_retrieve", "memory_search"],
            "sequential-thinking": ["sequential_think", "think_step"],
            "filesystem": ["fs_read", "fs_write", "fs_list", "fs_search"],
            "time": ["time_now", "time_in_timezone", "time_format"],
            "fetch": ["fetch_url", "fetch_extract_text"],
        }
        return known_tools.get(server_name, [])

    async def register_server_tools(self, server_name: str) -> int:
        """Register all tools from an MCP server."""
        config = self._configs.get(server_name, {})
        
        # Try to start actual MCP server, fallback to simulation
        try:
            if not await self.start_server(server_name):
                logger.warning(f"MCP server {server_name} not available, using simulated tools")
        except Exception as e:
            logger.debug(f"MCP server {server_name} start failed: {e}")
        
        tools = await self.discover_tools(server_name)
        from tool_registry import ToolSpec, ToolPermission
        
        for tool_name in tools:
            # Determine permissions based on tool category
            perms = ToolPermission()
            if server_name in ("github",):
                perms.can_access_network = True
            elif server_name in ("sqlite",):
                perms.can_write_files = True
            elif server_name in ("filesystem", "fetch", "time", "brave-search"):
                perms.can_access_network = True
            elif server_name in ("memory", "sequential-thinking"):
                perms.can_execute_code = True
            
            spec = ToolSpec(
                name=f"mcp_{server_name}_{tool_name}",
                description=f"[{server_name}] {tool_name}: {config.get('description', '')}",
                func=self._make_mcp_call(server_name, tool_name),
                parameters={"input": "Tool input"},
                permissions=perms,
                category="mcp",
                is_mcp_tool=True,
                mcp_server=server_name,
            )
            self.registry.register(spec)
        
        logger.info(f"Registered {len(tools)} tools from MCP server: {server_name}")
        return len(tools)

    def _make_mcp_call(self, server_name: str, tool_name: str):
        """Create a callable for MCP tool execution."""
        async def call(**kwargs):
            result = await self.call_tool(server_name, tool_name, kwargs)
            return result.get("result", {"status": "ok"})
        return call

    async def call_tool(self, server_name: str, tool_name: str, args: dict) -> dict:
        """Execute a tool on an MCP server."""
        # Placeholder - actual implementation uses JSON-RPC over stdin/stdout
        return {"result": {"status": "mcp_simulated", "tool": f"{server_name}/{tool_name}"}}

    def stop_all(self):
        """Stop all MCP server processes."""
        for name, proc in self._processes.items():
            try:
                proc.terminate()
                logger.info(f"Stopped MCP server: {name}")
            except Exception:
                pass