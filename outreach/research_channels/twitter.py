"""
MECOS Outreach - Twitter Research Adapter
Searches and extracts tweets for lead research.
"""
from __future__ import annotations

import asyncio
import subprocess
import urllib.parse
from typing import Any, Dict, List

from loguru import logger

from .base import DEFAULT_TIMEOUT, jina_read_fallback


async def research_twitter(query: str, max_results: int = 3,
                           timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """Search Twitter for recent content related to query.
    
    Returns dict with: ok, text, error, link, source.
    Uses twitter-cli/OpenCLI if available, falls back to Jina Reader.
    """
    try:
        from agent_reach.channels import TwitterChannel
        channel = TwitterChannel()
        status, msg = channel.check()
    except Exception:
        return {"ok": False, "text": "", "error": "backend_unavailable", "source": "twitter"}

    if status in ("off", "error", "warn"):
        try:
            search_url = f"https://x.com/search?q={urllib.parse.quote(query)}&f=live"
            fallback = await asyncio.to_thread(
                jina_read_fallback, search_url, timeout
            )
            if fallback.get("ok"):
                return {
                    "ok": True, "text": fallback["text"],
                    "link": f"https://x.com/search?q={query}", "source": "twitter_jina"
                }
            return {
                "ok": False, "text": fallback.get("text", ""),
                "error": fallback.get("error", "jina_fallback_failed"), "source": "twitter"
            }
        except Exception as e:
            return {"ok": False, "text": "", "error": str(e), "source": "twitter"}

    try:
        search_url = f"https://x.com/search?q={urllib.parse.quote(query)}&f=live"
        if channel.active_backend == "twitter-cli":
            cmd = ["twitter", "search", query, "--limit", str(max_results)]
            result = await asyncio.to_thread(_run_sync, cmd, timeout=timeout)
            if result.get("ok"):
                return {
                    "ok": True, "text": result.get("stdout", ""),
                    "link": search_url, "source": "twitter-cli"
                }
        elif channel.active_backend == "OpenCLI":
            cmd = ["opencli", "twitter", "search", "--q", query,
                   "--limit", str(max_results)]
            result = await asyncio.to_thread(_run_sync, cmd, timeout=timeout)
            if result.get("ok"):
                return {
                    "ok": True, "text": result.get("stdout", ""),
                    "link": search_url, "source": "opencli"
                }
        elif channel.active_backend and "bird" in str(channel.active_backend):
            cmd = ["bird", "search", query, "--limit", str(max_results)]
            result = await asyncio.to_thread(_run_sync, cmd, timeout=timeout)
            if result.get("ok"):
                return {
                    "ok": True, "text": result.get("stdout", ""),
                    "link": search_url, "source": "bird"
                }
    except Exception as exc:
        logger.debug("Twitter research failed: {}", exc)

    search_url = f"https://x.com/search?q={urllib.parse.quote(query)}&f=live"
    fallback = await asyncio.to_thread(jina_read_fallback, search_url, timeout)
    if fallback.get("ok"):
        return {
            "ok": True, "text": fallback["text"],
            "link": f"https://x.com/search?q={query}", "source": "twitter_jina"
        }
    return {
        "ok": False, "text": "",
        "error": fallback.get("error", "all_backends_failed"), "source": "twitter"
    }


def _run_sync(cmd: List[str], timeout: int = 10) -> Dict[str, Any]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {"ok": r.returncode == 0, "stdout": r.stdout, "stderr": r.stderr}
    except FileNotFoundError:
        return {"ok": False, "error": f"Command not found: {cmd[0]}"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Timeout after {timeout}s"}
    except Exception as e:
        return {"ok": False, "error": str(e)}