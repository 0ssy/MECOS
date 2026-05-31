"""
DailyReportGenerator — Automated Daily P&L Reporting (MECOS v3.0 Phase 2)

Generates formatted daily P&L summaries with trade details, metrics, and discoveries.
Outputs as Markdown, HTML, and JSON for multi-channel distribution.

Location: reporting/daily_report_generator.py
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DailyReport:
    """Complete daily report data."""
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
    trades: List[Dict] = None
    discoveries: List[str] = None
    
    def __post_init__(self):
        if self.trades is None:
            self.trades = []
        if self.discoveries is None:
            self.discoveries = []


class DailyReportGenerator:
    """
    Generate daily P&L reports with multiple output formats.
    
    Responsibilities:
    - Collect daily performance data
    - Format as Markdown, HTML, JSON
    - Include trade details and discoveries
    - Support multi-channel distribution
    """
    
    def __init__(
        self,
        performance_tracker,
        output_dir: str = "reports/daily",
        goal_equity: float = 60000.0,
    ):
        """
        Initialize DailyReportGenerator.
        
        Args:
            performance_tracker: PerformanceTracker instance
            output_dir: Directory to save reports
            goal_equity: Target equity for progress calculation
        """
        self.tracker = performance_tracker
        self.output_dir = Path(output_dir)
        self.goal_equity = goal_equity
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"DailyReportGenerator initialized")
        logger.info(f"  Output directory: {self.output_dir}")
    
    def generate_report(
        self,
        date: Optional[str] = None,
        discoveries: Optional[List[str]] = None,
    ) -> DailyReport:
        """
        Generate complete daily report.
        
        Args:
            date: Report date (YYYY-MM-DD). If None, uses today.
            discoveries: List of discoveries made today
        
        Returns:
            DailyReport object
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        if discoveries is None:
            discoveries = []
        
        # Get daily metrics
        daily_metrics = self.tracker.calculate_daily_pnl(date)
        
        # Get performance metrics
        perf_metrics = self.tracker.get_performance_metrics(lookback_days=30)
        
        # Get progress
        progress = self.tracker.get_progress_to_goal()
        
        # Get trades for the day
        all_trades = self.tracker.get_all_trades()
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
            for t in all_trades
            if t.timestamp.startswith(date)
        ]
        
        report = DailyReport(
            date=date,
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
            sharpe_ratio=perf_metrics.sharpe_ratio,
            max_drawdown=perf_metrics.max_drawdown,
            goal_equity=self.goal_equity,
            progress_percent=progress["progress_percent"],
            trades=today_trades,
            discoveries=discoveries,
        )
        
        return report
    
    def format_markdown(self, report: DailyReport) -> str:
        """Format report as Markdown."""
        lines = []
        
        # Header
        lines.append("═" * 70)
        lines.append(f"MECOS DAILY REPORT — {report.date}")
        lines.append("═" * 70)
        lines.append("")
        
        # Performance Summary
        lines.append("## 📊 PERFORMANCE SUMMARY")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Starting Equity | ${report.starting_equity:,.2f} |")
        lines.append(f"| Ending Equity | ${report.ending_equity:,.2f} |")
        lines.append(f"| Daily P&L | ${report.daily_pnl:+,.2f} |")
        lines.append(f"| Daily Return | {report.daily_return:+.2%} |")
        lines.append("")
        
        # Key Metrics
        lines.append("## 📈 KEY METRICS")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Sharpe Ratio | {report.sharpe_ratio:.2f} |")
        lines.append(f"| Max Drawdown | {report.max_drawdown:.1%} |")
        lines.append(f"| Win Rate | {report.win_rate:.1%} ({report.wins}/{report.trades_count}) |")
        lines.append(f"| Avg Win | ${report.avg_win:+,.2f} |")
        lines.append(f"| Avg Loss | ${report.avg_loss:+,.2f} |")
        lines.append("")
        
        # Progress to Goal
        lines.append("## 🎯 PROGRESS TO GOAL")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Target | ${report.goal_equity:,.2f} |")
        lines.append(f"| Current | ${report.ending_equity:,.2f} |")
        lines.append(f"| Remaining | ${max(0, report.goal_equity - report.ending_equity):,.2f} |")
        lines.append(f"| Progress | {report.progress_percent:.1f}% |")
        lines.append("")
        
        # Progress bar
        bar_length = 40
        filled = int(bar_length * report.progress_percent / 100)
        bar = "█" * filled + "░" * (bar_length - filled)
        lines.append(f"```")
        lines.append(f"[{bar}] {report.progress_percent:.1f}%")
        lines.append(f"```")
        lines.append("")
        
        # Trades
        if report.trades:
            lines.append("## 📋 TRADES EXECUTED TODAY")
            lines.append("")
            lines.append("| # | Symbol | Type | Entry | Exit | Qty | P&L | Strategy | Conf |")
            lines.append("|---|--------|------|-------|------|-----|-----|----------|------|")
            
            for i, trade in enumerate(report.trades, 1):
                pnl_symbol = "✓" if trade["pnl"] > 0 else "✗"
                lines.append(
                    f"| {i} | {trade['symbol']} | {trade['type']} | "
                    f"${trade['entry']:.2f} | ${trade['exit']:.2f} | "
                    f"{trade['quantity']} | ${trade['pnl']:+.2f} {pnl_symbol} | "
                    f"{trade['strategy']} | {trade['confidence']:.0%} |"
                )
            
            lines.append("")
        
        # Discoveries
        if report.discoveries:
            lines.append("## 🔍 DISCOVERIES TODAY")
            lines.append("")
            for discovery in report.discoveries:
                lines.append(f"✓ {discovery}")
            lines.append("")
        
        # Footer
        lines.append("═" * 70)
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("═" * 70)
        
        return "\n".join(lines)
    
    def format_html(self, report: DailyReport) -> str:
        """Format report as HTML."""
        trades_section = ""
        if report.trades:
            trade_rows = []
            for i, trade in enumerate(report.trades, 1):
                pnl_class = "positive" if float(trade["pnl"]) > 0 else "negative"
                trade_rows.append(
                    f"<tr><td>{i}</td><td>{trade['symbol']}</td><td>{trade['type']}</td>"
                    f"<td>${trade['entry']:.2f}</td><td>${trade['exit']:.2f}</td>"
                    f"<td>{trade['quantity']}</td><td class=\"{pnl_class}\">${trade['pnl']:+,.2f}</td>"
                    f"<td>{trade['strategy']}</td><td>{trade['confidence']:.0%}</td></tr>"
                )
            trades_section = (
                "<h2>Trades Executed Today</h2>\n"
                "<table>\n"
                "<tr><th>#</th><th>Symbol</th><th>Type</th><th>Entry</th><th>Exit</th>"
                "<th>Qty</th><th>P&L</th><th>Strategy</th><th>Conf</th></tr>\n"
                f"{''.join(trade_rows)}\n"
                "</table>"
            )

        discoveries_section = ""
        if report.discoveries:
            discoveries_section = "<h2>Discoveries Today</h2>\n" + "".join(
                f"<div class=\"discovery\">✓ {discovery}</div>" for discovery in report.discoveries
            )

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>MECOS Daily Report - {report.date}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
            color: #333;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
            margin-bottom: 15px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #3498db;
            color: white;
            font-weight: bold;
        }}
        tr:hover {{
            background-color: #f9f9f9;
        }}
        .positive {{
            color: #27ae60;
            font-weight: bold;
        }}
        .negative {{
            color: #e74c3c;
            font-weight: bold;
        }}
        .progress-bar {{
            width: 100%;
            height: 30px;
            background-color: #ecf0f1;
            border-radius: 4px;
            overflow: hidden;
            margin: 10px 0;
        }}
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #27ae60, #2ecc71);
            width: {report.progress_percent}%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 14px;
        }}
        .metric-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .metric-card {{
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 4px;
            border-left: 4px solid #3498db;
        }}
        .metric-label {{
            font-size: 12px;
            color: #7f8c8d;
            text-transform: uppercase;
            margin-bottom: 5px;
        }}
        .metric-value {{
            font-size: 20px;
            font-weight: bold;
            color: #2c3e50;
        }}
        .discovery {{
            background-color: #e8f8f5;
            padding: 10px 15px;
            border-left: 4px solid #27ae60;
            margin-bottom: 10px;
            border-radius: 4px;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            text-align: center;
            color: #7f8c8d;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 MECOS Daily Report — {report.date}</h1>
        
        <h2>Performance Summary</h2>
        <div class="metric-grid">
            <div class="metric-card">
                <div class="metric-label">Starting Equity</div>
                <div class="metric-value">${report.starting_equity:,.0f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Ending Equity</div>
                <div class="metric-value">${report.ending_equity:,.0f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Daily P&L</div>
                <div class="metric-value {'positive' if report.daily_pnl > 0 else 'negative'}">${report.daily_pnl:+,.0f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Daily Return</div>
                <div class="metric-value {'positive' if report.daily_return > 0 else 'negative'}">{report.daily_return:+.2%}</div>
            </div>
        </div>
        
        <h2>Key Metrics</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Sharpe Ratio</td>
                <td>{report.sharpe_ratio:.2f}</td>
            </tr>
            <tr>
                <td>Max Drawdown</td>
                <td>{report.max_drawdown:.1%}</td>
            </tr>
            <tr>
                <td>Win Rate</td>
                <td>{report.win_rate:.1%} ({report.wins}/{report.trades_count})</td>
            </tr>
            <tr>
                <td>Avg Win</td>
                <td class="positive">${report.avg_win:+,.2f}</td>
            </tr>
            <tr>
                <td>Avg Loss</td>
                <td class="negative">${report.avg_loss:+,.2f}</td>
            </tr>
        </table>
        
        <h2>Progress to Goal</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Target</td>
                <td>${report.goal_equity:,.0f}</td>
            </tr>
            <tr>
                <td>Current</td>
                <td>${report.ending_equity:,.0f}</td>
            </tr>
            <tr>
                <td>Remaining</td>
                <td>${max(0, report.goal_equity - report.ending_equity):,.0f}</td>
            </tr>
            <tr>
                <td>Progress</td>
                <td>{report.progress_percent:.1f}%</td>
            </tr>
        </table>
        <div class="progress-bar">
            <div class="progress-fill">{report.progress_percent:.1f}%</div>
        </div>
        
        {trades_section}
        
        {discoveries_section}
        
        <div class="footer">
            Generated: {datetime.now().isoformat()}
        </div>
    </div>
</body>
</html>
"""
        return html
    
    def format_json(self, report: DailyReport) -> str:
        """Format report as JSON."""
        data = {
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
        }
        
        return json.dumps(data, indent=2)
    
    def save_report(self, report: DailyReport, formats: List[str] = None) -> Dict[str, str]:
        """
        Save report in multiple formats.
        
        Args:
            report: DailyReport object
            formats: List of formats to save (markdown, html, json)
        
        Returns:
            Dictionary of {format: filepath}
        """
        if formats is None:
            formats = ["markdown", "html", "json"]
        
        saved_files = {}
        
        if "markdown" in formats:
            md_path = self.output_dir / f"{report.date}_report.md"
            with open(md_path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(self.format_markdown(report))
            saved_files["markdown"] = str(md_path)
            logger.info(f"Saved Markdown report: {md_path}")
        
        if "html" in formats:
            html_path = self.output_dir / f"{report.date}_report.html"
            with open(html_path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(self.format_html(report))
            saved_files["html"] = str(html_path)
            logger.info(f"Saved HTML report: {html_path}")
        
        if "json" in formats:
            json_path = self.output_dir / f"{report.date}_report.json"
            with open(json_path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(self.format_json(report))
            saved_files["json"] = str(json_path)
            logger.info(f"Saved JSON report: {json_path}")
        
        return saved_files


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    # Mock performance tracker
    class MockTracker:
        def calculate_daily_pnl(self, date):
            from performance_tracker import DailyMetrics
            return DailyMetrics(
                date=date,
                starting_equity=50000,
                ending_equity=51250,
                daily_pnl=1250,
                daily_return=0.025,
                trades_count=24,
                wins=15,
                losses=9,
                win_rate=0.625,
                avg_win=125.50,
                avg_loss=-95.30,
                largest_win=500,
                largest_loss=-300,
            )
        
        def get_performance_metrics(self, lookback_days):
            from performance_tracker import PerformanceMetrics
            return PerformanceMetrics(
                sharpe_ratio=1.45,
                max_drawdown=0.032,
                win_rate=0.625,
                profit_factor=2.14,
                total_return=0.025,
                total_trades=24,
                avg_trade_pnl=52.08,
            )
        
        def get_progress_to_goal(self):
            return {
                "current_equity": 51250,
                "goal_equity": 60000,
                "remaining": 8750,
                "progress_percent": 85.4,
                "days_to_goal": 7,
            }
        
        def get_all_trades(self):
            from performance_tracker import Trade
            return [
                Trade("BTC/USD", 65200, 65450, 0.1, 250, datetime.now().isoformat(), "BUY", "momentum", 0.87),
                Trade("ETH/USD", 3450, 3420, 1.0, 150, datetime.now().isoformat(), "SELL", "mean_reversion", 0.72),
            ]
    
    tracker = MockTracker()
    generator = DailyReportGenerator(tracker, goal_equity=60000)
    
    report = generator.generate_report(
        discoveries=[
            "Discovered correlation between BTC volatility and Fed announcements",
            "Learned new pattern: 15-min RSI divergence predicts reversals",
        ]
    )
    
    files = generator.save_report(report)
    print(f"\nReports saved:")
    for fmt, path in files.items():
        print(f"  {fmt}: {path}")
