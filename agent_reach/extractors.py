"""
Agent-Reach Platform Extraction
Wraps each platform's CLIs/APIs for real content extraction.
Only invoked after bridge.check() confirms backend availability.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False

from loguru import logger


# ── Helpers ────────────────────────────────────────────────────────────

def _check_probe(status, msg):
    if not status or status in ("off", "error"):
        return {"ok": False, "error": f"Backend not ready: {msg}", "source": "health_check"}
    return None  # means OK


def _run(cmd: list[str], timeout: int = 30) -> dict:
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace"
        )
        return {"ok": r.returncode == 0, "stdout": r.stdout, "stderr": r.stderr, "rc": r.returncode}
    except FileNotFoundError:
        return {"ok": False, "error": f"Command not found: {cmd[0]}"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Timeout after {timeout}s: {cmd[0]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _read_via_jina(url: str) -> dict:
    """Universal fallback: Jina Reader via urllib."""
    try:
        encoded = urllib.parse.quote(url, safe=":/")
        req = urllib.request.Request(
            f"https://r.jina.ai/{encoded}",
            headers={"Accept": "text/plain", "User-Agent": "MECOS/1.0"}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            text = resp.read().decode("utf-8", errors="replace")
        text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
        text = re.sub(r"\[.*?\]\(.*?\)", r"\1", text)
        return {"ok": True, "text": text[:15000], "source": "jina_reader"}
    except Exception as e:
        return {"ok": False, "error": f"Jina Reader failed: {e}", "source": "jina_reader"}


# ── GitHub ─────────────────────────────────────────────────────────────

async def read_github(channel, url: str) -> dict:
    status, msg = channel.check()
    blocker = _check_probe(status, msg)
    if blocker:
        return blocker

    text = ""
    try:
        if channel.active_backend == "gh CLI":
            parsed = urllib.parse.urlparse(url)
            parts = [p for p in parsed.path.strip("/").split("/") if p]
            owner, repo = parts[0], parts[1] if len(parts) > 1 else ""

            cmd = ["gh", "repo", "view", f"{owner}/{repo}", "--json", "name,description,url,defaultBranchRef,primaryLanguage,stargazerCount,forkCount"]
            probe = _run(cmd, timeout=15)
            if probe["ok"]:
                meta = json.loads(probe["stdout"]) if probe["stdout"] else {}
                text = f"# {meta.get('name', repo)}\n\n"
                if meta.get("description"):
                    text += f"**Description:** {meta['description']}\n\n"
                text += f"**Stars:** {meta.get('stargazerCount', '?')} | **Forks:** {meta.get('forkCount', '?')}\n"
                text += f"**Primary Language:** {meta.get('primaryLanguage', {}).get('name', '?')}\n"
                text += f"**URL:** {meta.get('url', url)}\n\n"

            readme_result = _run(["gh", "api", f"/repos/{owner}/{repo}/readme"], timeout=15)
            if readme_result.get("ok") and readme_result.get("stdout"):
                try:
                    rd = json.loads(readme_result["stdout"])
                    import base64
                    content = base64.b64decode(rd.get("content", "")).decode("utf-8", errors="replace")
                    text += f"\n## README\n\n{content[:8000]}"
                except Exception:
                    pass
    except Exception as exc:
        logger.warning("GitHub extractor failed: {}", exc)

    if not text:
        text = await asyncio.to_thread(_read_via_jina, url)
        if text.get("ok"):
            text = text.get("text", "")
    return {"ok": bool(text), "text": text, "source": "github"}


# ── Reddit ─────────────────────────────────────────────────────────────

async def read_reddit(channel, url: str) -> dict:
    status, msg = channel.check()
    blocker = _check_probe(status, msg)
    if blocker:
        return blocker

    output = ""
    source = "reddit"
    try:
        if channel.active_backend == "rdt-cli":
            result = _run(["rdt", "interact", "--url", url, "-o", "text", "-c"], timeout=20)
            if result["ok"]:
                output = result["stdout"]
                source = "rdt-cli"
        elif channel.active_backend in ("OpenCLI", "opencli"):
            result = _run(["opencli", "reddit", "read", "--url", url], timeout=20)
            if result["ok"]:
                output = result["stdout"]
                source = "opencli"
    except Exception as exc:
        logger.warning("Reddit extractor failed: {}", exc)

    if not output:
        fallback = await asyncio.to_thread(_read_via_jina, url)
        if fallback.get("ok"):
            output = fallback.get("text", "")
            source = "jina_reader"
    return {"ok": bool(output.strip()), "text": output.strip(), "source": source}


# ── Twitter / X ────────────────────────────────────────────────────────

async def read_twitter(channel, url: str) -> dict:
    status, msg = channel.check()
    blocker = _check_probe(status, msg)
    if blocker:
        return blocker

    output = ""
    source = "twitter"
    try:
        if channel.active_backend == "twitter-cli":
            tweet_id = urllib.parse.urlparse(url).path.strip("/").split("/")[-1]
            result = _run(["twitter", "article", tweet_id], timeout=20)
            if result["ok"]:
                output = result["stdout"]
                source = "twitter-cli"
        elif channel.active_backend == "OpenCLI":
            result = _run(["opencli", "twitter", "read", url], timeout=20)
            if result["ok"]:
                output = result["stdout"]
                source = "opencli"
        elif channel.active_backend and "bird" in channel.active_backend:
            result = _run(["bird", "read", url], timeout=20)
            if result["ok"]:
                output = result["stdout"]
                source = "bird"
    except Exception as exc:
        logger.warning("Twitter extractor failed: {}", exc)

    if not output:
        fallback = await asyncio.to_thread(_read_via_jina, url)
        if fallback.get("ok"):
            output = fallback.get("text", "")
            source = "jina_reader"
    return {"ok": bool(output.strip()), "text": output.strip(), "source": source}


# ── YouTube ────────────────────────────────────────────────────────────

async def read_youtube(channel, url: str) -> dict:
    status, msg = channel.check()
    blocker = _check_probe(status, msg)
    if blocker:
        return blocker

    output = ""
    source = "youtube"
    try:
        if channel.active_backend == "yt-dlp":
            with tempfile.TemporaryDirectory() as tmpdir:
                cmd = [
                    "yt-dlp",
                    "--print", "%(title)s\n%(description)s\n%(channel)s",
                    "--no-warnings", "--ignore-errors",
                    "--skip-download",
                    "-o", f"{tmpdir}/%(id)s.%(ext)s",
                    url,
                ]
                result = _run(cmd, timeout=30)
                if result["ok"] and result["stdout"]:
                    output = result["stdout"]
                    source = "yt-dlp"
    except Exception as exc:
        logger.warning("YouTube extractor failed: {}", exc)

    if not output:
        fallback = await asyncio.to_thread(_read_via_jina, url)
        if fallback.get("ok"):
            output = fallback.get("text", "")
            source = "jina_reader"
    return {"ok": bool(output.strip()), "text": output.strip(), "source": source}


# ── Bilibili ───────────────────────────────────────────────────────────

async def read_bilibili(channel, url: str) -> dict:
    status, msg = channel.check()
    blocker = _check_probe(status, msg)
    if blocker:
        return blocker

    output = ""
    source = "bilibili"
    try:
        if channel.active_backend in ("bili-cli", "OpenCLI"):
            cmd_name = channel.active_backend.lower().replace("-cli", "")
            result = _run([cmd_name, "read", url], timeout=20)
            if result["ok"]:
                output = result["stdout"]
                source = channel.active_backend
    except Exception as exc:
        logger.warning("Bilibili extractor failed: {}", exc)

    if not output:
        fallback = await asyncio.to_thread(_read_via_jina, url)
        if fallback.get("ok"):
            output = fallback.get("text", "")
            source = "jina_reader"
    return {"ok": bool(output.strip()), "text": output.strip(), "source": source}


# ── Xueqiu ─────────────────────────────────────────────────────────────

async def read_xueqiu(channel, url: str) -> dict:
    status, msg = channel.check()
    blocker = _check_probe(status, msg)
    if blocker:
        return blocker
    try:
        text = await asyncio.to_thread(channel.get_stock_quote, url)
        return {"ok": True, "text": str(text)[:5000], "source": "xueqiu_api"}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "source": "xueqiu_api"}


# ── V2EX ───────────────────────────────────────────────────────────────

async def read_v2ex(channel, url: str) -> dict:
    status, msg = channel.check()
    blocker = _check_probe(status, msg)
    if blocker:
        return blocker
    try:
        topic_id = urllib.parse.urlparse(url).path.strip("/").split("/")[-1]
        if topic_id.isdigit():
            data = channel.get_topic(int(topic_id))
            text = f"# {data.get('title', '')}\n\n{data.get('content', '')[:5000]}"
            return {"ok": True, "text": text, "source": "v2ex_api"}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "source": "v2ex_api"}
    return {"ok": False, "error": "Could not extract V2EX content", "source": "v2ex_api"}


# ── RSS ────────────────────────────────────────────────────────────────

def read_rss(url: str) -> dict:
    if not HAS_FEEDPARSER:
        return {"ok": False, "error": "feedparser not installed"}
    try:
        feed = feedparser.parse(url)
        entries = []
        for entry in feed.entries[:20]:
            entries.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
                "summary": (entry.get("summary", "") or "")[:500],
            })
        feed_title = feed.feed.get("title", url) if hasattr(feed, "feed") and feed.feed else url
        text_parts = [f"# {feed_title}\n"]
        for e in entries:
            text_parts.append(f"{e['title']}\n{e['published']}\n{e['summary']}\n")
        return {"ok": True, "text": "\n".join(text_parts), "entries": entries, "source": "rss"}
    except Exception as e:
        return {"ok": False, "error": str(e), "source": "rss"}
