#!/usr/bin/env python3
"""
sector_dashboard.py
Sector-separated performance dashboard for MECOS.
Shows crypto / equities / ETFs P&L independently so you can see
exactly where gains and losses are coming from.

Run: python sector_dashboard.py
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import json

DB_PATH = "data/trading.db"
STATE_PATH = "data/state.json"

# ── Sector classification ─────────────────────────────────────────────────────

CRYPTO  = {"BTC/USD", "ETH/USD", "SOL/USD", "AVAX/USD", "LINK/USD",
           "DOGE/USD", "ADA/USD", "BNB/USD", "XRP/USD", "DOT/USD"}
ETFS    = {"SPY", "QQQ", "IWM", "DIA", "GLD", "SLV", "TLT", "XLF",
           "XLE", "XLK", "XLV", "XLU", "ARKK", "VTI", "VOO"}
FOREX   = {"EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD",
           "NZD/USD", "USD/CAD", "EUR/GBP", "EUR/JPY"}

def classify(symbol: str) -> str:
    if symbol in CRYPTO:
        return "crypto"
    if symbol in ETFS:
        return "etf"
    if symbol in FOREX:
        return "forex"
    return "equity"


def sector_label(s: str) -> str:
    return {"crypto": "CRYPTO", "etf": "ETFs", "equity": "EQUITIES",
            "forex": "FOREX"}.get(s, s.upper())


# ── DB helpers ────────────────────────────────────────────────────────────────

def get_closed_trades(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT symbol, side, entry_price, exit_price, quantity, pnl,
               entry_time, exit_time, holding_seconds, regime
        FROM trades
        WHERE status = 'CLOSED' AND pnl IS NOT NULL
        ORDER BY entry_time
    """)
    rows = cur.fetchall()
    trades = []
    for r in rows:
        trades.append({
            "symbol":          r[0],
            "side":            r[1],
            "entry_price":     float(r[2] or 0),
            "exit_price":      float(r[3] or 0),
            "quantity":        float(r[4] or 0),
            "pnl":             float(r[5] or 0),
            "entry_time":      r[6],
            "exit_time":       r[7],
            "holding_seconds": float(r[8] or 0),
            "regime":          r[9] or "unknown",
            "sector":          classify(r[0]),
        })
    return trades


def get_open_positions():
    try:
        state = json.loads(Path(STATE_PATH).read_text())
        return state.get("open_positions", {})
    except Exception:
        return {}


