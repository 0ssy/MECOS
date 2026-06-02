from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import requests
from loguru import logger

try:
    import yfinance as yf
except ModuleNotFoundError:
    yf = None


class EventsCalendar:
    """Earnings and macro events collector with safe fallbacks."""

    def __init__(self):
        self.timeout_seconds = 10

    def earnings_dates(self, tickers: List[str]) -> Dict[str, Any]:
        if yf is None:
            return {
                "available": False,
                "error": "yfinance_not_installed",
                "events": [],
            }
        events: List[Dict[str, str]] = []
        for ticker in tickers:
            symbol = str(ticker or "").strip().upper()
            if not symbol:
                continue
            try:
                cal = yf.Ticker(symbol).calendar
                if cal is None or getattr(cal, "empty", True):
                    continue
                date_value = cal.iloc[0].get("Earnings Date")
                if date_value is None:
                    continue
                events.append({"ticker": symbol, "earnings_date": str(date_value)})
            except Exception as exc:
                logger.debug(f"Earnings fetch failed for {symbol}: {exc}")
        return {
            "available": True,
            "events": sorted(events, key=lambda e: e["earnings_date"]),
        }

    def economic_events(self) -> Dict[str, Any]:
        start = datetime.now(timezone.utc)
        end = start + timedelta(days=7)
        url = "https://calendar.fxstreet.com/eventdate/api/v1"
        params = {
            "f": start.strftime("%Y-%m-%dT%H:%M:%S"),
            "t": end.strftime("%Y-%m-%dT%H:%M:%S"),
            "impact": "high",
        }
        try:
            resp = requests.get(url, params=params, timeout=self.timeout_seconds)
            if not resp.ok:
                return {"available": True, "events": [], "error": f"http_{resp.status_code}"}
            payload = resp.json()
            if not isinstance(payload, list):
                return {"available": True, "events": []}
            return {"available": True, "events": payload}
        except Exception as exc:
            return {"available": True, "events": [], "error": str(exc)}
