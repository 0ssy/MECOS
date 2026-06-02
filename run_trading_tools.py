import argparse
import json
from pathlib import Path

from trading.events_calendar import EventsCalendar
from trading.pipeline_runner import PipelineRunner
from trading.screener import StockScreener
from trading.terminal_ui import render_signal_dashboard


def _load_bars(path: str):
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("Bars file must be a JSON list.")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="MECOS trading utility toolkit")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_screen = sub.add_parser("screen", help="Screen stocks by strategy")
    p_screen.add_argument("--tickers", nargs="+", required=True)
    p_screen.add_argument("--strategy", default="value", choices=["value", "growth", "momentum"])

    p_pipe = sub.add_parser("pipeline", help="Run a JSON strategy pipeline on bars")
    p_pipe.add_argument("--config", required=True, help="Path to pipeline JSON")
    p_pipe.add_argument("--bars", required=True, help="Path to bars JSON (list of OHLCV dicts)")

    p_cal = sub.add_parser("calendar", help="Fetch earnings and macro events")
    p_cal.add_argument("--tickers", nargs="*", default=[])

    p_dash = sub.add_parser("dashboard", help="Render dashboard from decisions JSON")
    p_dash.add_argument("--decisions", required=True, help="Path to decisions JSON object")

    args = parser.parse_args()

    if args.cmd == "screen":
        out = StockScreener().screen(args.tickers, strategy=args.strategy)
        print(json.dumps(out, indent=2, default=str))
        return

    if args.cmd == "pipeline":
        runner = PipelineRunner()
        config = runner.load(args.config)
        bars = _load_bars(args.bars)
        out = runner.run(config, bars)
        print(json.dumps(out, indent=2, default=str))
        return

    if args.cmd == "calendar":
        cal = EventsCalendar()
        out = {
            "earnings": cal.earnings_dates(args.tickers),
            "economic_events": cal.economic_events(),
        }
        print(json.dumps(out, indent=2, default=str))
        return

    if args.cmd == "dashboard":
        decisions = json.loads(Path(args.decisions).read_text(encoding="utf-8"))
        if not isinstance(decisions, dict):
            raise ValueError("Decisions file must be a JSON object keyed by symbol.")
        print(render_signal_dashboard(decisions))
        return


if __name__ == "__main__":
    main()
