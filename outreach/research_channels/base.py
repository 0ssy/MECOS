"""
MECOS Outreach - Research Channels Base
Shared types and constants for research adapters.
"""
from __future__ import annotations

import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class ResearchResult:
    """Result from a research platform query."""
    ok: bool
    text: str
    error: str = ""
    link: str = ""
    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "text": self.text,
            "error": self.error,
            "link": self.link,
            "source": self.source,
        }


DEFAULT_TIMEOUT = 10


def jina_read_fallback(url: str, timeout: int = 15) -> Dict[str, Any]:
    """Fallback to Jina Reader when platform channel unavailable."""
    try:
        encoded = urllib.parse.quote(url, safe=":/")
        req = urllib.request.Request(
            f"https://r.jina.ai/{encoded}",
            headers={"Accept": "text/plain", "User-Agent": "MECOS-AgentReach/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
        text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
        text = re.sub(r"\[.*?\]\(.*?\)", "", text)
        return {"ok": True, "text": text[:10000], "source": "jina_reader"}
    except Exception as e:
        return {"ok": False, "text": "", "error": str(e), "source": "jina_reader"}