from __future__ import annotations

import time
from typing import Any, Dict, List

from loguru import logger

try:
    import openbb  # type: ignore
except ModuleNotFoundError:
    openbb = None


class OpenBBDataAdapter:
    """Optional external data adapter powered by OpenBB SDK."""

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._warned_errors: set[str] = set()

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

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        return str(symbol or "").strip().upper()

    @staticmethod
    def _cache_key(kind: str, symbol: str, limit: int = 0) -> str:
        token = OpenBBDataAdapter._normalize_symbol(symbol)
        if limit:
            return f"{kind}:{token}:{limit}"
        return f"{kind}:{token}"

    def _read_cache(self, key: str, ttl_seconds: int) -> Dict[str, Any] | None:
        payload = self._cache.get(key)
        if not payload:
            return None
        ts = float(payload.get("ts", 0.0))
        if (time.time() - ts) > float(ttl_seconds):
            return None
        return payload.get("value")

    def _write_cache(self, key: str, value: Dict[str, Any]) -> None:
        self._cache[key] = {"ts": time.time(), "value": value}

    def _warn_once(self, key: str, message: str) -> None:
        if key in self._warned_errors:
            return
        self._warned_errors.add(key)
        logger.warning(message)

    def get_market_data(self, symbol: str) -> Dict[str, Any]:
        if openbb is None:
            raise RuntimeError("OpenBB SDK is not installed; cannot fetch market data.")
        obb = self._obb()
        if obb is None:
            raise RuntimeError("OpenBB App object unavailable.")
        if self._is_crypto_symbol(symbol):
            normalized = self._normalize_symbol(symbol)
            token = normalized.replace("/", "")
            data = obb.crypto.price.historical(symbol=token)
            return self._to_dict(data)
        if self._is_forex_symbol(symbol):
            return self.get_forex_data(symbol)
        if obb is not None and hasattr(obb, "equity") and hasattr(obb.equity, "price"):
            data = obb.equity.price.historical(symbol=symbol)
            return self._to_dict(data)
        raise RuntimeError("OpenBB equity price endpoint unavailable.")

    def get_forex_data(self, symbol: str) -> Dict[str, Any]:
        if openbb is None:
            raise RuntimeError("OpenBB SDK is not installed; cannot fetch forex data.")
        base, quote = self._normalize_forex_symbol(symbol)
        obb = self._obb()
        if obb is None or not hasattr(obb, "currency") or not hasattr(obb.currency, "price"):
            raise RuntimeError("OpenBB currency price endpoint unavailable.")
        attempts = [f"{base}/{quote}", f"{base}{quote}", f"{base}-{quote}"]
        last_error: Exception | None = None
        for instrument in attempts:
            try:
                result = obb.currency.price.historical(symbol=instrument)
                return self._to_dict(result)
            except Exception as exc:
                last_error = exc
        raise RuntimeError(f"OpenBB forex data fetch failed for {base}/{quote}: {last_error}")

    def get_macro_data(self, indicator: str) -> Dict[str, Any]:
        if openbb is None:
            raise RuntimeError("OpenBB SDK is not installed; cannot fetch macro data.")
        obb = self._obb()
        if obb is not None and hasattr(obb, "economy") and hasattr(obb.economy, "fred_series"):
            return self._to_dict(obb.economy.fred_series(symbol=indicator))
        raise RuntimeError("OpenBB economy.fred_series endpoint unavailable.")

    def safe_get_macro_data(self, indicator: str) -> Dict[str, Any]:
        cache_key = f"macro:{str(indicator).upper()}"
        cached = self._read_cache(cache_key, ttl_seconds=900)
        if cached is not None:
            return cached
        if not self.available:
            result = {"indicator": indicator, "available": False, "error": "openbb_not_installed"}
            self._write_cache(cache_key, result)
            return result
        try:
            result = {"indicator": indicator, "available": True, "data": self.get_macro_data(indicator)}
            self._write_cache(cache_key, result)
            return result
        except Exception as exc:
            result = {"indicator": indicator, "available": True, "error": str(exc)}
            self._warn_once(
                key=f"macro:{str(indicator).upper()}:{str(exc)}",
                message=f"OpenBB macro fetch failed for {indicator}: {exc}",
            )
            self._write_cache(cache_key, result)
            return result

    def get_news(self, symbol: str, limit: int = 5) -> List[Dict[str, Any]]:
        if openbb is None:
            raise RuntimeError("OpenBB SDK is not installed; cannot fetch news data.")
        obb = self._obb()
        if obb is None or not hasattr(obb, "news"):
            raise RuntimeError("OpenBB news endpoint unavailable.")
        symbol_token = self._normalize_symbol(symbol)
        if "/" in symbol_token:
            symbol_token = symbol_token.split("/", 1)[0]
        company_attempts = []
        if hasattr(obb.news, "company"):
            company_attempts.extend(
                [
                    lambda: obb.news.company(symbol=symbol_token, limit=limit),
                    lambda: obb.news.company(symbol=symbol_token),
                ]
            )
        world_attempts = []
        if hasattr(obb.news, "world"):
            world_attempts.extend(
                [
                    lambda: obb.news.world(limit=limit),
                    lambda: obb.news.world(),
                ]
            )
        attempts = company_attempts + world_attempts
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
        cache_key = self._cache_key("market", symbol)
        cached = self._read_cache(cache_key, ttl_seconds=120)
        if cached is not None:
            return cached
        if not self.available:
            result = {"symbol": symbol, "available": False, "error": "openbb_not_installed"}
            self._write_cache(cache_key, result)
            return result
        try:
            result = {"symbol": symbol, "available": True, "data": self.get_market_data(symbol)}
            self._write_cache(cache_key, result)
            return result
        except Exception as exc:
            result = {"symbol": symbol, "available": True, "error": str(exc)}
            self._warn_once(
                key=f"market:{self._normalize_symbol(symbol)}:{str(exc)}",
                message=f"OpenBB market data fetch failed for {symbol}: {exc}",
            )
            self._write_cache(cache_key, result)
            return result

    def safe_get_news(self, symbol: str, limit: int = 5) -> Dict[str, Any]:
        cache_key = self._cache_key("news", symbol, limit=limit)
        cached = self._read_cache(cache_key, ttl_seconds=300)
        if cached is not None:
            return cached
        if not self.available:
            result = {"symbol": symbol, "available": False, "error": "openbb_not_installed", "data": []}
            self._write_cache(cache_key, result)
            return result
        try:
            result = {"symbol": symbol, "available": True, "data": self.get_news(symbol=symbol, limit=limit)}
            self._write_cache(cache_key, result)
            return result
        except Exception as exc:
            result = {"symbol": symbol, "available": True, "error": str(exc), "data": []}
            self._warn_once(
                key=f"news:{self._normalize_symbol(symbol)}:{str(exc)}",
                message=f"OpenBB news fetch failed for {symbol}: {exc}",
            )
            self._write_cache(cache_key, result)
            return result

    @staticmethod
    def _is_forex_symbol(symbol: str) -> bool:
        token = str(symbol or "").strip().upper()
        if OpenBBDataAdapter._is_crypto_symbol(token):
            return False
        if "/" in token:
            left, right = token.split("/", 1)
            return len(left) == 3 and len(right) == 3 and left.isalpha() and right.isalpha()
        return len(token) == 6 and token.isalpha()

    @staticmethod
    def _is_crypto_symbol(symbol: str) -> bool:
        token = str(symbol or "").strip().upper()
        if "/" not in token:
            return False
        base, quote = token.split("/", 1)
        crypto_assets = {"BTC", "ETH", "SOL", "ADA", "DOGE", "AVAX", "LINK", "XRP", "BNB", "DOT", "LTC"}
        return base in crypto_assets and quote in {"USD", "USDT", "USDC"}

    @staticmethod
    def _normalize_forex_symbol(symbol: str) -> tuple[str, str]:
        token = str(symbol or "").strip().upper()
        if "/" in token:
            left, right = token.split("/", 1)
            return left, right
        return token[:3], token[3:]
