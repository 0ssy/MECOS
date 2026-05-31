from __future__ import annotations

from typing import Any, Dict

from loguru import logger

try:
    import openbb  # type: ignore
except ModuleNotFoundError:
    openbb = None


class OpenBBDataAdapter:
    """Optional external data adapter powered by OpenBB SDK."""

    @property
    def available(self) -> bool:
        return openbb is not None

    def get_market_data(self, symbol: str) -> Dict[str, Any]:
        if openbb is None:
            raise RuntimeError("OpenBB SDK is not installed; cannot fetch market data.")
        data = openbb.equity.price.get_historical(symbol)
        return data.to_dict()

    def get_macro_data(self, indicator: str) -> Dict[str, Any]:
        if openbb is None:
            raise RuntimeError("OpenBB SDK is not installed; cannot fetch macro data.")
        return openbb.economy.fred.get_series(indicator).to_dict()

    def safe_get_market_data(self, symbol: str) -> Dict[str, Any]:
        if not self.available:
            return {"symbol": symbol, "available": False, "error": "openbb_not_installed"}
        try:
            return {"symbol": symbol, "available": True, "data": self.get_market_data(symbol)}
        except Exception as exc:
            logger.warning(f"OpenBB market data fetch failed for {symbol}: {exc}")
            return {"symbol": symbol, "available": True, "error": str(exc)}
