from __future__ import annotations

import time
from typing import Any, Dict

from loguru import logger
import pandas as pd
import pandas_datareader.data as web


class MacroDataProvider:
    """Fetches macro indicators from free sources with TTL cache."""

    def __init__(self, ttl_seconds: int = 3600):
        self.ttl_seconds = int(max(ttl_seconds, 60))
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._warned: set[str] = set()

    def _warn_once(self, key: str, message: str) -> None:
        if key in self._warned:
            return
        self._warned.add(key)
        logger.warning(message)

    def _read_cache(self, key: str) -> Dict[str, Any] | None:
        row = self._cache.get(key)
        if not row:
            return None
        if (time.time() - float(row.get("ts", 0.0))) > float(self.ttl_seconds):
            return None
        return row.get("value")

    def _write_cache(self, key: str, value: Dict[str, Any]) -> Dict[str, Any]:
        self._cache[key] = {"ts": time.time(), "value": value}
        return value

    @staticmethod
    def _latest_float(frame: Any) -> float:
        if frame is None or getattr(frame, "empty", True):
            return 0.0
        value = frame.iloc[-1, 0]
        try:
            return float(value)
        except Exception:
            return 0.0

    @staticmethod
    def _pct_change(frame: Any) -> float:
        if frame is None or getattr(frame, "empty", True):
            return 0.0
        series = frame.iloc[:, 0]
        if len(series) < 2:
            return 0.0
        prev = float(series.iloc[-2]) if float(series.iloc[-2]) != 0 else 0.0
        curr = float(series.iloc[-1])
        if prev == 0.0:
            return 0.0
        return (curr / prev) - 1.0

    def get_macro_snapshot(self, asset_type: str = "equity") -> Dict[str, Any]:
        key = f"macro:{str(asset_type).strip().lower()}"
        cached = self._read_cache(key)
        if cached is not None:
            return cached

        try:
            fed_funds = self._fetch_fred("FEDFUNDS")
            cpi = self._fetch_fred("CPIAUCSL")
            unemployment = self._fetch_fred("UNRATE")
            gdp = self._fetch_fred("GDP")
        except Exception as exc:
            payload = {
                "available": True,
                "risk_regime": "neutral",
                "risk_score": 0.0,
                "error": str(exc),
            }
            self._warn_once("macro-fetch", f"MacroDataProvider fetch failed: {exc}")
            return self._write_cache(key, payload)

        fed_val = self._latest_float(fed_funds)
        cpi_val = self._latest_float(cpi)
        unrate_val = self._latest_float(unemployment)
        gdp_val = self._latest_float(gdp)
        cpi_mom = self._pct_change(cpi)
        gdp_qoq = self._pct_change(gdp)

        score = 0.0
        if fed_val <= 4.0:
            score += 0.25
        else:
            score -= 0.20
        if cpi_mom <= 0.003:
            score += 0.20
        else:
            score -= 0.15
        if unrate_val <= 5.0:
            score += 0.15
        else:
            score -= 0.20
        if gdp_qoq >= 0.0:
            score += 0.20
        else:
            score -= 0.25

        risk_regime = "neutral"
        if score >= 0.20:
            risk_regime = "risk_on"
        elif score <= -0.20:
            risk_regime = "risk_off"

        payload = {
            "available": True,
            "asset_type": str(asset_type),
            "risk_regime": risk_regime,
            "risk_score": float(score),
            "fed_funds": fed_val,
            "cpi": cpi_val,
            "cpi_mom": cpi_mom,
            "unemployment": unrate_val,
            "gdp": gdp_val,
            "gdp_qoq": gdp_qoq,
        }
        return self._write_cache(key, payload)

    @staticmethod
    def _fetch_fred(series_id: str) -> Any:
        try:
            return web.DataReader(series_id, "fred")
        except Exception:
            return MacroDataProvider._fetch_fred_csv(series_id)

    @staticmethod
    def _fetch_fred_csv(series_id: str) -> Any:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        frame = pd.read_csv(url)
        if frame.empty or "VALUE" not in frame.columns:
            raise RuntimeError(f"FRED series unavailable: {series_id}")
        cleaned = frame[["DATE", "VALUE"]].copy()
        cleaned["VALUE"] = pd.to_numeric(cleaned["VALUE"], errors="coerce")
        cleaned = cleaned.dropna(subset=["VALUE"])
        if cleaned.empty:
            raise RuntimeError(f"FRED series empty: {series_id}")
        return cleaned.set_index("DATE")
