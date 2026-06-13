from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(dt: Optional[datetime] = None) -> datetime:
    if dt is None:
        return _utcnow()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class CircuitBreaker:
    max_losses: int = 3
    window_hours: float = 24.0
    cooldown_minutes: float = 60.0
    loss_events: List[datetime] = field(default_factory=list)
    halted_until: Optional[datetime] = None

    def _prune(self, now: Optional[datetime] = None) -> None:
        ts = _to_utc(now)
        window_start = ts - timedelta(hours=float(self.window_hours))
        self.loss_events = [x for x in self.loss_events if x >= window_start]
        if self.halted_until and ts >= self.halted_until:
            self.halted_until = None

    def register_trade_close(self, pnl: float, when: Optional[datetime] = None) -> None:
        ts = _to_utc(when)
        self._prune(ts)
        if float(pnl) < 0.0:
            self.loss_events.append(ts)
            self._prune(ts)
        if len(self.loss_events) >= int(self.max_losses):
            self.halted_until = ts + timedelta(minutes=float(self.cooldown_minutes))
            logger.error(
                f"Circuit breaker triggered: {len(self.loss_events)} losses in "
                f"{self.window_hours:.1f}h. Halt until {self.halted_until.isoformat()}."
            )

    def should_halt(self, now: Optional[datetime] = None) -> bool:
        self._prune(now)
        return self.halted_until is not None

    def status(self) -> Dict[str, Any]:
        self._prune()
        return {
            "halted": bool(self.halted_until is not None),
            "halted_until": self.halted_until.isoformat() if self.halted_until else None,
            "loss_count_window": len(self.loss_events),
            "max_losses": int(self.max_losses),
            "window_hours": float(self.window_hours),
        }


