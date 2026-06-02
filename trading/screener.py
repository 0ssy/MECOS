from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List

from loguru import logger

try:
    import yfinance as yf
except ModuleNotFoundError:
    yf = None


class StockScreener:
    """Basic fundamentals screener with value/growth/momentum presets."""

    PRESETS = {
        "value": {"pe_max": 18.0, "pb_max": 2.0, "roe_min": 0.10},
        "growth": {"revenue_growth_min": 0.15, "eps_growth_min": 0.10},
        "momentum": {"beta_min": 0.8},
    }

    def __init__(self, max_workers: int = 8):
        self.max_workers = max_workers

    def screen(self, tickers: List[str], strategy: str = "value") -> Dict[str, Any]:
        if yf is None:
            return {"available": False, "error": "yfinance_not_installed", "results": []}

        preset = self.PRESETS.get(strategy, self.PRESETS["value"])
        results: List[Dict[str, Any]] = []

        def check(symbol: str) -> None:
            ticker = str(symbol or "").strip().upper()
            if not ticker:
                return
            try:
                info = yf.Ticker(ticker).info or {}
            except Exception as exc:
                logger.debug(f"Screener fetch failed for {ticker}: {exc}")
                return

            row = {
                "ticker": ticker,
                "name": info.get("shortName", ticker),
                "pe": float(info.get("trailingPE") or 999.0),
                "pb": float(info.get("priceToBook") or 999.0),
                "roe": float(info.get("returnOnEquity") or 0.0),
                "revenue_growth": float(info.get("revenueGrowth") or 0.0),
                "eps_growth": float(info.get("earningsGrowth") or 0.0),
                "beta": float(info.get("beta") or 0.0),
            }

            ok = True
            if strategy == "value":
                ok = row["pe"] <= preset["pe_max"] and row["pb"] <= preset["pb_max"] and row["roe"] >= preset["roe_min"]
            elif strategy == "growth":
                ok = row["revenue_growth"] >= preset["revenue_growth_min"] and row["eps_growth"] >= preset["eps_growth_min"]
            elif strategy == "momentum":
                ok = row["beta"] >= preset["beta_min"]
            if ok:
                results.append(row)

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            for symbol in tickers:
                pool.submit(check, symbol)

        if strategy == "value":
            results.sort(key=lambda r: r["pe"])
        elif strategy == "growth":
            results.sort(key=lambda r: (r["revenue_growth"] + r["eps_growth"]), reverse=True)
        else:
            results.sort(key=lambda r: r["beta"], reverse=True)

        return {"available": True, "strategy": strategy, "results": results}
