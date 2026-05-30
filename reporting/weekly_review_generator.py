from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class StrategyPerformance:
    name: str
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    total_trades: int
    total_pnl: float
    best_trade: float
    worst_trade: float
    status: str


@dataclass
class SystemImprovement:
    description: str
    impact: str
    impact_magnitude: float
    timestamp: str


@dataclass
class WeeklyReview:
    week_start: str
    week_end: str
    starting_equity: float
    ending_equity: float
    weekly_pnl: float
    weekly_return: float
    best_day: Tuple[str, float]
    worst_day: Tuple[str, float]
    total_trades: int
    win_rate: float
    sharpe_ratio: float
    max_drawdown: float
    strategies: List[StrategyPerformance] = field(default_factory=list)
    improvements: List[SystemImprovement] = field(default_factory=list)
    discoveries: List[str] = field(default_factory=list)
    uncertainties: List[str] = field(default_factory=list)
    next_week_focus: List[str] = field(default_factory=list)


class WeeklyReviewGenerator:
    def __init__(self, performance_tracker, uncertainty_flagger, output_dir: str = "reports/weekly"):
        self.tracker = performance_tracker
        self.flagger = uncertainty_flagger
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_review(
        self,
        week_end_date: Optional[str] = None,
        discoveries: Optional[List[str]] = None,
        improvements: Optional[List[SystemImprovement]] = None,
    ) -> WeeklyReview:
        week_end_date = week_end_date or datetime.now().strftime("%Y-%m-%d")
        discoveries = discoveries or []
        improvements = improvements or []

        week_end = datetime.strptime(week_end_date, "%Y-%m-%d")
        week_start = week_end - timedelta(days=6)
        week_start_str = week_start.strftime("%Y-%m-%d")

        daily_metrics = [
            self.tracker.calculate_daily_pnl((week_start + timedelta(days=offset)).strftime("%Y-%m-%d"))
            for offset in range(7)
        ]
        starting_equity = float(daily_metrics[0].starting_equity)
        ending_equity = float(daily_metrics[-1].ending_equity)
        weekly_pnl = ending_equity - starting_equity
        weekly_return = (weekly_pnl / starting_equity) if starting_equity > 0 else 0.0

        best_day = max(
            ((week_start + timedelta(days=i)).strftime("%Y-%m-%d"), float(item.daily_pnl))
            for i, item in enumerate(daily_metrics)
        )
        worst_day = min(
            ((week_start + timedelta(days=i)).strftime("%Y-%m-%d"), float(item.daily_pnl))
            for i, item in enumerate(daily_metrics)
        )

        perf = self.tracker.get_performance_metrics(lookback_days=7)
        strategies = self._analyze_strategies()
        uncertainties = self._extract_uncertainties()
        focus = self._generate_focus_areas(strategies, uncertainties)

        return WeeklyReview(
            week_start=week_start_str,
            week_end=week_end_date,
            starting_equity=starting_equity,
            ending_equity=ending_equity,
            weekly_pnl=weekly_pnl,
            weekly_return=weekly_return,
            best_day=best_day,
            worst_day=worst_day,
            total_trades=perf.total_trades,
            win_rate=perf.win_rate,
            sharpe_ratio=perf.sharpe_ratio,
            max_drawdown=perf.max_drawdown,
            strategies=strategies,
            improvements=improvements,
            discoveries=discoveries,
            uncertainties=uncertainties,
            next_week_focus=focus,
        )

    def _analyze_strategies(self) -> List[StrategyPerformance]:
        all_trades = self.tracker.get_all_trades()
        by_strategy: Dict[str, List[float]] = {}
        for trade in all_trades:
            by_strategy.setdefault(trade.strategy, []).append(float(trade.pnl))

        strategies: List[StrategyPerformance] = []
        for name, pnls in by_strategy.items():
            wins = [p for p in pnls if p > 0]
            losses = [p for p in pnls if p < 0]
            total = len(pnls)
            if total == 0:
                continue
            win_rate = len(wins) / total
            avg_win = (sum(wins) / len(wins)) if wins else 0.0
            avg_loss = (sum(losses) / len(losses)) if losses else 0.0
            gross_loss = abs(sum(losses))
            profit_factor = (sum(wins) / gross_loss) if gross_loss > 0 else (sum(wins) if wins else 0.0)
            if total < 5:
                status = "new"
            elif win_rate > 0.55 and profit_factor > 1.5:
                status = "performing"
            else:
                status = "underperforming"
            strategies.append(
                StrategyPerformance(
                    name=name,
                    win_rate=win_rate,
                    avg_win=avg_win,
                    avg_loss=avg_loss,
                    profit_factor=profit_factor,
                    total_trades=total,
                    total_pnl=sum(pnls),
                    best_trade=max(pnls),
                    worst_trade=min(pnls),
                    status=status,
                )
            )
        return sorted(strategies, key=lambda item: item.total_pnl, reverse=True)

    def _extract_uncertainties(self) -> List[str]:
        stats = self.flagger.get_approval_statistics()
        distribution = self.flagger.get_confidence_distribution()
        uncertainties: List[str] = []
        if stats["approval_rate"] < 0.5:
            uncertainties.append(f"Low approval rate ({stats['approval_rate']:.1%}).")
        if stats["avg_confidence"] < 0.7:
            uncertainties.append(f"Average confidence remains low ({stats['avg_confidence']:.1%}).")
        if (distribution["very_low"] + distribution["low"]) > (stats["total_plans_scored"] * 0.3):
            uncertainties.append("High proportion of low-confidence plans.")
        return uncertainties

    def _generate_focus_areas(self, strategies: List[StrategyPerformance], uncertainties: List[str]) -> List[str]:
        focus: List[str] = []
        underperforming = [item.name for item in strategies if item.status == "underperforming"]
        if underperforming:
            focus.append(f"Investigate underperforming strategies: {', '.join(underperforming)}")
        new_strategies = [item.name for item in strategies if item.status == "new"]
        if new_strategies:
            focus.append(f"Validate new strategies with more data: {', '.join(new_strategies)}")
        if uncertainties:
            focus.append("Address uncertainty flags before scaling risk.")
        if strategies:
            focus.append(f"Scale top-performing strategy: {strategies[0].name}")
        return focus

    def format_markdown(self, review: WeeklyReview) -> str:
        return "\n".join(
            [
                f"# MECOS Weekly Review ({review.week_start} - {review.week_end})",
                "",
                f"- Weekly PnL: ${review.weekly_pnl:+,.2f}",
                f"- Weekly Return: {review.weekly_return:+.2%}",
                f"- Sharpe Ratio: {review.sharpe_ratio:.2f}",
                f"- Max Drawdown: {review.max_drawdown:.2%}",
                f"- Total Trades: {review.total_trades}",
                f"- Win Rate: {review.win_rate:.1%}",
            ]
        )

    def format_json(self, review: WeeklyReview) -> str:
        return json.dumps(
            {
                "week_start": review.week_start,
                "week_end": review.week_end,
                "performance": {
                    "starting_equity": review.starting_equity,
                    "ending_equity": review.ending_equity,
                    "weekly_pnl": review.weekly_pnl,
                    "weekly_return": review.weekly_return,
                    "best_day": {"date": review.best_day[0], "pnl": review.best_day[1]},
                    "worst_day": {"date": review.worst_day[0], "pnl": review.worst_day[1]},
                },
                "metrics": {
                    "total_trades": review.total_trades,
                    "win_rate": review.win_rate,
                    "sharpe_ratio": review.sharpe_ratio,
                    "max_drawdown": review.max_drawdown,
                },
                "strategies": [strategy.__dict__ for strategy in review.strategies],
                "improvements": [improvement.__dict__ for improvement in review.improvements],
                "discoveries": review.discoveries,
                "uncertainties": review.uncertainties,
                "next_week_focus": review.next_week_focus,
                "generated_at": datetime.now().isoformat(),
            },
            indent=2,
        )

    def save_review(self, review: WeeklyReview, formats: Optional[List[str]] = None) -> Dict[str, str]:
        formats = formats or ["markdown", "json"]
        saved_files: Dict[str, str] = {}
        if "markdown" in formats:
            md_path = self.output_dir / f"week_{review.week_end}_review.md"
            with open(md_path, "w", encoding="utf-8") as handle:
                handle.write(self.format_markdown(review))
            saved_files["markdown"] = str(md_path)
        if "json" in formats:
            json_path = self.output_dir / f"week_{review.week_end}_review.json"
            with open(json_path, "w", encoding="utf-8") as handle:
                handle.write(self.format_json(review))
            saved_files["json"] = str(json_path)
        logger.info(f"Saved weekly review: {saved_files}")
        return saved_files
