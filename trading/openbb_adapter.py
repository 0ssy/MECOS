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
        if self._is_forex_symbol(symbol):
            return self.get_forex_data(symbol)
        data = openbb.equity.price.get_historical(symbol)
        return data.to_dict()

    def get_forex_data(self, symbol: str) -> Dict[str, Any]:
        if openbb is None:
            raise RuntimeError("OpenBB SDK is not installed; cannot fetch forex data.")
        base, quote = self._normalize_forex_symbol(symbol)
        attempts = [
            lambda: openbb.forex.price.get_historical(f"{base}{quote}"),
            lambda: openbb.forex.price.get_historical(f"{base}/{quote}"),
            lambda: openbb.forex.price.historical(f"{base}/{quote}"),
            lambda: openbb.forex.historical(f"{base}/{quote}"),
        ]
        last_error: Exception | None = None
        for fetch in attempts:
            try:
                result = fetch()
                if hasattr(result, "to_dict"):
                    return result.to_dict()
                if isinstance(result, dict):
                    return result
                return {"data": result}
            except Exception as exc:
                last_error = exc
                continue
        raise RuntimeError(f"OpenBB forex data fetch failed for {base}/{quote}: {last_error}")

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

    @staticmethod
    def _is_forex_symbol(symbol: str) -> bool:
        token = str(symbol or "").strip().upper()
        if "/" in token:
            left, right = token.split("/", 1)
            return len(left) == 3 and len(right) == 3 and left.isalpha() and right.isalpha()
        return len(token) == 6 and token.isalpha()

    @staticmethod
    def _normalize_forex_symbol(symbol: str) -> tuple[str, str]:
        token = str(symbol or "").strip().upper()
        if "/" in token:
            left, right = token.split("/", 1)
            return left, right
        return token[:3], token[3:]
