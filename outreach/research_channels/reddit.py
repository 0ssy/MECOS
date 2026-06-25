"""
MECOS Outreach - Reddit Research Adapter
Searches and extracts subreddit posts for lead research.
"""
from __future__ import annotations

import asyncio
import urllib.parse
from typing import Any, Dict

from loguru import logger

from .base import DEFAULT_TIMEOUT, jina_read_fallback


async def research_reddit(query: str, max_results: int = 3,
                         timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """Search Reddit for recent posts related to query.
    
    Returns dict with: ok, text, error, link, source.
    Uses rdt-cli/OpenCLI if available, falls back to Jina Reader.
    """
    try:
        from agent_reach.channels import RedditChannel
        channel = RedditChannel()
        status, msg = channel.check()
    except Exception:
        return {"ok": False, "text": "", "error": "backend_unavailable", "source": "reddit"}

    if status in ("off", "error", "warn"):
        try:
            search_url = f"https://www.reddit.com/search/?q={urllib.parse.quote(query)}"
            fallback = await asyncio.to_thread(jina_read_fallback, search_url, timeout)
            if fallback.get("ok"):
                return {
                    "ok": True, "text": fallback["text"],
                    "link": search_url, "source": "reddit_jina"
                }
            return {
                "ok": False, "text": "",
                "error": fallback.get("error", "jina_fallback_failed"), "source": "reddit"
            }
        except Exception as e:
            return {"ok": False, "text": "", "error": str(e), "source": "reddit"}

    try:
        search_url = f"https://www.reddit.com/search/?q={urllib.parse.quote(query)}"
        if channel.active_backend == "rdt-cli":
            cmd = ["rdt", "search", query, "--limit", str(max_results)]
            result = await asyncio.to_thread(_run_sync, cmd, timeout=timeout)
            if result.get("ok"):
                return {
                    "ok": True, "text": result.get("stdout", ""),
                    "link": search_url, "source": "rdt-cli"
                }
        elif channel.active_backend in ("OpenCLI", "opencli"):
            cmd = ["opencli", "reddit", "search", "--q", query,
                   "--limit", str(max_results)]
            result = await asyncio.to_thread(_run_sync, cmd, timeout=timeout)
            if result.get("ok"):
                return {
                    "ok": True, "text": result.get("stdout", ""),
                    "link": search_url, "source": "opencli"
                }
    except Exception as exc:
        logger.debug("Reddit research failed: {}", exc)

    search_url = f"https://www.reddit.com/search/?q={urllib.parse.quote(query)}"
    fallback = await asyncio.to_thread(jina_read_fallback, search_url, timeout)
    if fallback.get("ok"):
        return {
            "ok": True, "text": fallback["text"],
            "link": search_url, "source": "reddit_jina"
        }
    return {
        "ok": False, "text": "",
        "error": fallback.get("error", "all_backends_failed"), "source": "reddit"
    }


def _run_sync(cmd: list, timeout: int = 10) -> Dict[str, Any]:
    import subprocess
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {"ok": r.returncode == 0, "stdout": r.stdout, "stderr": r.stderr}
    except FileNotFoundError:
        return {"ok": False, "error": f"Command not found: {cmd[0]}"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Timeout after {timeout}s"}
    except Exception as e:
        return {"ok": False, "error": str(e)}