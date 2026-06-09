"""
MECOS Performance Dashboard
Run anytime: python performance_dashboard.py
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime


def show_dashboard():
    print("\n" + "=" * 60)
    print("MECOS TRADING PERFORMANCE DASHBOARD")
    print("=" * 60)

    db_path = Path("data/trading.db")
    if not db_path.exists():
        print("No trading database found")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # ── Portfolio ────────────────────────────────────────────
    try:
        row = conn.execute(
            "SELECT * FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        if row:
            equity  = float(row["total_value"])
            cash    = float(row["cash"])
            initial = 10_000.0
            pnl     = equity - initial
            pnl_pct = (pnl / initial) * 100
            print(f"\nPORTFOLIO:")
            print(f"  Equity:    ${equity:,.2f}")
            print(f"  Cash:      ${cash:,.2f}")
            print(f"  Total PnL: ${pnl:+,.2f} ({pnl_pct:+.2f}%)")
        else:
            print("\nPORTFOLIO: No snapshots yet")
    except Exception as e:
        print(f"Portfolio error: {e}")

    # ── Open positions ───────────────────────────────────────
    try:
        state     = json.loads(Path("data/state.json").read_text())
        positions = state.get("open_positions", {})
        print(f"\nOPEN POSITIONS ({len(positions)}):")
        for sym, pos in positions.items():
            entry  = float(pos.get("entry",        0))
            size   = float(pos.get("size",         0))
            stop   = float(pos.get('stop', 0) or 0)
            tp     = float(pos.get('take_profit', 0) or 0)
            value  = entry * size
            opened = str(pos.get("opened_at", ""))[:19]
            pnl_pct_pos = ((stop / entry) - 1) * 100 if entry and stop else 0
            print(f"  {sym:10s}  entry=${entry:>10,.2f}  value=${value:>8,.2f}"
                  f"  stop=${stop:>10,.2f}  tp=${tp:>10,.2f}  opened={opened}")
    except Exception as e:
        print(f"Positions error: {e}")

    # ── Trade history ────────────────────────────────────────
    try:
        trades = conn.execute(
            "SELECT * FROM trades ORDER BY timestamp DESC"
        ).fetchall()

        closed = [t for t in trades
                  if t["exit_price"] and float(t["exit_price"] or 0) > 0]
        wins   = [t for t in closed if float(t["pnl"] or 0) > 0]
        losses = [t for t in closed if float(t["pnl"] or 0) <= 0]

        print(f"\nTRADE HISTORY:")
        print(f"  Total trades:  {len(trades)}")
        print(f"  Closed trades: {len(closed)}")

        if closed:
            total_pnl = sum(float(t["pnl"] or 0) for t in closed)
            win_rate  = len(wins) / len(closed) * 100
            avg_win   = sum(float(t["pnl"] or 0) for t in wins)   / max(len(wins),   1)
            avg_loss  = sum(float(t["pnl"] or 0) for t in losses) / max(len(losses), 1)
            pf        = abs(avg_win / avg_loss) if avg_loss != 0 else 0
            avg_hold  = sum(float(t["holding_seconds"] or 0) for t in closed) / len(closed)
            print(f"  Win rate:      {win_rate:.1f}%")
            print(f"  Total PnL:     ${total_pnl:+,.2f}")
            print(f"  Avg win:       ${avg_win:+,.2f}")
            print(f"  Avg loss:      ${avg_loss:+,.2f}")
            print(f"  Profit factor: {pf:.2f}")
            print(f"  Avg hold time: {avg_hold/60:.1f} min")
        else:
            print("  No closed trades yet — positions still open")

        if trades:
            print(f"\nRECENT TRADES (last 10):")
            for t in list(trades)[:10]:
                pnl    = float(t["pnl"] or 0)
                sym    = str(t["symbol"])
                side   = str(t["side"])
                status = str(t["status"] or "open")
                ts     = str(t["timestamp"])[:19]
                ep     = float(t["entry_price"] or 0)
                xp     = float(t["exit_price"]  or 0)
                exit_str = f"→ ${xp:,.2f}" if xp else "  (open)"
                print(f"  {ts}  {sym:10s}  {side:4s}  "
                      f"${ep:,.2f} {exit_str}  pnl=${pnl:+,.2f}  [{status}]")

    except Exception as e:
        print(f"Trades error: {e}")

    # ── Signals summary ──────────────────────────────────────
    try:
        sig_count = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
        last_sig  = conn.execute(
            "SELECT symbol, signal, confidence, timestamp FROM signals ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        print(f"\nSIGNALS: {sig_count} total")
        if last_sig:
            print(f"  Last: {last_sig['timestamp'][:19]}  "
                  f"{last_sig['symbol']}  {last_sig['signal']}  "
                  f"conf={float(last_sig['confidence']):.3f}")
    except Exception as e:
        print(f"Signals error: {e}")

    # ── Performance metrics ───────────────────────────────────
    try:
        daily = conn.execute(
            "SELECT * FROM performance_daily_metrics ORDER BY date DESC LIMIT 7"
        ).fetchall()
        if daily:
            print(f"\nDAILY PERFORMANCE (last 7 days):")
            for d in daily:
                ret = float(d["daily_return"] or 0) * 100
                eq  = float(d["ending_equity"] or 0)
                print(f"  {d['date']}  equity=${eq:,.2f}  return={ret:+.2f}%")
    except Exception as e:
        print(f"Daily metrics error: {e}")

    conn.close()
    print("\n" + "=" * 60)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    show_dashboard()


