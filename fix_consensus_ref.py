"""
fix_consensus_ref.py
Run from MECOS root: python fix_consensus_ref.py
"""
from pathlib import Path

p = Path("trading/trading_agent.py")
src = p.read_text(encoding="utf-8")

old = '            "consensus": consensus,'
new = '            "consensus": orchestrated,'

count = src.count(old)
if count == 0:
    print("NOT FOUND — checking raw content around line 461:")
    lines = src.splitlines()
    for i, line in enumerate(lines[455:470], start=456):
        print(f"  {i}: {repr(line)}")
elif count > 1:
    print(f"AMBIGUOUS ({count} matches) — not patching")
else:
    src = src.replace(old, new)
    p.write_text(src, encoding="utf-8")
    print("OK: consensus reference fixed")

print("Done.")
