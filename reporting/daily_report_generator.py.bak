from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class DailyReport:
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
    sharpe_ratio: float
    max_drawdown: float
    goal_equity: float
    progress_percent: float
    trades: List[Dict] = field(default_factory=list)
    discoveries: List[str] = field(default_factory=list)


class DailyReportGenerator:
    def __init__(self, performance_tracker, output_dir: str = "reports/daily", goal_equity: float = 60000.0):
        self.tracker = performance_tracker
        self.output_dir = Path(output_dir)
        self.goal_equity = float(goal_equity)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_report(self, date: Optional[str] = None, discoveries: Optional[List[str]] = None) -> DailyReport:
        target_date = date or datetime.now().strftime("%Y-%m-%d")
        discoveries = discoveries or []
        daily_metrics = self.tracker.calculate_daily_pnl(target_date)
        perf = self.tracker.get_performance_metrics(lookback_days=30)
        progress = self.tracker.get_progress_to_goal()
        today_trades = [
            {
                "symbol": t.symbol,
                "type": t.trade_type,
                "entry": t.entry_price,
                "exit": t.exit_price,
                "quantity": t.quantity,
                "pnl": t.pnl,
                "strategy": t.strategy,
                "confidence": t.confidence,
                "timestamp": t.timestamp,
            }
            for t in self.tracker.get_all_trades()
            if str(t.timestamp).startswith(target_date)
        ]
        return DailyReport(
            date=target_date,
            starting_equity=daily_metrics.starting_equity,
            ending_equity=daily_metrics.ending_equity,
            daily_pnl=daily_metrics.daily_pnl,
            daily_return=daily_metrics.daily_return,
            trades_count=daily_metrics.trades_count,
            wins=daily_metrics.wins,
            losses=daily_metrics.losses,
            win_rate=daily_metrics.win_rate,
            avg_win=daily_metrics.avg_win,
            avg_loss=daily_metrics.avg_loss,
            largest_win=daily_metrics.largest_win,
            largest_loss=daily_metrics.largest_loss,
            sharpe_ratio=perf.sharpe_ratio,
            max_drawdown=perf.max_drawdown,
            goal_equity=self.goal_equity,
            progress_percent=float(progress.get("progress_percent", 0.0)),
            trades=today_trades,
            discoveries=list(discoveries),
        )

    def format_markdown(self, report: DailyReport) -> str:
        return "\n".join(
            [
                f"# MECOS Daily Report - {report.date}",
                "",
                f"- Starting Equity: ${report.starting_equity:,.2f}",
                f"- Ending Equity: ${report.ending_equity:,.2f}",
                f"- Daily PnL: ${report.daily_pnl:+,.2f}",
                f"- Daily Return: {report.daily_return:+.2%}",
                f"- Sharpe Ratio: {report.sharpe_ratio:.2f}",
                f"- Max Drawdown: {report.max_drawdown:.2%}",
                f"- Trades: {report.trades_count} (win rate {report.win_rate:.1%})",
                f"- Goal Progress: {report.progress_percent:.1f}%",
            ]
        )

    def format_json(self, report: DailyReport) -> str:
        return json.dumps(
            {
                "date": report.date,
                "performance": {
                    "starting_equity": report.starting_equity,
                    "ending_equity": report.ending_equity,
                    "daily_pnl": report.daily_pnl,
                    "daily_return": report.daily_return,
                },
                "metrics": {
                    "trades_count": report.trades_count,
                    "wins": report.wins,
                    "losses": report.losses,
                    "win_rate": report.win_rate,
                    "avg_win": report.avg_win,
                    "avg_loss": report.avg_loss,
                    "largest_win": report.largest_win,
                    "largest_loss": report.largest_loss,
                    "sharpe_ratio": report.sharpe_ratio,
                    "max_drawdown": report.max_drawdown,
                },
                "progress": {
                    "goal_equity": report.goal_equity,
                    "current_equity": report.ending_equity,
                    "progress_percent": report.progress_percent,
                },
                "trades": report.trades,
                "discoveries": report.discoveries,
                "generated_at": datetime.now().isoformat(),
            },
            indent=2,
        )

    def save_report(self, report: DailyReport, formats: Optional[List[str]] = None) -> Dict[str, str]:
        formats = formats or ["markdown", "json"]
        saved_files: Dict[str, str] = {}

        if "markdown" in formats:
            md_path = self.output_dir / f"{report.date}_report.md"
            with open(md_path, "w", encoding="utf-8") as handle:
                handle.write(self.format_markdown(report))
            saved_files["markdown"] = str(md_path)
        if "json" in formats:
            json_path = self.output_dir / f"{report.date}_report.json"
            with open(json_path, "w", encoding="utf-8") as handle:
                handle.write(self.format_json(report))
            saved_files["json"] = str(json_path)

        logger.info(f"Saved daily report: {saved_files}")
        return saved_files
