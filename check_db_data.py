import sqlite3
from pathlib import Path
conn = sqlite3.connect('data/trading.db')
conn.row_factory = sqlite3.Row

print('=== ORDERS (last 10) ===')
orders = conn.execute('SELECT * FROM orders ORDER BY id DESC LIMIT 10').fetchall()
for o in orders:
    print(f"  {o['symbol']:10s} {o['side']:4s} size={float(o['size'] or 0):.4f} price= status={o['status']} ts={str(o['timestamp'])[:19]}")

print('\n=== FILLS (last 10) ===')
fills = conn.execute('SELECT * FROM fills ORDER BY id DESC LIMIT 10').fetchall()
for f in fills:
    print(f"  {f['symbol']:10s} size={float(f['size'] or 0):.4f} price= ts={str(f['timestamp'])[:19]}")

print('\n=== PORTFOLIO SNAPSHOTS (last 5) ===')
snaps = conn.execute('SELECT * FROM portfolio_snapshots ORDER BY id DESC LIMIT 5').fetchall()
for s in snaps:
    print(f"  equity= cash= ts={str(s['timestamp'])[:19]}")

conn.close()
