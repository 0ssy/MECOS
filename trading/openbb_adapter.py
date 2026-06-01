from __future__ import annotations

from typing import Any, Dict, List

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

    @staticmethod
    def _obb() -> Any:
        return getattr(openbb, "obb", None) if openbb is not None else None

    @staticmethod
    def _to_dict(data: Any) -> Dict[str, Any]:
        if data is None:
            return {}
        if hasattr(data, "to_dataframe"):
            try:
                frame = data.to_dataframe()
                if hasattr(frame, "to_dict"):
                    return frame.to_dict()
            except Exception:
                pass
        if hasattr(data, "to_dict"):
            try:
                return data.to_dict()
            except TypeError:
                return data.to_dict(orient="records")
        if isinstance(data, dict):
            return data
        return {"data": data}

    @staticmethod
    def _headline_rows(data: Any) -> List[Dict[str, Any]]:
        if data is None:
            return []
        if hasattr(data, "to_dataframe"):
            try:
                frame = data.to_dataframe()
                return frame.to_dict(orient="records")
            except Exception:
                return []
        if hasattr(data, "to_dict"):
            try:
                maybe = data.to_dict(orient="records")
                if isinstance(maybe, list):
                    return [row for row in maybe if isinstance(row, dict)]
            except TypeError:
                maybe = data.to_dict()
                if isinstance(maybe, dict):
                    return [maybe]
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
        if isinstance(data, dict):
            return [data]
        return []

    def get_market_data(self, symbol: str) -> Dict[str, Any]:
        if openbb is None:
            raise RuntimeError("OpenBB SDK is not installed; cannot fetch market data.")
        obb = self._obb()
        if self._is_forex_symbol(symbol):
            return self.get_forex_data(symbol)
        if obb is not None and hasattr(obb, "equity") and hasattr(obb.equity, "price"):
            data = obb.equity.price.historical(symbol=symbol)
            return self._to_dict(data)
        data = openbb.equity.price.get_historical(symbol)
        return self._to_dict(data)

    def get_forex_data(self, symbol: str) -> Dict[str, Any]:
        if openbb is None:
            raise RuntimeError("OpenBB SDK is not installed; cannot fetch forex data.")
        base, quote = self._normalize_forex_symbol(symbol)
        obb = self._obb()
        attempts = [
            lambda: obb.forex.price.historical(symbol=f"{base}/{quote}") if obb is not None else None,
            lambda: obb.forex.price.historical(symbol=f"{base}{quote}") if obb is not None else None,
            lambda: openbb.forex.price.get_historical(f"{base}{quote}"),
            lambda: openbb.forex.price.get_historical(f"{base}/{quote}"),
            lambda: openbb.forex.price.historical(f"{base}/{quote}"),
            lambda: openbb.forex.historical(f"{base}/{quote}"),
        ]
        last_error: Exception | None = None
        for fetch in attempts:
            try:
                result = fetch()
                if result is None:
                    continue
                return self._to_dict(result)
            except Exception as exc:
                last_error = exc
                continue
        raise RuntimeError(f"OpenBB forex data fetch failed for {base}/{quote}: {last_error}")

    def get_macro_data(self, indicator: str) -> Dict[str, Any]:
        if openbb is None:
            raise RuntimeError("OpenBB SDK is not installed; cannot fetch macro data.")
        obb = self._obb()
        if obb is not None and hasattr(obb, "economy") and hasattr(obb.economy, "fred_series"):
            return self._to_dict(obb.economy.fred_series(series_id=indicator))
        return self._to_dict(openbb.economy.fred.get_series(indicator))

    def get_news(self, symbol: str, limit: int = 5) -> List[Dict[str, Any]]:
        if openbb is None:
            raise RuntimeError("OpenBB SDK is not installed; cannot fetch news data.")
        obb = self._obb()
        attempts = [
            lambda: obb.news.company(symbol=symbol, limit=limit) if obb is not None else None,
            lambda: obb.news.company(symbol=symbol) if obb is not None else None,
            lambda: openbb.news.company(symbol=symbol, limit=limit),
            lambda: openbb.news.company(symbol),
        ]
        last_error: Exception | None = None
        for fetch in attempts:
            try:
                result = fetch()
                if result is None:
                    continue
                rows = self._headline_rows(result)
                if rows:
                    return rows[:limit]
            except Exception as exc:
                last_error = exc
                continue
        raise RuntimeError(f"OpenBB news data fetch failed for {symbol}: {last_error}")

    def safe_get_market_data(self, symbol: str) -> Dict[str, Any]:
        if not self.available:
            return {"symbol": symbol, "available": False, "error": "openbb_not_installed"}
        try:
            return {"symbol": symbol, "available": True, "data": self.get_market_data(symbol)}
        except Exception as exc:
            logger.warning(f"OpenBB market data fetch failed for {symbol}: {exc}")
            return {"symbol": symbol, "available": True, "error": str(exc)}

    def safe_get_news(self, symbol: str, limit: int = 5) -> Dict[str, Any]:
        if not self.available:
            return {"symbol": symbol, "available": False, "error": "openbb_not_installed", "data": []}
        try:
            return {"symbol": symbol, "available": True, "data": self.get_news(symbol=symbol, limit=limit)}
        except Exception as exc:
            logger.warning(f"OpenBB news fetch failed for {symbol}: {exc}")
            return {"symbol": symbol, "available": True, "error": str(exc), "data": []}

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
