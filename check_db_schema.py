import sqlite3
from pathlib import Path
conn = sqlite3.connect('data/trading.db')
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
for t in tables:
    print(f'\nTable: {t[0]}')
    cols = conn.execute(f"PRAGMA table_info({t[0]})").fetchall()
    for c in cols:
        print(f'  {c[1]} ({c[2]})')
conn.close()
