from __future__ import annotations

from typing import Any, Dict, List

from loguru import logger

try:
    import feedparser
except ModuleNotFoundError:
    feedparser = None


class NewsSentimentEngine:
    FEEDS = [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "https://feeds.feedburner.com/Investingcom",
    ]

    BULLISH_WORDS = {
        "rally",
        "surge",
        "beat",
        "growth",
        "gain",
        "upgrade",
        "bullish",
        "strong",
        "record",
    }
    BEARISH_WORDS = {
        "drop",
        "crash",
        "miss",
        "loss",
        "downgrade",
        "bearish",
        "risk",
        "weak",
        "selloff",
    }

    def __init__(self):
        self._warned_feedparser = False

    @staticmethod
    def _symbol_tokens(symbol: str) -> List[str]:
        token = str(symbol or "").strip().upper()
        if "/" in token:
            left, right = token.split("/", 1)
            return [token, left, right]
        if "-" in token:
            left, right = token.split("-", 1)
            return [token, left, right]
        return [token]

    def _score_text(self, text: str) -> float:
        words = {w.strip(".,:;!?()[]{}\"'").lower() for w in text.split() if w}
        pos = len(words.intersection(self.BULLISH_WORDS))
        neg = len(words.intersection(self.BEARISH_WORDS))
        if pos == 0 and neg == 0:
            return 0.0
        raw = float(pos - neg) / 5.0
        return max(-1.0, min(1.0, raw))

    def analyze_symbol(self, symbol: str, limit: int = 10) -> Dict[str, Any]:
        if feedparser is None:
            if not self._warned_feedparser:
                logger.warning("NewsSentimentEngine disabled: feedparser is not installed.")
                self._warned_feedparser = True
            return {
                "available": False,
                "symbol": symbol,
                "sentiment_score": 0.0,
                "sentiment_label": "NEUTRAL",
                "headlines": [],
                "error": "feedparser_not_installed",
            }

        symbol_keys = [s.lower() for s in self._symbol_tokens(symbol)]
        matches: List[Dict[str, str]] = []
        scores: List[float] = []

        for url in self.FEEDS:
            parsed = feedparser.parse(url)
            entries = getattr(parsed, "entries", []) or []
            for entry in entries:
                title = str(getattr(entry, "title", "") or "")
                summary = str(getattr(entry, "summary", "") or "")
                content = f"{title} {summary}".lower()
                if symbol_keys and not any(k and k in content for k in symbol_keys):
                    continue
                score = self._score_text(f"{title} {summary}")
                matches.append(
                    {
                        "title": title,
                        "summary": summary[:280],
                        "link": str(getattr(entry, "link", "") or ""),
                    }
                )
                scores.append(score)
                if len(matches) >= limit:
                    break
            if len(matches) >= limit:
                break

        avg_score = float(sum(scores) / len(scores)) if scores else 0.0
        label = "NEUTRAL"
        if avg_score >= 0.2:
            label = "BULLISH"
        elif avg_score <= -0.2:
            label = "BEARISH"

        return {
            "available": True,
            "symbol": symbol,
            "sentiment_score": avg_score,
            "sentiment_label": label,
            "matching_headlines": len(matches),
            "headlines": matches,
        }
