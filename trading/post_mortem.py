from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List


class PostMortemEngine:
    def __init__(self, journal_file: str = "data/trade_journal.jsonl"):
        self.path = Path(journal_file)

    def _load_all_trades(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []

        entries: Dict[str, Dict[str, Any]] = {}
        closed: List[Dict[str, Any]] = []
        for raw in self.path.read_text(encoding="utf-8").splitlines():
            token = raw.strip()
            if not token:
                continue
            try:
                event = json.loads(token)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            event_type = str(event.get("event", "")).upper()
            trade_id = str(event.get("trade_id", ""))
            if not trade_id:
                continue
            if event_type == "ENTRY":
                entries[trade_id] = event
                continue
            if event_type != "EXIT":
                continue
            entry = entries.get(trade_id)
            if not entry:
                continue
            entry_price = float(entry.get("price", 0.0) or 0.0)
            exit_price = float(event.get("exit_price", 0.0) or 0.0)
            size = float(entry.get("size", 0.0) or 0.0)
            action = str(entry.get("action", "BUY")).upper()
            explicit_pnl = event.get("pnl")
            if explicit_pnl is not None:
                pnl = float(explicit_pnl)
            elif action == "SELL":
                pnl = (entry_price - exit_price) * size
            else:
                pnl = (exit_price - entry_price) * size
            outcome = event.get("outcome")
            if not outcome:
                outcome = "win" if pnl > 0 else "loss" if pnl < 0 else "flat"
            closed.append(
                {
                    "trade_id": trade_id,
                    "ticker": entry.get("ticker"),
                    "entry_time": entry.get("timestamp"),
                    "exit_time": event.get("timestamp"),
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "size": size,
                    "pnl": pnl,
                    "outcome": outcome,
                    "reasoning": entry.get("reasoning", {}) if isinstance(entry.get("reasoning"), dict) else {},
                    "exit_reason": event.get("exit_reason", ""),
                }
            )
        return closed

    def analyse_signal_accuracy(self) -> Dict[str, Dict[str, Any]]:
        trades = self._load_all_trades()
        if not trades:
            return {}

        stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {"wins": 0, "total": 0})
        for trade in trades:
            reasoning = trade.get("reasoning", {})
            if not isinstance(reasoning, dict):
                continue
            won = str(trade.get("outcome", "")).lower() == "win" or float(trade.get("pnl", 0.0) or 0.0) > 0.0
            for signal_name in reasoning.keys():
                key = str(signal_name).strip().lower()
                if not key:
                    continue
                stats[key]["total"] += 1
                if won:
                    stats[key]["wins"] += 1

        results: Dict[str, Dict[str, Any]] = {}
        for sig, data in stats.items():
            total = int(data["total"])
            if total <= 0:
                continue
            win_rate = float(data["wins"]) / float(total)
            results[sig] = {
                "win_rate": round(win_rate, 3),
                "sample_size": total,
                "verdict": self._verdict(win_rate),
            }
        return dict(sorted(results.items(), key=lambda x: -float(x[1]["win_rate"])))

    @staticmethod
    def _verdict(win_rate: float) -> str:
        if win_rate >= 0.65:
            return "strong - keep weight high"
        if win_rate >= 0.55:
            return "moderate - use with confirmation"
        if win_rate >= 0.45:
            return "weak - reduce weight"
        return "harmful - consider removing"

    def worst_trades(self, n: int = 5) -> List[Dict[str, Any]]:
        trades = self._load_all_trades()
        losses = [t for t in trades if float(t.get("pnl", 0.0) or 0.0) < 0.0]
        return sorted(losses, key=lambda x: float(x.get("pnl", 0.0) or 0.0))[: max(1, int(n))]

    def best_conditions(self) -> Dict[str, Any]:
        trades = self._load_all_trades()
        wins = [t for t in trades if float(t.get("pnl", 0.0) or 0.0) > 0.0]
        if not wins:
            return {"best_regime": None, "best_sentiment": None, "avg_win_rsi": None}

        regimes = []
        sentiments = []
        rsi_values: List[float] = []
        for trade in wins:
            reasoning = trade.get("reasoning", {})
            if not isinstance(reasoning, dict):
                continue
            regime = reasoning.get("regime")
            sentiment = reasoning.get("sentiment")
            rsi = reasoning.get("rsi")
            if regime is not None:
                regimes.append(str(regime))
            if sentiment is not None:
                sentiments.append(str(sentiment))
            try:
                if rsi is not None:
                    rsi_values.append(float(rsi))
            except (TypeError, ValueError):
                pass

        return {
            "best_regime": Counter(regimes).most_common(1)[0][0] if regimes else None,
            "best_sentiment": Counter(sentiments).most_common(1)[0][0] if sentiments else None,
            "avg_win_rsi": (sum(rsi_values) / len(rsi_values)) if rsi_values else None,
        }
