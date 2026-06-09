import sqlite3
from pathlib import Path
conn = sqlite3.connect('data/trading.db')
conn.row_factory = sqlite3.Row
trades = conn.execute(
    "SELECT symbol, side, entry_price, exit_price, pnl, holding_seconds, entry_time, exit_time FROM trades WHERE status='CLOSED' ORDER BY timestamp DESC LIMIT 10"
).fetchall()
for t in trades:
    print(f"{t['symbol']:10s} entry= exit= pnl= hold={float(t['holding_seconds'] or 0):.0f}s")
conn.close()
