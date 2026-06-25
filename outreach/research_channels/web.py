"""
MECOS Outreach - Web Research Adapter
General web search and content extraction for lead research.
Uses AgentReachBridge.Jina Reader fallback as primary method.
"""
from __future__ import annotations

import urllib.parse
from typing import Any, Dict

from loguru import logger


async def research_web(query: str, max_results: int = 3,
                      timeout: int = 10) -> Dict[str, Any]:
    """Search the open web for content related to query.
    
    Returns dict with: ok, text, error, link, source.
    Uses Jina Reader via AgentReachBridge for extraction.
    """
    try:
        from agent_reach_bridge import AgentReachBridge
        bridge = AgentReachBridge()
        if bridge.healthy_web_channel():
            search_url = f"https://duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            result = await bridge.read_url(search_url)
            if result.get("ok"):
                return {
                    "ok": True, "text": result.get("text", ""),
                    "link": search_url, "source": "web_jina"
                }
            return {
                "ok": False, "text": "",
                "error": result.get("error", "web_fetch_failed"), "source": "web"
            }
    except Exception as exc:
        logger.debug("Web research failed: {}", exc)

    return {"ok": False, "text": "", "error": "backend_unavailable", "source": "web"}