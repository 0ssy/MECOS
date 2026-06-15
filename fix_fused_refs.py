"""
fix_fused_refs.py
Run from MECOS root: python fix_fused_refs.py
"""
from pathlib import Path

p = Path("trading/trading_agent.py")
src = p.read_text(encoding="utf-8")

replacements = [
    (
        'sizing = fused.get("sizing_multipliers", {})',
        'sizing = {}  # collab engine handles sizing via Kelly fraction'
    ),
    (
        'signal_strength=float(fused.get("confidence", 0.5)),',
        'signal_strength=float(orchestrated.get("confidence", 0.5)),'
    ),
    (
        'historical_accuracy=float(fused.get("agreement", 0.5)),',
        'historical_accuracy=float(orchestrated.get("agreement", 0.5)),'
    ),
    (
        '"buy_score": float(fused.get("buy_score", orchestrated.get("buy_score", 0.0))),',
        '"buy_score": float(orchestrated.get("buy_score", 0.0)),'
    ),
    (
        '"sell_score": float(fused.get("sell_score", orchestrated.get("sell_score", 0.0))),',
        '"sell_score": float(orchestrated.get("sell_score", 0.0)),'
    ),
    (
        '"hold_score": float(fused.get("hold_score", orchestrated.get("hold_score", 0.0))),',
        '"hold_score": float(orchestrated.get("hold_score", 0.0)),'
    ),
]

for old, new in replacements:
    count = src.count(old)
    if count == 0:
        print(f"NOT FOUND: {old[:70]}")
    elif count > 1:
        print(f"AMBIGUOUS ({count}x): {old[:70]}")
    else:
        src = src.replace(old, new)
        print(f"OK: {old[:70]}")

p.write_text(src, encoding="utf-8")
print("\nDone.")
