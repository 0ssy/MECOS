"""
PerformanceTracker — trading performance persistence and analytics.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import statistics
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    symbol: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    timestamp: str
    trade_type: str
    strategy: str
    confidence: float = 0.0


@dataclass
class PerformanceMetrics:
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_return: float
    total_trades: int
    avg_trade_pnl: float


@dataclass
class DailyMetrics:
    date: str
    starting_equity: float
    ending_equity: float
    daily_pnl: float
    daily_return: float
    trades_count: int
    wins: int
    losses: int
    win_rate: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float


class PerformanceTracker:
    """
    Real-time performance tracker persisted in SQLite.
    Uses dedicated table names to avoid schema conflicts with trading tables.
    """

    def __init__(
        self,
        db_path: str = "data/trading.db",
        starting_equity: float = 10000.0,
        goal_equity: float = 60000.0,
    ):
        self.db_path = db_path
        self.starting_equity = float(starting_equity)
        self.current_equity = float(starting_equity)
        self.goal_equity = float(goal_equity)
        self.equity_curve: List[float] = [float(starting_equity)]
        self.reached_milestones: set[float] = set()
        self.milestones = self._calculate_milestones()
        self._init_database()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _calculate_milestones(self) -> List[float]:
        if self.goal_equity <= self.starting_equity:
            return [self.goal_equity]
        step = (self.goal_equity - self.starting_equity) / 6.0
        milestones = [self.starting_equity + (step * i) for i in range(1, 7)]
        return sorted(float(m) for m in milestones)

    def _init_database(self) -> None:
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS performance_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                quantity REAL NOT NULL,
                pnl REAL NOT NULL,
                timestamp TEXT NOT NULL,
                trade_type TEXT NOT NULL,
                strategy TEXT NOT NULL,
                confidence REAL DEFAULT 0.0
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS performance_daily_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE NOT NULL,
                ending_equity REAL NOT NULL,
                daily_return REAL NOT NULL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS performance_milestones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                milestone_amount REAL UNIQUE NOT NULL,
                reached_at TEXT,
                days_to_reach INTEGER
            )
            """
        )

        conn.commit()
        conn.close()

    async def update(self, portfolio_value: float) -> None:
        self.update_equity(float(portfolio_value))

    def update_equity(self, portfolio_value: float) -> None:
        previous_equity = self.current_equity
        self.current_equity = float(portfolio_value)
        self.equity_curve.append(self.current_equity)
        if previous_equity > 0:
            daily_return = (self.current_equity - previous_equity) / previous_equity
        else:
            daily_return = 0.0
        self._upsert_daily_metric(datetime.now().strftime("%Y-%m-%d"), self.current_equity, daily_return)
        self._check_milestone()

    def record_trade(
        self,
        symbol: str,
        entry_price: float,
        exit_price: float,
        quantity: float,
        pnl: float,
        trade_type: str = "BUY",
        strategy: str = "unknown",
        confidence: float = 0.0,
    ) -> None:
        trade = Trade(
            symbol=symbol,
            entry_price=float(entry_price),
            exit_price=float(exit_price),
            quantity=float(quantity),
            pnl=float(pnl),
            timestamp=datetime.now().isoformat(),
            trade_type=str(trade_type),
            strategy=str(strategy),
            confidence=float(confidence),
        )

        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO performance_trades (
                symbol, entry_price, exit_price, quantity, pnl, timestamp, trade_type, strategy, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade.symbol,
                trade.entry_price,
                trade.exit_price,
                trade.quantity,
                trade.pnl,
                trade.timestamp,
                trade.trade_type,
                trade.strategy,
                trade.confidence,
            ),
        )
        conn.commit()
        conn.close()

    def record_trade_close(
        self,
        pnl: float,
        symbol: str = "UNKNOWN",
        price: float = 0.0,
        quantity: float = 1.0,
        strategy: str = "unknown",
        confidence: float = 0.0,
    ) -> None:
        self.record_trade(
            symbol=symbol,
            entry_price=price,
            exit_price=price,
            quantity=quantity,
            pnl=float(pnl),
            trade_type="SELL",
            strategy=strategy,
            confidence=confidence,
        )

    def _upsert_daily_metric(self, date: str, ending_equity: float, daily_return: float) -> None:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO performance_daily_metrics (date, ending_equity, daily_return)
            VALUES (?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                ending_equity=excluded.ending_equity,
                daily_return=excluded.daily_return
            """,
            (date, float(ending_equity), float(daily_return)),
        )
        conn.commit()
        conn.close()

    def _check_milestone(self) -> Optional[float]:
        for milestone in self.milestones:
            if self.current_equity >= milestone and milestone not in self.reached_milestones:
                self.reached_milestones.add(milestone)
                self._record_milestone(milestone)
                logger.info(f"Milestone reached: ${milestone:,.2f}")
                return milestone
        return None

    def _record_milestone(self, milestone_amount: float) -> None:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO performance_milestones (milestone_amount, reached_at, days_to_reach)
            VALUES (?, ?, ?)
            """,
            (float(milestone_amount), datetime.now().isoformat(), self._calculate_days_to_reach()),
        )
        conn.commit()
        conn.close()

    def _calculate_days_to_reach(self) -> int:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT MIN(timestamp) FROM performance_trades")
        result = cursor.fetchone()
        conn.close()
        if result and result[0]:
            first_trade_time = datetime.fromisoformat(result[0])
            return max((datetime.now() - first_trade_time).days, 1)
        return 0

    def get_all_trades(self, lookback_days: Optional[int] = None) -> List[Trade]:
        conn = self._connect()
        cursor = conn.cursor()
        params: tuple = ()
        query = """
            SELECT symbol, entry_price, exit_price, quantity, pnl, timestamp, trade_type, strategy, confidence
            FROM performance_trades
        """
        if lookback_days is not None:
            cutoff = (datetime.now() - timedelta(days=int(lookback_days))).isoformat()
            query += " WHERE timestamp >= ?"
            params = (cutoff,)
        query += " ORDER BY timestamp ASC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [
            Trade(
                symbol=str(row[0]),
                entry_price=float(row[1]),
                exit_price=float(row[2]),
                quantity=float(row[3]),
                pnl=float(row[4]),
                timestamp=str(row[5]),
                trade_type=str(row[6]),
                strategy=str(row[7]),
                confidence=float(row[8] or 0.0),
            )
            for row in rows
        ]

    def calculate_daily_pnl(self, date: Optional[str] = None) -> DailyMetrics:
        target_date = date or datetime.now().strftime("%Y-%m-%d")
        day_start = f"{target_date}T00:00:00"
        day_end = f"{target_date}T23:59:59.999999"
        prev_date = (datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")

        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT ending_equity FROM performance_daily_metrics WHERE date = ?",
            (prev_date,),
        )
        prev_row = cursor.fetchone()
        starting_equity = float(prev_row[0]) if prev_row else float(self.starting_equity)

        cursor.execute(
            "SELECT ending_equity FROM performance_daily_metrics WHERE date = ?",
            (target_date,),
        )
        day_row = cursor.fetchone()

        cursor.execute(
            """
            SELECT pnl FROM performance_trades
            WHERE timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp
            """,
            (day_start, day_end),
        )
        pnls = [float(row[0]) for row in cursor.fetchall()]
        conn.close()

        daily_pnl = float(sum(pnls))
        ending_equity = float(day_row[0]) if day_row else (starting_equity + daily_pnl)
        daily_return = (daily_pnl / starting_equity) if starting_equity > 0 else 0.0
        wins = len([p for p in pnls if p > 0])
        losses = len([p for p in pnls if p <= 0])
        winning = [p for p in pnls if p > 0]
        losing = [p for p in pnls if p < 0]

        return DailyMetrics(
            date=target_date,
            starting_equity=starting_equity,
            ending_equity=ending_equity,
            daily_pnl=daily_pnl,
            daily_return=daily_return,
            trades_count=len(pnls),
            wins=wins,
            losses=losses,
            win_rate=(wins / len(pnls)) if pnls else 0.0,
            avg_win=(sum(winning) / len(winning)) if winning else 0.0,
            avg_loss=(sum(losing) / len(losing)) if losing else 0.0,
            largest_win=max(winning) if winning else 0.0,
            largest_loss=min(losing) if losing else 0.0,
        )

    def _calculate_daily_returns(self, lookback_days: int) -> List[float]:
        conn = self._connect()
        cursor = conn.cursor()
        cutoff_date = (datetime.now() - timedelta(days=int(lookback_days))).strftime("%Y-%m-%d")
        cursor.execute(
            """
            SELECT daily_return FROM performance_daily_metrics
            WHERE date >= ?
            ORDER BY date
            """,
            (cutoff_date,),
        )
        returns = [float(row[0]) for row in cursor.fetchall()]
        conn.close()
        return returns

    def _calculate_sharpe_ratio(self, returns: List[float], risk_free_rate: float = 0.02) -> float:
        if len(returns) < 2:
            return 0.0
        std_dev = statistics.stdev(returns)
        if std_dev == 0:
            return 0.0
        mean_return = statistics.mean(returns)
        daily_risk_free = risk_free_rate / 252.0
        return (mean_return - daily_risk_free) / std_dev * (252.0 ** 0.5)

    def _calculate_max_drawdown(self) -> float:
        if len(self.equity_curve) < 2:
            return 0.0
        peak = self.equity_curve[0]
        max_drawdown = 0.0
        for equity in self.equity_curve:
            peak = max(peak, equity)
            drawdown = (peak - equity) / peak if peak > 0 else 0.0
            max_drawdown = max(max_drawdown, drawdown)
        return max_drawdown

    def get_performance_metrics(self, lookback_days: int = 30) -> PerformanceMetrics:
        conn = self._connect()
        cursor = conn.cursor()
        cutoff = (datetime.now() - timedelta(days=int(lookback_days))).isoformat()
        cursor.execute(
            """
            SELECT pnl FROM performance_trades
            WHERE timestamp > ?
            """,
            (cutoff,),
        )
        trades = [float(row[0]) for row in cursor.fetchall()]
        conn.close()

        if not trades:
            return PerformanceMetrics(
                sharpe_ratio=0.0,
                max_drawdown=self._calculate_max_drawdown(),
                win_rate=0.0,
                profit_factor=0.0,
                total_return=(self.current_equity - self.starting_equity) / max(self.starting_equity, 1.0),
                total_trades=0,
                avg_trade_pnl=0.0,
            )

        wins = [p for p in trades if p > 0]
        losses = [p for p in trades if p < 0]
        total_wins = sum(wins)
        total_losses = abs(sum(losses))
        profit_factor = total_wins / total_losses if total_losses > 0 else (float(total_wins) if total_wins > 0 else 0.0)
        win_rate = len(wins) / len(trades)
        total_pnl = sum(trades)
        daily_returns = self._calculate_daily_returns(lookback_days)

        return PerformanceMetrics(
            sharpe_ratio=self._calculate_sharpe_ratio(daily_returns),
            max_drawdown=self._calculate_max_drawdown(),
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_return=total_pnl / max(self.starting_equity, 1.0),
            total_trades=len(trades),
            avg_trade_pnl=total_pnl / len(trades),
        )

    def get_progress_to_goal(self) -> Dict[str, float]:
        denominator = self.goal_equity - self.starting_equity
        progress = ((self.current_equity - self.starting_equity) / denominator) if denominator != 0 else 0.0
        days_to_goal = self._estimate_days_to_goal()
        return {
            "current_equity": float(self.current_equity),
            "goal_equity": float(self.goal_equity),
            "remaining": float(max(0.0, self.goal_equity - self.current_equity)),
            "progress_percent": float(max(0.0, min(100.0, progress * 100.0))),
            "days_to_goal": float(days_to_goal),
        }

    def _estimate_days_to_goal(self) -> int:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT MIN(date), MAX(date) FROM performance_daily_metrics")
        row = cursor.fetchone()
        conn.close()
        if not row or not row[0] or not row[1]:
            return 0
        try:
            start_date = datetime.strptime(str(row[0]), "%Y-%m-%d")
            end_date = datetime.strptime(str(row[1]), "%Y-%m-%d")
        except ValueError:
            return 0
        elapsed_days = max((end_date - start_date).days, 1)
        gained = self.current_equity - self.starting_equity
        remaining = self.goal_equity - self.current_equity
        if gained <= 0 or remaining <= 0:
            return 0
        pace_per_day = gained / elapsed_days
        if pace_per_day <= 0:
            return 0
        return int(max(1, round(remaining / pace_per_day)))

    def get_metrics(self, lookback_days: int = 30) -> Dict[str, float]:
        performance = self.get_performance_metrics(lookback_days=lookback_days)
        progress = self.get_progress_to_goal()
        return {
            **asdict(performance),
            **progress,
        }

    def export_metrics_json(self, filepath: str) -> None:
        payload = {
            "timestamp": datetime.now().isoformat(),
            "metrics": self.get_metrics(),
            "milestones_reached": sorted(self.reached_milestones),
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