def get_latest_snapshot(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT total_value, cash, timestamp
        FROM portfolio_snapshots
        ORDER BY id DESC LIMIT 1
    """)
    row = cur.fetchone()
    if not row:
        return 10000.0, 10000.0, ""
    return float(row[0] or 0), float(row[1] or 0), row[2]


# ── Stats per sector ──────────────────────────────────────────────────────────

def sector_stats(trades):
    sectors = {}
    for t in trades:
        s = t["sector"]
        if s not in sectors:
            sectors[s] = {"trades": [], "wins": 0, "losses": 0,
                          "total_pnl": 0.0, "win_pnl": 0.0, "loss_pnl": 0.0,
                          "avg_hold": 0.0}
        d = sectors[s]
        d["trades"].append(t)
        d["total_pnl"] += t["pnl"]
        if t["pnl"] > 0:
            d["wins"]    += 1
            d["win_pnl"] += t["pnl"]
        elif t["pnl"] < 0:
            d["losses"]    += 1
            d["loss_pnl"]  += t["pnl"]

    for s, d in sectors.items():
        n = len(d["trades"])
        d["n"] = n
        d["win_rate"]      = d["wins"] / n if n > 0 else 0
        d["avg_hold_min"]  = (sum(t["holding_seconds"] for t in d["trades"]) / n / 60) if n > 0 else 0
        d["avg_win"]       = d["win_pnl"]  / d["wins"]   if d["wins"]   > 0 else 0
        d["avg_loss"]      = d["loss_pnl"] / d["losses"] if d["losses"] > 0 else 0
        d["profit_factor"] = abs(d["win_pnl"] / d["loss_pnl"]) if d["loss_pnl"] != 0 else float("inf") if d["win_pnl"] > 0 else 0

    return sectors


# ── Render ────────────────────────────────────────────────────────────────────

WIDTH = 62

def bar(value, max_abs=None, width=30):
    """Simple ASCII bar, green for positive, red for negative."""
    if max_abs is None or max_abs == 0:
        max_abs = max(abs(value), 1)
    filled = int(abs(value) / max_abs * width)
    char   = "█" if value >= 0 else "▓"
    return char * filled + "·" * (width - filled)


def pnl_color(v):
    return f"+${v:,.2f}" if v >= 0 else f"-${abs(v):,.2f}"


def print_sector(name, d, open_positions):
    label = sector_label(name)
    n     = d["n"]
    pf_str = f"{d['profit_factor']:.2f}" if d["profit_factor"] != float("inf") else "∞"

    # Open positions in this sector
    open_in_sector = {
        sym: pos for sym, pos in open_positions.items()
        if classify(sym) == name
    }
    open_pnl = 0.0
    for sym, pos in open_in_sector.items():
        ep  = float(pos.get("entry", 0) or 0)
        lp  = float(pos.get("entry", ep))  # last_price not in state, use entry as proxy
        qty = float(pos.get("size", 0) or 0)
        open_pnl += (lp - ep) * qty

    print(f"\n{'═' * WIDTH}")
    print(f"  {label}  ({n} closed trades, {len(open_in_sector)} open)")
    print(f"{'─' * WIDTH}")

    # P&L bar
    max_abs = max(abs(d["total_pnl"]), 1)
    b = bar(d["total_pnl"], max_abs)
    pnl_str = pnl_color(d["total_pnl"])
    print(f"  Closed PnL   {b}  {pnl_str}")

    print(f"  Win rate     {d['win_rate']*100:5.1f}%   "
          f"({d['wins']}W / {d['losses']}L)")
    print(f"  Avg win      +${d['avg_win']:,.2f}   "
          f"Avg loss   -${abs(d['avg_loss']):,.2f}")
    print(f"  Profit fac   {pf_str}        "
          f"Avg hold  {d['avg_hold_min']:.0f}min")

    if open_in_sector:
        print(f"  Open pos     {', '.join(open_in_sector.keys())}")

        print(f"{'─' * WIDTH}")

    # Last 5 trades
    recent = sorted(d["trades"], key=lambda t: t["entry_time"] or "", reverse=True)[:5]
    for t in recent:
        ts  = (t["entry_time"] or "")[:16]
        sym = t["symbol"].ljust(9)
        p   = pnl_color(t["pnl"])
        print(f"    {ts}  {sym}  {p}")


def main():
    conn = sqlite3.connect(DB_PATH)
    trades  = get_closed_trades(conn)
    equity, cash, snap_ts = get_latest_snapshot(conn)
    open_pos = get_open_positions()

    initial  = 10_000.0
    total_pnl = equity - initial
    pnl_pct   = total_pnl / initial * 100

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"\n{'═' * WIDTH}")
    print(f"  MECOS SECTOR PERFORMANCE DASHBOARD")
    print(f"  Generated: {now}")
    print(f"{'═' * WIDTH}")
    print(f"  Equity:    ${equity:>10,.2f}")
    print(f"  Cash:      ${cash:>10,.2f}")
    print(f"  Total PnL: {pnl_color(total_pnl)} ({pnl_pct:+.2f}%)")
    print(f"  Open pos:  {len(open_pos)}")
    print(f"{'─' * WIDTH}")
    print(f"  All closed trades: {len(trades)}")

    stats = sector_stats(trades)

    # Print in order: crypto, equity, etf, forex
    for sector in ("crypto", "equity", "etf", "forex"):
        if sector in stats:
            print_sector(sector, stats[sector], open_pos)

    # Summary comparison table
    print(f"\n{'═' * WIDTH}")
    print(f"  SECTOR COMPARISON")
    print(f"{'─' * WIDTH}")
    print(f"  {'Sector':<12} {'Trades':>6} {'PnL':>10} {'WinRate':>8} {'ProfFac':>8}")
    print(f"  {'─'*12} {'─'*6} {'─'*10} {'─'*8} {'─'*8}")

    for sector in ("crypto", "equity", "etf", "forex"):
        if sector not in stats:
            continue
        d = stats[sector]
        pf_str = f"{d['profit_factor']:.2f}" if d["profit_factor"] != float("inf") else "  ∞"
        pnl_s  = f"${d['total_pnl']:+,.2f}"
        print(f"  {sector_label(sector):<12} {d['n']:>6} {pnl_s:>10} "
              f"{d['win_rate']*100:>7.1f}% {pf_str:>8}")

    print(f"{'═' * WIDTH}")
    print(f"  NOTE: 'Closed PnL' reflects realised trades only.")
    print(f"  Open position marks are approximated from entry price.")
    print(f"{'═' * WIDTH}\n")

    conn.close()


if __name__ == "__main__":
    main()