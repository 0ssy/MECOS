import os
import asyncio
import logging
import pandas as pd
from typing import Dict, List, Any
import yfinance as yf

from loguru import logger
from dotenv import load_dotenv

from alpaca.common.exceptions import APIError
from alpaca.data.enums import DataFeed
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

class BrokerConnector:
    """
    Institutional Broker Connector
    Alpaca Paper Trading + Market Data
    """

    def __init__(self):
        load_dotenv(override=True)
        logging.getLogger("yfinance").setLevel(logging.ERROR)

        self.api_key = self._resolve_credential("ALPACA_API_KEY", "APCA_API_KEY_ID")
        self.secret_key = self._resolve_credential("ALPACA_SECRET_KEY", "APCA_API_SECRET_KEY")
        self.base_url = os.getenv(
            "ALPACA_BASE_URL",
            "https://paper-api.alpaca.markets"
        ).strip().rstrip("/")
        self.paper_mode = self._is_paper_mode(self.base_url)

        missing = []
        if not self.api_key:
            missing.append("ALPACA_API_KEY")
        if not self.secret_key:
            missing.append("ALPACA_SECRET_KEY")

        if missing:
            raise ValueError(
                "Missing Alpaca API credentials: "
                + ", ".join(missing)
                + ". Set them in environment variables or .env file."
            )

        self.trading_client = self._build_trading_client(self.paper_mode)

        self.data_client = StockHistoricalDataClient(
            self.api_key,
            self.secret_key
        )

        self._validate_auth_or_retry_mode()
        feed_mode = str(os.getenv("MECOS_ALPACA_STOCK_FEED", "auto")).strip().lower()
        if feed_mode not in {"auto", "iex", "sip"}:
            feed_mode = "auto"
        self._alpaca_feed_mode = feed_mode
        self._sip_entitlement_unavailable = False
        logger.info(f"BrokerConnector initialized | paper_mode={self.paper_mode}")

    @staticmethod
    def _sanitize_secret(value: str) -> str:
        token = (value or "").strip()
        if (token.startswith("'") and token.endswith("'")) or (token.startswith('"') and token.endswith('"')):
            token = token[1:-1].strip()
        return token

    def _resolve_credential(self, primary_name: str, fallback_name: str) -> str:
        primary = self._sanitize_secret(os.getenv(primary_name, ""))
        if primary:
            return primary
        return self._sanitize_secret(os.getenv(fallback_name, ""))

    @staticmethod
    def _is_paper_mode(base_url: str) -> bool:
        normalized = str(base_url or "").lower()
        if "paper-api.alpaca.markets" in normalized:
            return True
        if "api.alpaca.markets" in normalized:
            return False
        return True

    def _build_trading_client(self, paper_mode: bool) -> TradingClient:
        return TradingClient(
            self.api_key,
            self.secret_key,
            paper=bool(paper_mode)
        )

    def _validate_auth_or_retry_mode(self):
        try:
            self.trading_client.get_account()
            return
        except APIError as exc:
            msg = str(exc).lower()
            if "unauthorized" not in msg:
                raise

            # Retry once with opposite account mode (paper/live mismatch is common).
            alternate_mode = not self.paper_mode
            alternate_client = self._build_trading_client(alternate_mode)
            try:
                alternate_client.get_account()
                self.trading_client = alternate_client
                self.paper_mode = alternate_mode
                logger.warning(
                    f"Alpaca auth succeeded after mode switch | paper_mode={self.paper_mode}"
                )
                return
            except APIError:
                pass
            raise RuntimeError(
                "Alpaca authentication failed for both paper and live modes. "
                "Verify API key/secret pair and account access."
            ) from exc

    async def get_market_data(
        self,
        symbol: str,
        timeframe: str = "1Hour",
        limit: int = 200
    ) -> List[Dict]:
        symbol_token = self._normalize_symbol(symbol)
        if not symbol_token:
            logger.warning(f"Market data request with invalid symbol: {symbol}")
            return []

        tf_map = {
            "1Min": TimeFrame(1, TimeFrameUnit.Minute),
            "5Min": TimeFrame(5, TimeFrameUnit.Minute),
            "15Min": TimeFrame(15, TimeFrameUnit.Minute),
            "1Hour": TimeFrame(1, TimeFrameUnit.Hour),
            "1Day": TimeFrame(1, TimeFrameUnit.Day),
        }
        tf_key = timeframe if timeframe in tf_map else "1Hour"
        bar_minutes = {
            "1Min": 1,
            "5Min": 5,
            "15Min": 15,
            "1Hour": 60,
            "1Day": 1440,
        }
        now_utc = pd.Timestamp.utcnow()
        lookback_minutes = max(limit * bar_minutes[tf_key] * 3, bar_minutes[tf_key] * 100)
        start_utc = now_utc - pd.Timedelta(minutes=lookback_minutes)

        df = self._fetch_alpaca_bars(
            symbol=symbol_token,
            timeframe_key=tf_key,
            start_utc=start_utc,
            end_utc=now_utc,
            limit=limit,
            tf_map=tf_map,
        )
        if df is None or df.empty:
            df = await asyncio.to_thread(self._fetch_yfinance_bars, symbol_token, tf_key, limit)
            if df is None or df.empty:
                await asyncio.sleep(0.2)
                df = await asyncio.to_thread(self._fetch_yfinance_bars, symbol_token, tf_key, limit)
            if df is None or df.empty:
                logger.warning(f"No market data returned for {symbol_token} ({tf_key}).")
                return []
        required_columns = {"timestamp", "open", "high", "low", "close", "volume"}
        if not required_columns.issubset(set(df.columns)):
            logger.warning(
                f"Unexpected bars schema for {symbol_token}: {list(df.columns)}"
            )
            return []

        formatted = []

        for _, row in df.iterrows():
            if any(pd.isna(row[col]) for col in ["open", "high", "low", "close", "volume"]):
                continue

            formatted.append({
                "timestamp": str(row["timestamp"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"])
            })

        return formatted[-limit:]

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        token = str(symbol or "").strip().upper().lstrip("$")
        return token

    def _candidate_stock_feeds(self) -> List[DataFeed]:
        if self._alpaca_feed_mode == "iex":
            return [DataFeed.IEX]
        if self._alpaca_feed_mode == "sip":
            return [DataFeed.SIP]
        if self._sip_entitlement_unavailable:
            return [DataFeed.IEX]
        # Auto mode: prefer IEX first to avoid avoidable SIP entitlement errors.
        return [DataFeed.IEX, DataFeed.SIP]

    def _fetch_alpaca_bars(
        self,
        symbol: str,
        timeframe_key: str,
        start_utc: pd.Timestamp,
        end_utc: pd.Timestamp,
        limit: int,
        tf_map: Dict[str, TimeFrame],
    ) -> pd.DataFrame | None:
        feeds = self._candidate_stock_feeds()
        last_error: Exception | None = None
        for feed in feeds:
            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=tf_map[timeframe_key],
                start=start_utc.to_pydatetime(),
                end=end_utc.to_pydatetime(),
                feed=feed,
                limit=limit,
            )
            try:
                bars = self.data_client.get_stock_bars(request)
                if bars.df is not None and not bars.df.empty:
                    if feed == DataFeed.IEX:
                        logger.debug(f"Using IEX feed for {symbol}")
                    return bars.df.reset_index()
            except APIError as exc:
                last_error = exc
                error_text = str(exc)
                if (
                    feed == DataFeed.SIP
                    and "subscription does not permit querying recent SIP data" in error_text
                ):
                    self._sip_entitlement_unavailable = True
                    if self._alpaca_feed_mode == "auto":
                        logger.info("Alpaca SIP entitlement unavailable; using IEX feed for subsequent requests.")
                continue

        if last_error is not None:
            logger.debug(f"Alpaca bars unavailable for {symbol}: {last_error}")
        return None

    @staticmethod
    def _fetch_yfinance_bars(symbol: str, timeframe_key: str, limit: int) -> pd.DataFrame | None:
        interval_map = {
            "1Min": ("1m", "5d"),
            "5Min": ("5m", "30d"),
            "15Min": ("15m", "60d"),
            "1Hour": ("60m", "730d"),
            "1Day": ("1d", "max"),
        }
        interval, period = interval_map.get(timeframe_key, ("60m", "730d"))
        ticker_symbol = BrokerConnector._normalize_symbol(symbol)
        if not ticker_symbol:
            return None
        if "/" in ticker_symbol:
            left, right = ticker_symbol.split("/", 1)
            if len(left) == 3 and len(right) == 3 and left.isalpha() and right.isalpha():
                ticker_symbol = f"{left}{right}=X"
        try:
            history = yf.Ticker(ticker_symbol).history(
                period=period,
                interval=interval,
                auto_adjust=False,
                prepost=True,
                raise_errors=True,
            )
            if history is None or history.empty:
                return None
            history = history.tail(max(5, int(limit))).reset_index()
            history.columns = [str(c).lower() for c in history.columns]
            rename_map = {}
            if "datetime" in history.columns:
                rename_map["datetime"] = "timestamp"
            if "date" in history.columns:
                rename_map["date"] = "timestamp"
            if rename_map:
                history = history.rename(columns=rename_map)
            return history
        except TypeError:
            try:
                history = yf.Ticker(ticker_symbol).history(
                    period=period,
                    interval=interval,
                    auto_adjust=False,
                    prepost=True,
                )
                if history is None or history.empty:
                    return None
                history = history.tail(max(5, int(limit))).reset_index()
                history.columns = [str(c).lower() for c in history.columns]
                rename_map = {}
                if "datetime" in history.columns:
                    rename_map["datetime"] = "timestamp"
                if "date" in history.columns:
                    rename_map["date"] = "timestamp"
                if rename_map:
                    history = history.rename(columns=rename_map)
                return history
            except Exception:
                return None
        except Exception:
            return None

    async def place_order(
        self,
        symbol: str,
        qty: float,
        side: str
    ) -> Dict[str, Any]:

        order_side = (
            OrderSide.BUY
            if side.upper() == "BUY"
            else OrderSide.SELL
        )

        market_order = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=order_side,
            time_in_force=TimeInForce.DAY
        )

        try:
            order = self.trading_client.submit_order(
                order_data=market_order
            )
        except APIError as exc:
            raise RuntimeError(
                f"Order submit failed for {symbol} {side} qty={qty}: {exc}"
            ) from exc

        logger.info(
            f"Order submitted: {side} {qty} {symbol}"
        )

        return {
            "id": order.id,
            "symbol": order.symbol,
            "qty": order.qty,
            "side": side,
            "status": str(order.status)
        }

    async def get_positions(self):
        positions = self.trading_client.get_all_positions()

        output = []

        for pos in positions:

            output.append({
                "symbol": pos.symbol,
                "qty": float(pos.qty),
                "market_value": float(pos.market_value),
                "unrealized_pl": float(pos.unrealized_pl)
            })

        return output

    async def get_account_info(self):
        try:
            account = self.trading_client.get_account()
        except APIError as exc:
            raise RuntimeError(f"Failed to get account info: {exc}") from exc

        return {
            "cash": float(account.cash),
            "portfolio_value": float(account.portfolio_value),
            "buying_power": float(account.buying_power),
            "equity": float(account.equity),
            "status": str(account.status)
        }
