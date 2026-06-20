"""
Agent-Reach Bridge Tools
Registers the Agent-Reach multi-platform system as MECOS ToolRegistry tools.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger

from agent_reach_bridge import AgentReachBridge, get_bridge


def get_agent_reach_tools(memory_system=None) -> List[Dict[str, Any]]:
    """Return a list of MECOS ToolSpec-style dicts for Agent-Reach tools."""
    bridge = get_bridge(memory_system)
    return [
        {
            "name": "agent_reach_read_url",
            "description": "Read any URL using the best available platform channel (Twitter, Reddit, YouTube, GitHub, Bilibili, XiaoHongShu, etc.) via Agent-Reach.",
            "func": bridge.read_url,
            "parameters": {
                "url": "The URL to read/extract content from"
            },
            "permissions": {
                "can_write_files": False,
                "can_execute_code": False,
                "can_access_network": True,
                "can_launch_apps": False,
                "requires_confirmation": False,
                "allowed_paths": [],
            },
            "category": "web_perception",
            "enabled": True,
        },
        {
            "name": "agent_reach_health_check",
            "description": "Run a health check across all Agent-Reach channels and return their status.",
            "func": bridge.initialize,
            "parameters": {},
            "permissions": {
                "can_write_files": False,
                "can_execute_code": False,
                "can_access_network": True,
                "can_launch_apps": False,
                "requires_confirmation": False,
                "allowed_paths": [],
            },
            "category": "diagnostics",
            "enabled": True,
        },
        {
            "name": "agent_reach_list_channels",
            "description": "List all supported Agent-Reach platforms with descriptions and example URLs.",
            "func": bridge.get_available_channels,
            "parameters": {},
            "permissions": {
                "can_write_files": False,
                "can_execute_code": False,
                "can_access_network": False,
                "can_launch_apps": False,
                "requires_confirmation": False,
                "allowed_paths": [],
            },
            "category": "diagnostics",
            "enabled": True,
        },
        {
            "name": "agent_reach_read_jina",
            "description": "Read any URL via Jina Reader (fallback web channel, zero API key needed).",
            "func": _read_via_jina,
            "parameters": {
                "url": "The URL to read via Jina Reader"
            },
            "permissions": {
                "can_write_files": False,
                "can_execute_code": False,
                "can_access_network": True,
                "can_launch_apps": False,
                "requires_confirmation": False,
                "allowed_paths": [],
            },
            "category": "web_perception",
            "enabled": True,
        },
        {
            "name": "agent_reach_crawl",
            "description": "Crawl web pages starting from seed URLs and ingest discovered content.",
            "func": bridge.crawl_web,
            "parameters": {
                "seed_urls": "List of starting URLs",
                "max_pages": "Maximum pages to visit (default: 10)",
                "max_depth": "Maximum crawl depth (default: 1)",
                "same_domain_only": "Stay within initial domains (default: True)",
            },
            "permissions": {
                "can_write_files": False,
                "can_execute_code": False,
                "can_access_network": True,
                "can_launch_apps": False,
                "requires_confirmation": True,
                "allowed_paths": [],
            },
            "category": "web_perception",
            "enabled": True,
        },
    ]


async def _read_via_jina(url: str) -> Dict[str, Any]:
    from agent_reach.channels.web import WebChannel
    channel = WebChannel()
    try:
        text = channel.read(url)
        return {
            "url": url,
            "text": text,
            "links": [],
            "ok": True,
            "error": "",
            "channel_used": "jina_reader",
        }
    except Exception as e:
        return {
            "url": url,
            "text": "",
            "links": [],
            "ok": False,
            "error": str(e),
            "channel_used": "jina_reader",
        }


def register_agent_reach_tools(tool_registry, memory_system=None) -> int:
    """Register all Agent-Reach tools into a MECOS ToolRegistry instance.

    Returns the number of tools registered.
    """
    if tool_registry is None:
        logger.warning("ToolRegistry is None; cannot register Agent-Reach tools")
        return 0

    tool_specs = get_agent_reach_tools(memory_system)
    registered = 0
    for spec in tool_specs:
        try:
            from tool_registry import ToolSpec, ToolPermission
            perm = ToolPermission(
                can_write_files=spec["permissions"].get("can_write_files", False),
                can_execute_code=spec["permissions"].get("can_execute_code", False),
                can_access_network=spec["permissions"].get("can_access_network", False),
                can_launch_apps=spec["permissions"].get("can_launch_apps", False),
                requires_confirmation=spec["permissions"].get("requires_confirmation", False),
                allowed_paths=spec["permissions"].get("allowed_paths", []),
            )
            tool_spec = ToolSpec(
                name=spec["name"],
                description=spec["description"],
                func=spec["func"],
                parameters=spec["parameters"],
                permissions=perm,
                category=spec.get("category", "web_perception"),
                enabled=spec.get("enabled", True),
            )
            tool_registry.register(tool_spec)
            registered += 1
        except Exception as e:
            logger.error(f"Failed to register Agent-Reach tool '{spec['name']}': {e}")
    logger.success(f"Registered {registered} Agent-Reach tools")
    return registered
