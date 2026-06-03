from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TradeJournal:
    """Persistent JSONL trade journal for entry/exit reasoning."""

    def __init__(
        self,
        journal_file: str = "data/trade_journal.jsonl",
        state_file: str = "data/trade_journal_state.json",
    ):
        self.journal_path = Path(journal_file)
        self.state_path = Path(state_file)
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        if not self.state_path.exists():
            return {"open_trades": {}, "updated_at": _now_iso()}
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("journal state must be object")
            payload.setdefault("open_trades", {})
            if not isinstance(payload["open_trades"], dict):
                payload["open_trades"] = {}
            payload.setdefault("updated_at", _now_iso())
            return payload
        except Exception as exc:
            logger.warning(f"TradeJournal state load failed: {exc}. Using empty state.")
            return {"open_trades": {}, "updated_at": _now_iso()}

    def _save_state(self) -> None:
        self.state["updated_at"] = _now_iso()
        self.state_path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def _append_event(self, event: Dict[str, Any]) -> None:
        line = json.dumps(event, ensure_ascii=True)
        with self.journal_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def record_entry(
        self,
        ticker: str,
        action: str,
        price: float,
        size: float,
        reasoning: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> str:
        token = str(ticker or "").strip().upper()
        if not token:
            raise ValueError("ticker must be non-empty")
        trade_id = str(uuid.uuid4())
        event = {
            "event": "ENTRY",
            "trade_id": trade_id,
            "timestamp": timestamp or _now_iso(),
            "ticker": token,
            "action": str(action or "").upper(),
            "price": float(price),
            "size": float(size),
            "reasoning": reasoning or {},
        }
        self._append_event(event)
        self.state.setdefault("open_trades", {})
        self.state["open_trades"][token] = {
            "trade_id": trade_id,
            "timestamp": event["timestamp"],
            "price": float(price),
            "size": float(size),
        }
        self._save_state()
        return trade_id

    def record_exit(
        self,
        trade_id: str,
        exit_price: float,
        exit_reason: str = "",
        pnl: Optional[float] = None,
        outcome: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> None:
        if not trade_id:
            raise ValueError("trade_id must be non-empty")
        event = {
            "event": "EXIT",
            "trade_id": str(trade_id),
            "timestamp": timestamp or _now_iso(),
            "exit_price": float(exit_price),
            "exit_reason": str(exit_reason or ""),
            "pnl": float(pnl) if pnl is not None else None,
            "outcome": str(outcome) if outcome else None,
        }
        self._append_event(event)
        open_trades = self.state.get("open_trades", {})
        for symbol, payload in list(open_trades.items()):
            if isinstance(payload, dict) and payload.get("trade_id") == trade_id:
                open_trades.pop(symbol, None)
                break
        self._save_state()

    def get_open_trade_id(self, ticker: str) -> Optional[str]:
        token = str(ticker or "").strip().upper()
        payload = self.state.get("open_trades", {}).get(token)
        if not isinstance(payload, dict):
            return None
        trade_id = payload.get("trade_id")
        return str(trade_id) if trade_id else None

    def list_events(self, limit: int = 500) -> List[Dict[str, Any]]:
        if not self.journal_path.exists():
            return []
        rows: List[Dict[str, Any]] = []
        with self.journal_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                token = line.strip()
                if not token:
                    continue
                try:
                    payload = json.loads(token)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    rows.append(payload)
        if limit <= 0:
            return rows
        return rows[-limit:]
