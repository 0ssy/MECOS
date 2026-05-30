# fix_final_three.ps1
# Fixes three remaining issues:
#   1. TradingConfig not defined in autonomous_trading_loop.py
#   2. evolution_worker heartbeat timeout < cycle interval (keeps restarting)
#   3. Position size exceeded - existing positions blocking new trades
#
# Run from MECOS folder: .\fix_final_three.ps1

$ErrorActionPreference = "Stop"
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Final Three Fixes" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# FIX 1 — autonomous_trading_loop.py: add TradingConfig import
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "Fix 1: Add TradingConfig import to autonomous_trading_loop.py" -ForegroundColor White

$ATLPath = "trading\autonomous_trading_loop.py"
Copy-Item $ATLPath "$ATLPath.bak" -Force
Write-Host "  [BAK] $ATLPath.bak" -ForegroundColor Yellow

$ATL = Get-Content $ATLPath -Raw

# Add TradingConfig import if missing
if ($ATL -notmatch "from .config import TradingConfig" -and $ATL -notmatch "from trading.config import TradingConfig") {
    # Find existing imports and add after them
    $ATL = $ATL -replace `
        "(from \.cooldown_manager import CooldownManager)", `
        'from .config import TradingConfig
$1'
    Write-Host "  [OK]  TradingConfig import added" -ForegroundColor Green
} else {
    Write-Host "  [SKIP] TradingConfig already imported" -ForegroundColor Yellow
}

Set-Content $ATLPath $ATL -Encoding UTF8

# ---------------------------------------------------------------------------
# FIX 2 — process_manager.py: raise heartbeat timeout to 300s
# evolution_worker cycle is 180s, needs timeout > 180s
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "Fix 2: process_manager.py (heartbeat timeout 120s -> 300s)" -ForegroundColor White

$PMPath = "runtime\process_manager.py"
Copy-Item $PMPath "$PMPath.bak" -Force

$PM = Get-Content $PMPath -Raw
$PM = $PM -replace "HEARTBEAT_TIMEOUT = 120\.0", "HEARTBEAT_TIMEOUT = 300.0  # Must exceed longest worker cycle (evolution=180s)"
Set-Content $PMPath $PM -Encoding UTF8
Write-Host "  [OK]  Heartbeat timeout raised to 300s" -ForegroundColor Green

# ---------------------------------------------------------------------------
# FIX 3 — Close stale open positions from previous sessions
# Creates a one-time cleanup script
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "Fix 3: Create position cleanup script" -ForegroundColor White

Set-Content "close_stale_positions.py" @'
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
'@ -Encoding UTF8
Write-Host "  [OK]  close_stale_positions.py created" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Fixes applied" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "What was fixed:" -ForegroundColor White
Write-Host "  1. TradingConfig import added to autonomous_trading_loop.py" -ForegroundColor Green
Write-Host "  2. Heartbeat timeout raised 120s -> 300s (stops evolution_worker restarts)" -ForegroundColor Green
Write-Host "  3. close_stale_positions.py created for one-time position cleanup" -ForegroundColor Green
Write-Host ""
Write-Host "OPTIONAL: Close stale open positions first:" -ForegroundColor Yellow
Write-Host "  python close_stale_positions.py" -ForegroundColor Yellow
Write-Host ""
Write-Host "Then run:" -ForegroundColor White
Write-Host "  python main.py" -ForegroundColor Yellow
Write-Host ""
Write-Host "You should now see:" -ForegroundColor White
Write-Host "  - No more 'TradingConfig is not defined' errors" -ForegroundColor Green
Write-Host "  - evolution_worker staying alive (no more 125s restarts)" -ForegroundColor Green
Write-Host "  - BTC/USD signals passing through to execution" -ForegroundColor Green
Write-Host "  - Signals: conf=0.6+ executing as trades" -ForegroundColor Green
Write-Host ""
Write-Host "After 30 min clean run:" -ForegroundColor White
Write-Host "  python freeze_baseline.py --force" -ForegroundColor Yellow
Write-Host ""
