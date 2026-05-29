# fix_and_refreeze.ps1
# Run from your MECOS folder:
#   .\fix_and_refreeze.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Fix baseline format + refreeze" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Step 1: Show what's currently in the baseline file
$BaselinePath = "data\trusted_memory_anchors.json"
Write-Host ""
Write-Host "Current baseline content:" -ForegroundColor Yellow
Get-Content $BaselinePath
Write-Host ""

# Step 2: Make the file writable so we can overwrite it
Write-Host "Making baseline writable..." -ForegroundColor White
try {
    $acl = Get-Acl $BaselinePath
    $file = Get-Item $BaselinePath
    $file.IsReadOnly = $false
    Write-Host "  [OK] File is now writable" -ForegroundColor Green
} catch {
    Write-Host "  [WARN] Could not change permissions: $_" -ForegroundColor Yellow
}

# Step 3: Overwrite freeze_baseline.py with fixed version
Write-Host "Writing fixed freeze_baseline.py ..." -ForegroundColor White

Set-Content -Path "freeze_baseline.py" -Value @'
"""
freeze_baseline.py - MECOS Frozen Baseline Manager

Run MANUALLY from PowerShell after a known-good benchmark burn.
NEVER called automatically by the runtime.

Usage:
    python freeze_baseline.py             # freeze current metrics
    python freeze_baseline.py --force     # overwrite existing baseline
    python freeze_baseline.py --show      # print frozen baseline
    python freeze_baseline.py --verify    # compare live vs frozen
"""

import argparse
import json
import os
import stat
import sys
import time
from pathlib import Path

BASELINE_PATH = Path("data/trusted_memory_anchors.json")
METRICS_PATH  = Path("memory_db/benchmarks/runtime_subsystem_metrics.json")


def load_metrics() -> dict:
    if not METRICS_PATH.exists():
        print(f"[ERROR] Metrics file not found: {METRICS_PATH}")
        print("        Run MECOS for at least one full cycle first.")
        sys.exit(1)
    with open(METRICS_PATH) as f:
        return json.load(f)


def load_baseline() -> dict | None:
    if not BASELINE_PATH.exists():
        return None
    # Make readable if needed
    try:
        cur = os.stat(BASELINE_PATH).st_mode
        os.chmod(BASELINE_PATH, cur | stat.S_IRUSR)
    except Exception:
        pass
    try:
        with open(BASELINE_PATH) as f:
            raw = json.load(f)
        # Normalise: the file might be a flat {subsystem: score} dict,
        # a {subsystem: [list]} dict, or the correct {subsystem: {score:...}} dict.
        normalised = {}
        for k, v in raw.items():
            if isinstance(v, dict):
                # already correct format
                normalised[k] = v
            elif isinstance(v, list):
                # old format: list of score entries — take the last score value
                score = None
                for item in reversed(v):
                    if isinstance(item, dict):
                        score = item.get("score") or item.get("value") or item.get("avg")
                    elif isinstance(item, (int, float)):
                        score = float(item)
                    if score is not None:
                        break
                if score is not None:
                    normalised[k] = {
                        "score": float(score),
                        "frozen_at": time.time(),
                        "frozen_at_human": time.strftime("%Y-%m-%d %H:%M:%S"),
                    }
            elif isinstance(v, (int, float)):
                normalised[k] = {
                    "score": float(v),
                    "frozen_at": time.time(),
                    "frozen_at_human": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
        return normalised
    except PermissionError:
        print("[ERROR] Baseline is read-only. Use --force to overwrite.")
        sys.exit(1)


def _make_writable():
    if BASELINE_PATH.exists():
        try:
            BASELINE_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass


def _make_readonly():
    try:
        BASELINE_PATH.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    except Exception:
        pass


def freeze(force: bool = False):
    metrics = load_metrics()
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)

    if BASELINE_PATH.exists() and not force:
        print(f"[SKIP] Baseline already exists at {BASELINE_PATH}")
        print("       Use --force to overwrite.")
        return

    _make_writable()

    snapshot = {}
    for subsystem, values in metrics.items():
        if isinstance(values, dict):
            score = values.get("score") or values.get("latest") or values.get("avg")
        elif isinstance(values, list):
            # take last numeric value
            score = None
            for item in reversed(values):
                if isinstance(item, (int, float)):
                    score = float(item)
                    break
                if isinstance(item, dict):
                    score = item.get("score") or item.get("value") or item.get("avg")
                    if score is not None:
                        break
        elif isinstance(values, (int, float)):
            score = float(values)
        else:
            continue

        if score is not None:
            snapshot[subsystem] = {
                "score": float(score),
                "frozen_at": time.time(),
                "frozen_at_human": time.strftime("%Y-%m-%d %H:%M:%S"),
            }

    with open(BASELINE_PATH, "w") as f:
        json.dump(snapshot, f, indent=2)

    _make_readonly()

    print(f"\n[OK] Frozen baseline written to {BASELINE_PATH} (read-only)")
    print(f"     Subsystems frozen:\n")
    for sub, v in snapshot.items():
        print(f"       {sub:<35}  score={v['score']:.4f}  at={v['frozen_at_human']}")
    print()


