import sqlite3

conn = sqlite3.connect("data/trading.db")
cur = conn.cursor()

# List tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print("Tables:", tables)

# Show schema + recent rows for each table
for t in tables:
    cur.execute(f"PRAGMA table_info({t})")
    cols = [(r[1], r[2]) for r in cur.fetchall()]
    print(f"\n=== {t} ===")
    print(f"  Columns: {cols}")
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    cnt = cur.fetchone()[0]
    print(f"  Row count: {cnt}")
    if cnt > 0:
        cur.execute(f"SELECT * FROM {t} ORDER BY rowid DESC LIMIT 3")
        for row in cur.fetchall():
            print(f"  {row}")

conn.close()
