import json
from pathlib import Path
from datetime import datetime


def show_dashboard():
    print("\n" + "=" * 60)
    print("MECOS TRADING PERFORMANCE DASHBOARD")
    print("=" * 60)

    try:
        snapshot = json.loads(Path("data/portfolio_snapshot.json").read_text())
        equity = float(snapshot.get("equity", 0))
        cash = float(snapshot.get("cash", 0))
        initial = 10000.0
        pnl = equity - initial
        pnl_pct = (pnl / initial) * 100
        print("\nPORTFOLIO:")
        print(f"  Equity:    ${equity:,.2f}")
        print(f"  Cash:      ${cash:,.2f}")
        print(f"  Total PnL: ${pnl:+,.2f} ({pnl_pct:+.2f}%)")
    except Exception as e:
        print(f"Portfolio error: {e}")

    try:
        state = json.loads(Path("data/state.json").read_text())
        positions = state.get("open_positions", {})
        print(f"\nOPEN POSITIONS ({len(positions)}):")
        for sym, pos in positions.items():
            entry = float(pos.get("entry", 0) or 0)
            size = float(pos.get("size", 0) or 0)
            stop = float(pos.get("stop", 0) or 0)
            tp = float(pos.get("take_profit", 0) or 0)
            value = entry * size
            opened = str(pos.get("opened_at", ""))[:19]
            print(
                f"  {sym:10s} entry=${entry:,.2f} value=${value:,.2f} "
                f"stop=${stop:,.2f} tp=${tp:,.2f} opened={opened}"
            )
    except Exception as e:
        print(f"Positions error: {e}")

    try:
        lines = Path("data/trade_journal.jsonl").read_text().strip().split("\n")
        trades = [json.loads(l) for l in lines if l.strip()]
        closed = [t for t in trades if t.get("status") == "closed" or t.get("exit_price")]
        if closed:
            wins = [t for t in closed if float(t.get("pnl", 0)) > 0]
            losses = [t for t in closed if float(t.get("pnl", 0)) <= 0]
            total_pnl = sum(float(t.get("pnl", 0)) for t in closed)
            win_rate = len(wins) / len(closed) * 100
            avg_win = sum(float(t.get("pnl", 0)) for t in wins) / max(len(wins), 1)
            avg_loss = sum(float(t.get("pnl", 0)) for t in losses) / max(len(losses), 1)
            pf = abs(avg_win / avg_loss) if avg_loss != 0 else 0
            print(f"\nTRADE HISTORY ({len(closed)} closed):")
            print(f"  Win rate:      {win_rate:.1f}%")
            print(f"  Total PnL:     ${total_pnl:+,.2f}")
            print(f"  Avg win:       ${avg_win:+,.2f}")
            print(f"  Avg loss:      ${avg_loss:+,.2f}")
            print(f"  Profit factor: {pf:.2f}")
        else:
            print("\nTRADE HISTORY: No closed trades yet — positions still open")
    except Exception as e:
        print(f"Journal error: {e}")

    print("\n" + "=" * 60)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    show_dashboard()
