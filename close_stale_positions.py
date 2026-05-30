"""
close_stale_positions.py
One-time script to close stale positions from previous sessions
that are blocking new trades due to position size limits.

Run once: python close_stale_positions.py
"""
import json
import sqlite3
from pathlib import Path

DB_PATH       = Path("data/trading.db")
SNAPSHOT_PATH = Path("data/portfolio_snapshot.json")

def main():
    print("\nMECOS Position Cleanup")
    print("=" * 40)

    # Show current snapshot
    if SNAPSHOT_PATH.exists():
        snap = json.loads(SNAPSHOT_PATH.read_text())
        positions = snap.get("positions", {})
        cash      = snap.get("cash", 0)
        equity    = snap.get("total_value", snap.get("equity", 0))
        print(f"Current snapshot: cash=${cash:.2f} equity=${equity:.2f} positions={len(positions)}")
        if positions:
            print("Open positions:")
            for sym, pos in positions.items():
                size = pos.get("size", 0)
                avg  = pos.get("avg_price", 0)
                print(f"  {sym:<12} size={size:.4f} avg_price=${avg:.4f}")
        print()

    choice = input("Close ALL open positions and reset to cash-only? (yes/no): ").strip().lower()
    if choice != "yes":
        print("Cancelled.")
        return

    # Reset portfolio snapshot to cash only
    if SNAPSHOT_PATH.exists():
        snap = json.loads(SNAPSHOT_PATH.read_text())
        current_equity = float(snap.get("total_value", snap.get("equity", 10000.0)))
    else:
        current_equity = 10000.0

    clean_snapshot = {
        "cash":        current_equity,
        "total_value": current_equity,
        "equity":      current_equity,
        "positions":   {},
        "timestamp":   __import__("time").time(),
    }
    SNAPSHOT_PATH.write_text(json.dumps(clean_snapshot, indent=2))
    print(f"[OK] Portfolio reset: cash=${current_equity:.2f}, 0 positions")

    # Also clear position records from DB if it exists
    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            # Check what tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            print(f"     DB tables: {tables}")
            if "positions" in tables:
                cursor.execute("DELETE FROM positions")
                conn.commit()
                print(f"[OK] Cleared positions table in {DB_PATH}")
            conn.close()
        except Exception as e:
            print(f"[WARN] DB cleanup failed: {e}")

    print("\nDone. Restart MECOS — it will start with full cash and no open positions.")
    print("New trades can now execute without 'Position size exceeded' errors.")

if __name__ == "__main__":
    main()