def show():
    baseline = load_baseline()
    if baseline is None:
        print("[INFO] No frozen baseline exists yet.")
        return
    print(f"\nFrozen baseline — {BASELINE_PATH}\n")
    print(f"  {'Subsystem':<35}  {'Score':>8}  {'Frozen At'}")
    print("  " + "-" * 65)
    for sub, v in baseline.items():
        score = v.get("score", "N/A")
        frozen_at = v.get("frozen_at_human", "unknown")
        if isinstance(score, float):
            print(f"  {sub:<35}  {score:>8.4f}  {frozen_at}")
        else:
            print(f"  {sub:<35}  {'N/A':>8}  {frozen_at}")
    print()


def verify():
    baseline = load_baseline()
    if baseline is None:
        print("[WARN] No frozen baseline to compare against.")
        return
    metrics = load_metrics()
    print(f"\nVerification — live vs frozen\n")
    print(f"  {'Subsystem':<35}  {'Live':>8}  {'Frozen':>8}  {'Delta':>8}  Status")
    print("  " + "-" * 80)
    any_issue = False
    for sub, fv in baseline.items():
        frozen = fv.get("score")
        if frozen is None:
            continue
        lv = metrics.get(sub, {})
        if isinstance(lv, dict):
            live_score = lv.get("score") or lv.get("latest") or lv.get("avg")
        elif isinstance(lv, (int, float)):
            live_score = float(lv)
        else:
            live_score = None

        if live_score is None:
            print(f"  {sub:<35}  {'N/A':>8}  {frozen:>8.4f}  {'N/A':>8}  [NO DATA]")
            continue

        delta  = float(live_score) - frozen
        status = ("REGRESSION" if delta < -0.20 else "IMPROVEMENT" if delta > 0.20 else "OK")
        if status != "OK":
            any_issue = True
        print(f"  {sub:<35}  {float(live_score):>8.4f}  {frozen:>8.4f}  {delta:>+8.4f}  {status}")
    print()
    if any_issue:
        print("[WARN] Drift detected. Review before next evolution cycle.\n")
    else:
        print("[OK] All subsystems within acceptable bounds.\n")


def main():
    parser = argparse.ArgumentParser(description="MECOS Frozen Baseline Manager")
    parser.add_argument("--force",  action="store_true", help="Overwrite existing baseline")
    parser.add_argument("--show",   action="store_true", help="Print frozen baseline")
    parser.add_argument("--verify", action="store_true", help="Compare live vs frozen")
    args = parser.parse_args()

    if args.show:
        show()
    elif args.verify:
        verify()
    else:
        freeze(force=args.force)


if __name__ == "__main__":
    main()
'@ -Encoding UTF8

Write-Host "  [OK]  freeze_baseline.py updated" -ForegroundColor Green

# Step 4: Force refreeze with correct format
Write-Host ""
Write-Host "Refreezing baseline with correct format..." -ForegroundColor White
python freeze_baseline.py --force

Write-Host ""
Write-Host "Verifying --show works..." -ForegroundColor White
python freeze_baseline.py --show

Write-Host ""
Write-Host "[DONE] Baseline is fixed and locked." -ForegroundColor Cyan
Write-Host "Next: apply the two patches from meta_learner_patch.py to meta_learner.py" -ForegroundColor Yellow
Write-Host ""