class PositionStateStore:
    def __init__(self, path: str = "data/state.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load()

    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"open_positions": {}, "last_updated": _utcnow().isoformat()}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("state payload must be object")
            payload.setdefault("open_positions", {})
            if not isinstance(payload["open_positions"], dict):
                payload["open_positions"] = {}
            payload.setdefault("last_updated", _utcnow().isoformat())
            return payload
        except Exception as exc:
            logger.warning(f"Position state load failed ({self.path}): {exc}. Using empty state.")
            return {"open_positions": {}, "last_updated": _utcnow().isoformat()}

    def _save(self) -> None:
        self.state["last_updated"] = _utcnow().isoformat()
        self.path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def has_open_position(self, symbol: str) -> bool:
        token = str(symbol or "").strip().upper()
        if not token:
            return False
        return token in self.state.get("open_positions", {})

    def record_entry(
        self,
        symbol: str,
        entry: float,
        size: float,
        stop: Optional[float] = None,
        take_profit: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        token = str(symbol or "").strip().upper()
        if not token:
            return
        self.state.setdefault("open_positions", {})
        self.state["open_positions"][token] = {
            "entry": float(entry),
            "size": float(size),
            "stop": float(stop) if stop is not None else None,
            "take_profit": float(take_profit) if take_profit is not None else None,
            "opened_at": _utcnow().isoformat(),
            "metadata": metadata or {},
        }
        self._save()

    def record_exit(self, symbol: str) -> None:
        token = str(symbol or "").strip().upper()
        if not token:
            return
        self.state.setdefault("open_positions", {})
        self.state["open_positions"].pop(token, None)
        self._save()

    def replace_from_positions(self, positions: Dict[str, Dict[str, Any]]) -> None:
        snapshot: Dict[str, Any] = {}
        for symbol, payload in (positions or {}).items():
            token = str(symbol or "").strip().upper()
            if not token or not isinstance(payload, dict):
                continue
            size = float(payload.get("size", 0.0) or 0.0)
            if size <= 0.0:
                continue
            snapshot[token] = {
                "entry": float(payload.get("avg_price", payload.get("entry", 0.0)) or 0.0),
                "size": size,
                "stop": float(payload.get("stop_loss", payload.get("stop", 0.0)) or 0.0) or None,
                "take_profit": float(payload.get("take_profit", 0.0) or 0.0) or None,
                "opened_at": str(payload.get("entry_time", _utcnow().isoformat())),
                "metadata": {"source": "restored_snapshot"},
            }
        self.state["open_positions"] = snapshot
        self._save()

    def snapshot(self) -> Dict[str, Any]:
        return {
            "open_positions": dict(self.state.get("open_positions", {})),
            "last_updated": self.state.get("last_updated"),
        }


class StabilityLayer:
    """Data validation + position tracking + circuit breaker + decision logging."""

    def __init__(
        self,
        state_path: str = "data/state.json",
        max_losses: int = 3,
        window_hours: float = 24.0,
        cooldown_minutes: float = 60.0,
    ):
        self.position_store = PositionStateStore(path=state_path)
        self.circuit_breaker = CircuitBreaker(
            max_losses=max_losses,
            window_hours=window_hours,
            cooldown_minutes=cooldown_minutes,
        )

    @staticmethod
    def _is_valid_number(value: Any) -> bool:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return False
        return math.isfinite(numeric)

    def validate_tick(self, symbol: str, tick: Dict[str, Any]) -> Tuple[bool, str]:
        close = tick.get("close")
        if not self._is_valid_number(close):
            return False, f"invalid_close_for_{symbol}"
        if float(close) <= 0.0:
            return False, f"non_positive_close_for_{symbol}"
        volume = tick.get("volume", 0.0)
        if not self._is_valid_number(volume):
            return False, f"invalid_volume_for_{symbol}"
        return True, ""

    def sanitize_bars(self, symbol: str, bars: List[Dict[str, Any]], min_bars: int = 1) -> List[Dict[str, Any]]:
        cleaned: List[Dict[str, Any]] = []
        for bar in bars:
            if not isinstance(bar, dict):
                continue
            ok, reason = self.validate_tick(symbol, bar)
            if not ok:
                logger.warning(f"Bad data for {symbol} - skipping bar ({reason})")
                continue
            cloned = dict(bar)
            cloned["close"] = float(cloned["close"])
            cloned["open"] = float(cloned.get("open", cloned["close"]) or cloned["close"])
            cloned["high"] = float(cloned.get("high", cloned["close"]) or cloned["close"])
            cloned["low"] = float(cloned.get("low", cloned["close"]) or cloned["close"])
            cloned["volume"] = float(cloned.get("volume", 1.0) or 1.0)
            cleaned.append(cloned)

        if len(cleaned) < int(min_bars):
            logger.warning(f"{symbol}: clean bars below threshold ({len(cleaned)}/{min_bars})")
            return []
        return cleaned

    def can_place_order(self, symbol: str, side: str) -> Tuple[bool, str]:
        if self.circuit_breaker.should_halt():
            status = self.circuit_breaker.status()
            return False, f"circuit_breaker_halted_until_{status.get('halted_until')}"
        action = str(side or "").upper()
        if action == "BUY" and self.position_store.has_open_position(symbol):
            return False, "duplicate_entry_blocked"
        if action == "SELL" and not self.position_store.has_open_position(symbol):
            return False, "no_open_position_to_exit"
        return True, ""

    def record_order_fill(
        self,
        symbol: str,
        side: str,
        price: float,
        size: float,
        stop: Optional[float] = None,
        take_profit: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        action = str(side or "").upper()
        if action == "BUY":
            self.position_store.record_entry(symbol, entry=price, size=size, stop=stop, take_profit=take_profit, metadata=metadata)
        elif action == "SELL":
            self.position_store.record_exit(symbol)

    def record_trade_close(self, symbol: str, pnl: float, exit_reason: str = "") -> None:
        self.circuit_breaker.register_trade_close(float(pnl))
        logger.info(
            f"TRADE_CLOSE | {symbol} | pnl={float(pnl):.2f} | reason={exit_reason or 'n/a'} | "
            f"breaker={self.circuit_breaker.status()}"
        )

    @staticmethod
    def log_signal_decision(
        symbol: str,
        action: str,
        confidence: float,
        regime: str,
        size: float,
        rsi: Optional[float] = None,
    ) -> None:
        rsi_text = f"{float(rsi):.1f}" if rsi is not None else "n/a"
        logger.info(
            f"SIGNAL | {symbol} | RSI={rsi_text} | Regime={regime} | "
            f"Action={str(action).upper()} | Size={float(size):.4f} | Confidence={float(confidence):.3f}"
        )
