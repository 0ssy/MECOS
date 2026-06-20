"""
MECOS Agent-Reach Integration Bridge
Wraps Agent-Reach channels as MECOS tools for multi-platform web perception.
Provides URL routing, channel health checks, data extraction, and MemorySystem integration.
"""

from __future__ import annotations

import asyncio
import importlib
import logging
from typing import Any, Dict, List, Optional

from loguru import logger

try:
    from agent_reach.channels import get_channel, get_all_channels
    from agent_reach.channels.base import Channel
except ImportError:
    logger.warning("agent_reach package not available; Agent-Reach integration disabled.")
    get_channel = None  # type: ignore
    get_all_channels = None  # type: ignore
    Channel = None  # type: ignore


class AgentReachBridge:
    """MECOS bridge to Agent-Reach multi-platform channel system.

    Routes URLs to the correct Agent-Reach channel, executes data extraction,
    and stores results in MECOS MemorySystem.
    """

    def __init__(self, memory_system=None):
        self.memory = memory_system
        self._all_channels: List[Channel] = []
        self._initialized = False

    async def initialize(self) -> Dict[str, Dict[str, str]]:
        """Initialize all channels and return health check results."""
        if get_all_channels is None:
            logger.warning("Agent-Reach not installed; returning empty channel map.")
            return {}
        self._all_channels = get_all_channels()
        self._initialized = True
        results = {}
        for ch in self._all_channels:
            try:
                status, msg = ch.check(config=None)
                results[ch.name] = {
                    "status": status,
                    "message": msg,
                    "active_backend": ch.active_backend or "N/A",
                    "tier": ch.tier,
                    "description": ch.description,
                }
            except Exception as e:
                results[ch.name] = {
                    "status": "error",
                    "message": str(e),
                    "active_backend": "N/A",
                    "tier": ch.tier,
                    "description": ch.description,
                }
        logger.info(f"AgentReachBridge initialized: {len(results)} channels probed")
        return results

    def route_url(self, url: str) -> Optional[Channel]:
        """Find the best channel to handle a given URL."""
        if not self._initialized:
            self._all_channels = get_all_channels() if get_all_channels else []
            self._initialized = True
        for ch in self._all_channels:
            try:
                if ch.can_handle(url):
                    return ch
            except Exception:
                continue
        return None

    async def read_url(self, url: str) -> Dict[str, Any]:
        """Read content from any URL using the appropriate Agent-Reach channel.

        Returns dict with: url, text, links, ok, error, channel_used
        """
        channel = self.route_url(url)
        if not channel:
            if self.healthy_web_channel():
                try:
                    text = await asyncio.to_thread(self._jina_read, url)
                    result = {
                        "url": url,
                        "text": text,
                        "links": [],
                        "ok": True,
                        "error": "",
                        "channel_used": "web (Jina Reader)",
                    }
                except Exception as e:
                    result = {
                        "url": url,
                        "text": "",
                        "links": [],
                        "ok": False,
                        "error": str(e),
                        "channel_used": "web (Jina Reader)",
                    }
            else:
                result = {
                    "url": url,
                    "text": "",
                    "links": [],
                    "ok": False,
                    "error": "No channel available for this URL",
                    "channel_used": "none",
                }
        else:
            ch_name = channel.name
            try:
                from agent_reach.channels.web import WebChannel
                if ch_name == "web":
                    text = await asyncio.to_thread(self._jina_read, url)
                    result = {
                        "url": url,
                        "text": text,
                        "links": [],
                        "ok": True,
                        "error": "",
                        "channel_used": ch_name,
                    }
                else:
                    result = {
                        "url": url,
                        "text": f"Channel {ch_name} available but requires specific extraction method",
                        "links": [],
                        "ok": False,
                        "error": "Platform-specific extraction not yet wrapped for MECOS",
                        "channel_used": ch_name,
                    }
            except Exception as e:
                result = {
                    "url": url,
                    "text": "",
                    "links": [],
                    "ok": False,
                    "error": f"Channel {ch_name} requires external tool setup: {e}",
                    "channel_used": ch_name,
                }
        if result.get("ok") and self.memory is not None:
            try:
                await self.memory.add_experience(
                    content=f"AGENT-REACH [{result.get('channel_used')}] ({url}):\n{result.get('text', '')[:5000]}",
                    source="agent_reach",
                )
            except Exception:
                pass
        return result

    @staticmethod
    def _jina_read(url: str) -> str:
        from agent_reach.channels.web import WebChannel
        return WebChannel().read(url)

    async def crawl_web(self, seed_urls: list, max_pages: int = 10, max_depth: int = 1, same_domain_only: bool = True) -> Dict[str, Any]:
        """Crawl URLs using the best available channel (delegates to web channel)."""
        from agent_reach.channels.web import WebChannel
        wc = WebChannel()
        return wc.read(url)

    def healthy_web_channel(self) -> bool:
        """Check if the fallback web channel is available."""
        channel = self.route_url("https://example.com")
        if channel and channel.name == "web":
            return True
        return False

    def get_available_channels(self) -> List[Dict[str, Any]]:
        """Return a list of all platforms with their capabilities."""
        if not self._initialized:
            self._all_channels = get_all_channels() if get_all_channels else []
            self._initialized = True
        return [
            {
                "name": ch.name,
                "description": ch.description,
                "backends": ch.backends,
                "tier": ch.tier,
                "can_handle_example": self._example_url(ch.name),
            }
            for ch in self._all_channels
        ]

    @staticmethod
    def _example_url(channel_name: str) -> str:
        examples = {
            "github": "https://github.com/user/repo",
            "twitter": "https://x.com/user/status/123",
            "youtube": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "reddit": "https://www.reddit.com/r/python/comments/abc123/",
            "bilibili": "https://www.bilibili.com/video/BV1xx411c7mD",
            "xiaohongshu": "https://www.xiaohongshu.com/explore/abc123",
            "linkedin": "https://www.linkedin.com/in/username/",
            "xiaoyuzhou": "https://www.xiaoyuzhoufm.com/episode/abc123",
            "xueqiu": "https://xueqiu.com/S/SH600519",
            "v2ex": "https://www.v2ex.com/t/123456",
            "rss": "https://example.com/feed",
            "exa_search": "search://query text",
            "web": "https://any-website.com/page",
        }
        return examples.get(channel_name, "")


_bridge_instance: Optional[AgentReachBridge] = None


def get_bridge(memory_system=None) -> AgentReachBridge:
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = AgentReachBridge(memory_system)
    return _bridge_instance
