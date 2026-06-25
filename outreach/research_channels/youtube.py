"""
MECOS Outreach - YouTube Research Adapter
Searches and extracts video transcripts for lead research.
"""
from __future__ import annotations

import asyncio
import tempfile
import urllib.parse
from typing import Any, Dict, List

from loguru import logger

from .base import DEFAULT_TIMEOUT, jina_read_fallback


async def research_youtube(query: str, max_results: int = 3,
                          timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """Search YouTube for recent videos related to query.
    
    Returns dict with: ok, text, error, link, source.
    Uses yt-dlp if available, falls back to Jina Reader.
    """
    try:
        from agent_reach.channels import YouTubeChannel
        channel = YouTubeChannel()
        status, msg = channel.check()
    except Exception:
        return {"ok": False, "text": "", "error": "backend_unavailable", "source": "youtube"}

    if status in ("off", "error", "warn"):
        try:
            search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
            fallback = await asyncio.to_thread(
                jina_read_fallback, search_url, timeout
            )
            if fallback.get("ok"):
                return {
                    "ok": True, "text": fallback["text"],
                    "link": search_url, "source": "youtube_jina"
                }
            return {
                "ok": False, "text": fallback.get("text", ""),
                "error": fallback.get("error", "jina_fallback_failed"), "source": "youtube"
            }
        except Exception as e:
            return {"ok": False, "text": "", "error": str(e), "source": "youtube"}

    try:
        search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
        if channel.active_backend == "yt-dlp":
            with tempfile.TemporaryDirectory() as tmpdir:
                cmd = [
                    "yt-dlp",
                    "--print", "%(title)s\n%(description)s\n%(channel)s",
                    "--no-warnings", "--ignore-errors",
                    "--skip-download",
                    "-o", f"{tmpdir}/%(id)s.%(ext)s",
                    search_url,
                ]
                result = await asyncio.to_thread(_run_sync, cmd, timeout=timeout)
                if result.get("ok") and result.get("stdout"):
                    return {
                        "ok": True, "text": result["stdout"],
                        "link": search_url, "source": "yt-dlp"
                    }
    except Exception as exc:
        logger.debug("YouTube research failed: {}", exc)

    search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
    fallback = await asyncio.to_thread(jina_read_fallback, search_url, timeout)
    if fallback.get("ok"):
        return {
            "ok": True, "text": fallback["text"],
            "link": search_url, "source": "youtube_jina"
        }
    return {
        "ok": False, "text": "",
        "error": fallback.get("error", "all_backends_failed"), "source": "youtube"
    }


def _run_sync(cmd: List[str], timeout: int = 10) -> Dict[str, Any]:
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