"""
WeeklyReviewGenerator — Comprehensive Weekly Performance Analysis (MECOS v3.0 Phase 5)

Generates detailed weekly reviews analyzing strategy performance, discoveries,
system improvements, and uncertainties.

Location: reporting/weekly_review_generator.py
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class StrategyPerformance:
    """Performance metrics for a trading strategy."""
    name: str
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    total_trades: int
    total_pnl: float
    best_trade: float
    worst_trade: float
    status: str  # "performing", "underperforming", "new"


@dataclass
class SystemImprovement:
    """Represents a system improvement made."""
    description: str
    impact: str  # "positive", "negative", "neutral"
    impact_magnitude: float  # 0.0-1.0
    timestamp: str


@dataclass
class WeeklyReview:
    """Complete weekly review data."""
    week_start: str
    week_end: str
    starting_equity: float
    ending_equity: float
    weekly_pnl: float
    weekly_return: float
    best_day: Tuple[str, float]  # (date, pnl)
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
    """
    Generate comprehensive weekly performance reviews.
    
    Responsibilities:
    - Analyze weekly performance metrics
    - Compare strategies
    - Track system improvements
    - Flag uncertainties and limitations
    - Generate actionable insights
    """
    
    def __init__(
        self,
        performance_tracker,
        uncertainty_flagger,
        output_dir: str = "reports/weekly",
    ):
        """
        Initialize WeeklyReviewGenerator.
        
        Args:
            performance_tracker: PerformanceTracker instance
            uncertainty_flagger: UncertaintyFlagger instance
            output_dir: Directory to save reports
        """
        self.tracker = performance_tracker
        self.flagger = uncertainty_flagger
        self.output_dir = Path(output_dir)
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"WeeklyReviewGenerator initialized")
    
    def generate_review(
        self,
        week_end_date: Optional[str] = None,
        discoveries: Optional[List[str]] = None,
        improvements: Optional[List[SystemImprovement]] = None,
    ) -> WeeklyReview:
        """
        Generate complete weekly review.
        
        Args:
            week_end_date: End date of week (YYYY-MM-DD). If None, uses today.
            discoveries: List of discoveries made this week
            improvements: List of system improvements made
        
        Returns:
            WeeklyReview object
        """
        if week_end_date is None:
            week_end_date = datetime.now().strftime("%Y-%m-%d")
        
        if discoveries is None:
            discoveries = []
        
        if improvements is None:
            improvements = []
        
        # Calculate week dates
        week_end = datetime.strptime(week_end_date, "%Y-%m-%d")
        week_start = week_end - timedelta(days=6)
        week_start_str = week_start.strftime("%Y-%m-%d")
        
        # Get daily metrics for the week
        daily_metrics_list = []
        for i in range(7):
            date = (week_start + timedelta(days=i)).strftime("%Y-%m-%d")
            daily = self.tracker.calculate_daily_pnl(date)
            daily_metrics_list.append(daily)
        
        # Calculate weekly totals
        starting_equity = daily_metrics_list[0].starting_equity
        ending_equity = daily_metrics_list[-1].ending_equity
        weekly_pnl = ending_equity - starting_equity
        weekly_return = weekly_pnl / starting_equity if starting_equity > 0 else 0.0
        
        # Find best and worst days
        best_day = max(
            ((week_start + timedelta(days=i)).strftime("%Y-%m-%d"), m.daily_pnl)
            for i, m in enumerate(daily_metrics_list)
        )
        worst_day = min(
            ((week_start + timedelta(days=i)).strftime("%Y-%m-%d"), m.daily_pnl)
            for i, m in enumerate(daily_metrics_list)
        )
        
        # Get performance metrics
        perf_metrics = self.tracker.get_performance_metrics(lookback_days=7)
        
        # Analyze strategies
        strategies = self._analyze_strategies()
        
        # Get uncertainties from flagger
        uncertainties = self._extract_uncertainties()
        
        # Generate next week focus
        next_week_focus = self._generate_focus_areas(strategies, uncertainties)
        
        review = WeeklyReview(
            week_start=week_start_str,
            week_end=week_end_date,
            starting_equity=starting_equity,
            ending_equity=ending_equity,
            weekly_pnl=weekly_pnl,
            weekly_return=weekly_return,
            best_day=best_day,
            worst_day=worst_day,
            total_trades=perf_metrics.total_trades,
            win_rate=perf_metrics.win_rate,
            sharpe_ratio=perf_metrics.sharpe_ratio,
            max_drawdown=perf_metrics.max_drawdown,
            strategies=strategies,
            improvements=improvements,
            discoveries=discoveries,
            uncertainties=uncertainties,
            next_week_focus=next_week_focus,
        )
        
        return review
    
    def _analyze_strategies(self) -> List[StrategyPerformance]:
        """Analyze performance of each strategy."""
        all_trades = self.tracker.get_all_trades()
        
        strategy_stats = {}
        
        for trade in all_trades:
            if trade.strategy not in strategy_stats:
                strategy_stats[trade.strategy] = {
                    "trades": [],
                    "wins": 0,
                    "losses": 0,
                }
            
            strategy_stats[trade.strategy]["trades"].append(trade.pnl)
            
            if trade.pnl > 0:
                strategy_stats[trade.strategy]["wins"] += 1
            else:
                strategy_stats[trade.strategy]["losses"] += 1
        
        strategies = []
        
        for strategy_name, stats in strategy_stats.items():
            trades = stats["trades"]
            
            if not trades:
                continue
            
            total_pnl = sum(trades)
            wins = stats["wins"]
            losses = stats["losses"]
            total_trades = len(trades)
            
            win_rate = wins / total_trades if total_trades > 0 else 0.0
            
            winning_trades = [t for t in trades if t > 0]
            losing_trades = [t for t in trades if t < 0]
            
            avg_win = sum(winning_trades) / len(winning_trades) if winning_trades else 0.0
            avg_loss = sum(losing_trades) / len(losing_trades) if losing_trades else 0.0
            
            profit_factor = (
                sum(winning_trades) / abs(sum(losing_trades))
                if losing_trades and sum(losing_trades) != 0
                else 0.0
            )
            
            # Determine status
            if total_trades < 5:
                status = "new"
            elif win_rate > 0.55 and profit_factor > 1.5:
                status = "performing"
            else:
                status = "underperforming"
            
            strategy = StrategyPerformance(
                name=strategy_name,
                win_rate=win_rate,
                avg_win=avg_win,
                avg_loss=avg_loss,
                profit_factor=profit_factor,
                total_trades=total_trades,
                total_pnl=total_pnl,
                best_trade=max(trades),
                worst_trade=min(trades),
                status=status,
            )
            
            strategies.append(strategy)
        
        return sorted(strategies, key=lambda s: s.total_pnl, reverse=True)
    
    def _extract_uncertainties(self) -> List[str]:
        """Extract uncertainties from flagger."""
        uncertainties = []
        
        stats = self.flagger.get_approval_statistics()
        
        if stats["approval_rate"] < 0.5:
            uncertainties.append(
                f"Low approval rate ({stats['approval_rate']:.1%}). "
                f"Many plans are being rejected due to low confidence."
            )
        
        if stats["avg_confidence"] < 0.7:
            uncertainties.append(
                f"Average confidence is low ({stats['avg_confidence']:.1%}). "
                f"Consider collecting more data before executing trades."
            )
        
        dist = self.flagger.get_confidence_distribution()
        if dist["very_low"] + dist["low"] > stats["total_plans_scored"] * 0.3:
            uncertainties.append(
                "High proportion of low-confidence plans. "
                "System may need more training data or better signal detection."
            )
        
        return uncertainties
    
    def _generate_focus_areas(
        self,
        strategies: List[StrategyPerformance],
        uncertainties: List[str],
    ) -> List[str]:
        """Generate focus areas for next week."""
        focus = []
        
        # Focus on underperforming strategies
        underperforming = [s for s in strategies if s.status == "underperforming"]
        if underperforming:
            focus.append(
                f"Investigate underperforming strategies: "
                f"{', '.join(s.name for s in underperforming)}"
            )
        
        # Focus on new strategies
        new_strategies = [s for s in strategies if s.status == "new"]
        if new_strategies:
            focus.append(
                f"Validate new strategies with more data: "
                f"{', '.join(s.name for s in new_strategies)}"
            )
        
        # Focus on uncertainties
        if uncertainties:
            focus.append("Address flagged uncertainties before scaling positions")
        
        # Focus on best performing
        if strategies:
            best = strategies[0]
            focus.append(f"Scale up best performing strategy: {best.name}")
        
        return focus
    
    def format_markdown(self, review: WeeklyReview) -> str:
        """Format review as Markdown."""
        lines = []
        
        # Header
        lines.append("═" * 80)
        lines.append(f"MECOS WEEKLY REVIEW — Week of {review.week_start} to {review.week_end}")
        lines.append("═" * 80)
        lines.append("")
        
        # Performance Summary
        lines.append("## 📊 WEEKLY PERFORMANCE")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Starting Equity | ${review.starting_equity:,.2f} |")
        lines.append(f"| Ending Equity | ${review.ending_equity:,.2f} |")
        lines.append(f"| Weekly P&L | ${review.weekly_pnl:+,.2f} |")
        lines.append(f"| Weekly Return | {review.weekly_return:+.2%} |")
        lines.append(f"| Best Day | {review.best_day[0]}: ${review.best_day[1]:+,.2f} |")
        lines.append(f"| Worst Day | {review.worst_day[0]}: ${review.worst_day[1]:+,.2f} |")
        lines.append("")
        
        # Key Metrics
        lines.append("## 📈 KEY METRICS")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Total Trades | {review.total_trades} |")
        lines.append(f"| Win Rate | {review.win_rate:.1%} |")
        lines.append(f"| Sharpe Ratio | {review.sharpe_ratio:.2f} |")
        lines.append(f"| Max Drawdown | {review.max_drawdown:.1%} |")
        lines.append("")
        
        # Strategy Analysis
        if review.strategies:
            lines.append("## 📈 STRATEGY ANALYSIS")
            lines.append("")
            lines.append("| Strategy | Win Rate | Avg Win | Avg Loss | Profit Factor | Status |")
            lines.append("|----------|----------|---------|----------|---------------|--------|")
            
            for strategy in review.strategies:
                lines.append(
                    f"| {strategy.name} | {strategy.win_rate:.1%} | "
                    f"${strategy.avg_win:+,.2f} | ${strategy.avg_loss:+,.2f} | "
                    f"{strategy.profit_factor:.2f} | {strategy.status} |"
                )
            
            lines.append("")
        
        # Discoveries
        if review.discoveries:
            lines.append("## 🎓 WHAT MECOS LEARNED THIS WEEK")
            lines.append("")
            for discovery in review.discoveries:
                lines.append(f"✓ {discovery}")
            lines.append("")
        
        # System Improvements
        if review.improvements:
            lines.append("## 🔧 SYSTEM IMPROVEMENTS")
            lines.append("")
            for improvement in review.improvements:
                lines.append(f"✓ {improvement.description}")
            lines.append("")
        
        # Uncertainties
        if review.uncertainties:
            lines.append("## ⚠️ UNCERTAINTIES & LIMITATIONS")
            lines.append("")
            for uncertainty in review.uncertainties:
                lines.append(f"⚠ {uncertainty}")
            lines.append("")
        
        # Next Week Focus
        if review.next_week_focus:
            lines.append("## 🎯 NEXT WEEK FOCUS")
            lines.append("")
            for i, focus in enumerate(review.next_week_focus, 1):
                lines.append(f"{i}. {focus}")
            lines.append("")
        
        # Footer
        lines.append("═" * 80)
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("═" * 80)
        
        return "\n".join(lines)
    
    def format_json(self, review: WeeklyReview) -> str:
        """Format review as JSON."""
        data = {
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
            "strategies": [
                {
                    "name": s.name,
                    "win_rate": s.win_rate,
                    "avg_win": s.avg_win,
                    "avg_loss": s.avg_loss,
                    "profit_factor": s.profit_factor,
                    "total_trades": s.total_trades,
                    "total_pnl": s.total_pnl,
                    "status": s.status,
                }
                for s in review.strategies
            ],
            "improvements": [
                {
                    "description": i.description,
                    "impact": i.impact,
                    "magnitude": i.impact_magnitude,
                }
                for i in review.improvements
            ],
            "discoveries": review.discoveries,
            "uncertainties": review.uncertainties,
            "next_week_focus": review.next_week_focus,
            "generated_at": datetime.now().isoformat(),
        }
        
        return json.dumps(data, indent=2)
    
    def save_review(
        self,
        review: WeeklyReview,
        formats: List[str] = None,
    ) -> Dict[str, str]:
        """Save review in multiple formats."""
        if formats is None:
            formats = ["markdown", "json"]
        
        saved_files = {}
        
        if "markdown" in formats:
            md_path = self.output_dir / f"week_{review.week_end}_review.md"
            with open(md_path, 'w') as f:
                f.write(self.format_markdown(review))
            saved_files["markdown"] = str(md_path)
            logger.info(f"Saved Markdown review: {md_path}")
        
        if "json" in formats:
            json_path = self.output_dir / f"week_{review.week_end}_review.json"
            with open(json_path, 'w') as f:
                f.write(self.format_json(review))
            saved_files["json"] = str(json_path)
            logger.info(f"Saved JSON review: {json_path}")
        
        return saved_files


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    # Mock instances
    class MockTracker:
        current_equity = 55000
        
        def calculate_daily_pnl(self, date):
            from performance_tracker import DailyMetrics
            return DailyMetrics(
                date=date,
                starting_equity=50000,
                ending_equity=55000,
                daily_pnl=1000,
                daily_return=0.02,
                trades_count=20,
                wins=12,
                losses=8,
                win_rate=0.6,
                avg_win=150,
                avg_loss=-100,
                largest_win=500,
                largest_loss=-300,
            )
        
        def get_performance_metrics(self, lookback_days):
            from performance_tracker import PerformanceMetrics
            return PerformanceMetrics(
                sharpe_ratio=1.45,
                max_drawdown=0.032,
                win_rate=0.6,
                profit_factor=2.0,
                total_return=0.1,
                total_trades=140,
                avg_trade_pnl=71.43,
            )
        
        def get_all_trades(self):
            from performance_tracker import Trade
            from datetime import datetime
            
            return [
                Trade("BTC/USD", 65000, 65100, 1, 100, datetime.now().isoformat(), "BUY", "momentum", 0.85),
                Trade("ETH/USD", 3400, 3450, 1, 50, datetime.now().isoformat(), "BUY", "mean_reversion", 0.70),
            ]
    
    class MockFlagger:
        def get_approval_statistics(self):
            return {
                "total_plans_scored": 100,
                "approved_count": 75,
                "rejected_count": 25,
                "approval_rate": 0.75,
                "avg_confidence": 0.78,
                "min_confidence": 0.45,
                "max_confidence": 0.98,
            }
        
        def get_confidence_distribution(self):
            return {
                "very_low": 5,
                "low": 10,
                "medium": 20,
                "high": 40,
                "very_high": 25,
            }
    
    tracker = MockTracker()
    flagger = MockFlagger()
    
    generator = WeeklyReviewGenerator(tracker, flagger)
    
    review = generator.generate_review(
        discoveries=[
            "BTC shows stronger momentum on Tuesdays",
            "Fed announcements create 2-hour volatility spike",
        ],
        improvements=[
            SystemImprovement(
                description="Evolved new trading signal: 4-hour RSI divergence",
                impact="positive",
                impact_magnitude=0.15,
                timestamp=datetime.now().isoformat(),
            ),
        ],
    )
    
    files = generator.save_review(review)
    print(f"\nReviews saved:")
    for fmt, path in files.items():
        print(f"  {fmt}: {path}")
