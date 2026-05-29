# final_fix.ps1
# Run from your MECOS folder:
#   .\final_fix.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  MECOS Final Baseline Fix" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Step 1: Show the actual metrics file structure
Write-Host ""
Write-Host "Checking metrics file structure..." -ForegroundColor White
$MetricsPath = "memory_db\benchmarks\runtime_subsystem_metrics.json"
if (Test-Path $MetricsPath) {
    Write-Host "  Found: $MetricsPath" -ForegroundColor Green
    Write-Host "  First 30 lines:" -ForegroundColor Gray
    Get-Content $MetricsPath | Select-Object -First 30
} else {
    Write-Host "  [NOT FOUND] $MetricsPath" -ForegroundColor Yellow
    Write-Host "  Listing all files in memory_db\benchmarks\:" -ForegroundColor Gray
    if (Test-Path "memory_db\benchmarks") {
        Get-ChildItem "memory_db\benchmarks" | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
    } else {
        Write-Host "    memory_db\benchmarks\ does not exist yet" -ForegroundColor Yellow
    }
}

Write-Host ""

# Step 2: Write the corrected freeze_baseline.py
# Key changes:
# - Uses data\benchmark_baseline.json (separate from trusted_memory_anchors.json)
# - Handles metrics file being a list OR a dict
# - Gracefully creates a minimal baseline if metrics file doesn't exist yet
Write-Host "Writing corrected freeze_baseline.py ..." -ForegroundColor White

Set-Content -Path "freeze_baseline.py" -Value @'
"""
freeze_baseline.py - MECOS Frozen Benchmark Baseline Manager

Uses: data/benchmark_baseline.json
(Separate from data/trusted_memory_anchors.json which is the drift_guard policy anchor file)

Run MANUALLY after a known-good burn:
    python freeze_baseline.py             # freeze
    python freeze_baseline.py --force     # overwrite
    python freeze_baseline.py --show      # print
    python freeze_baseline.py --verify    # compare live vs frozen
"""

import argparse
import json
import os
import stat
import sys
import time
from pathlib import Path

# NOTE: separate file from trusted_memory_anchors.json
BASELINE_PATH = Path("data/benchmark_baseline.json")
METRICS_DIR   = Path("memory_db/benchmarks")


def find_metrics() -> dict | None:
    """
    Try to load benchmark metrics. Handles dict or list format.
    Returns a flat {subsystem: score} dict, or None if nothing found.
    """
    # Try the standard metrics file first
    candidates = [
        METRICS_DIR / "runtime_subsystem_metrics.json",
        METRICS_DIR / "benchmark_metrics.json",
        METRICS_DIR / "metrics.json",
    ]
    for path in candidates:
        if path.exists():
            with open(path) as f:
                raw = json.load(f)
            return _normalise_metrics(raw, str(path))

    # Try any json in the benchmarks dir
    if METRICS_DIR.exists():
        for p in METRICS_DIR.glob("*.json"):
            if "baseline" not in p.name and "drift" not in p.name and "audit" not in p.name and "trusted" not in p.name:
                with open(p) as f:
                    raw = json.load(f)
                result = _normalise_metrics(raw, str(p))
                if result:
                    return result
    return None


def _normalise_metrics(raw, source: str) -> dict:
    """Convert any metrics format to {subsystem: float}."""
    scores = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            if k in ("anchors",):
                continue
            if isinstance(v, (int, float)):
                scores[k] = float(v)
            elif isinstance(v, dict):
                s = v.get("score") or v.get("latest") or v.get("avg") or v.get("value")
                if s is not None:
                    scores[k] = float(s)
            elif isinstance(v, list) and v:
                # take last numeric value in list
                for item in reversed(v):
                    if isinstance(item, (int, float)):
                        scores[k] = float(item)
                        break
                    if isinstance(item, dict):
                        s = item.get("score") or item.get("value") or item.get("avg")
                        if s is not None:
                            scores[k] = float(s)
                            break
    elif isinstance(raw, list):
        # list of {subsystem, score} entries — take latest per subsystem
        for item in raw:
            if isinstance(item, dict):
                sub = item.get("subsystem") or item.get("name") or item.get("key")
                val = item.get("score") or item.get("value") or item.get("avg")
                if sub and val is not None:
                    scores[sub] = float(val)
    if scores:
        print(f"  [metrics] Loaded {len(scores)} subsystem scores from {source}")
    return scores


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


def load_baseline() -> dict | None:
    if not BASELINE_PATH.exists():
        return None
    _make_writable()
    try:
        with open(BASELINE_PATH) as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Could not read baseline: {e}")
        return None


def freeze(force: bool = False):
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)

    if BASELINE_PATH.exists() and not force:
        print(f"[SKIP] Baseline already exists at {BASELINE_PATH}")
        print("       Use --force to overwrite.")
        return

    _make_writable()

    metrics = find_metrics()

    if not metrics:
        # No metrics file yet — create a minimal placeholder baseline
        print("[WARN] No metrics file found. Creating placeholder baseline.")
        print("       Run MECOS for a full cycle then use --force to update with real scores.")
        metrics = {
            "coding":    0.0,
            "research":  0.0,
            "debugging": 0.0,
            "memory":    0.0,
            "evolution": 0.0,
            "planning":  0.0,
            "trading":   0.0,
        }

    snapshot = {
        sub: {
            "score": score,
            "frozen_at": time.time(),
            "frozen_at_human": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for sub, score in metrics.items()
    }

    with open(BASELINE_PATH, "w") as f:
        json.dump(snapshot, f, indent=2)

    _make_readonly()

    print(f"\n[OK] Benchmark baseline frozen at {BASELINE_PATH} (read-only)")
    print(f"     NOTE: trusted_memory_anchors.json is untouched (that's your policy anchor file)\n")
    for sub, v in snapshot.items():
        print(f"       {sub:<35}  score={v['score']:.4f}  at={v['frozen_at_human']}")
    print()


def show():
    baseline = load_baseline()
    if baseline is None:
        print(f"[INFO] No benchmark baseline at {BASELINE_PATH}. Run: python freeze_baseline.py")
        return
    print(f"\nFrozen benchmark baseline — {BASELINE_PATH}\n")
    print(f"  {'Subsystem':<35}  {'Score':>8}  {'Frozen At'}")
    print("  " + "-" * 65)
    for sub, v in baseline.items():
        score    = v.get("score", "N/A")
        at       = v.get("frozen_at_human", "unknown")
        if isinstance(score, (int, float)):
            print(f"  {sub:<35}  {float(score):>8.4f}  {at}")
        else:
            print(f"  {sub:<35}  {'N/A':>8}  {at}")
    print()


def verify():
    baseline = load_baseline()
    if baseline is None:
        print(f"[WARN] No benchmark baseline at {BASELINE_PATH}.")
        return
    metrics = find_metrics()
    if not metrics:
        print("[WARN] No live metrics found to compare.")
        return
    print(f"\nVerification — live vs frozen baseline\n")
    print(f"  {'Subsystem':<35}  {'Live':>8}  {'Frozen':>8}  {'Delta':>8}  Status")
    print("  " + "-" * 80)
    any_issue = False
    for sub, fv in baseline.items():
        frozen     = fv.get("score")
        live_score = metrics.get(sub)
        if frozen is None:
            continue
        if live_score is None:
            print(f"  {sub:<35}  {'N/A':>8}  {frozen:>8.4f}  {'N/A':>8}  [NO DATA]")
            continue
        delta  = live_score - frozen
        status = "REGRESSION" if delta < -0.20 else ("IMPROVEMENT" if delta > 0.20 else "OK")
        if status != "OK":
            any_issue = True
        print(f"  {sub:<35}  {live_score:>8.4f}  {frozen:>8.4f}  {delta:>+8.4f}  {status}")
    print()
    if any_issue:
        print("[WARN] Drift detected. Review before next evolution cycle.\n")
    else:
        print("[OK] All subsystems within acceptable bounds.\n")


def main():
    parser = argparse.ArgumentParser(description="MECOS Benchmark Baseline Manager")
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

Write-Host "  [OK]  freeze_baseline.py written" -ForegroundColor Green

# Step 3: Also update drift_guard.py to point to the new baseline path
Write-Host ""
Write-Host "Updating drift_guard.py default baseline path..." -ForegroundColor White
$DriftPath = "runtime\drift_guard.py"
$drift = Get-Content $DriftPath -Raw
$drift = $drift -replace '"data/trusted_memory_anchors.json"', '"data/benchmark_baseline.json"'
Set-Content $DriftPath $drift -Encoding UTF8
Write-Host "  [OK]  drift_guard.py updated" -ForegroundColor Green

# Step 4: Also update validity_filter.py default baseline path
Write-Host "Updating validity_filter.py default baseline path..." -ForegroundColor White
$VFPath = "runtime\validity_filter.py"
$vf = Get-Content $VFPath -Raw
$vf = $vf -replace '"data/trusted_memory_anchors.json"', '"data/benchmark_baseline.json"'
Set-Content $VFPath $vf -Encoding UTF8
Write-Host "  [OK]  validity_filter.py updated" -ForegroundColor Green

# Step 5: Run freeze
Write-Host ""
Write-Host "Freezing benchmark baseline..." -ForegroundColor White
python freeze_baseline.py --force

# Step 6: Show result
Write-Host ""
python freeze_baseline.py --show

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Done." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Summary:" -ForegroundColor White
Write-Host "  data\trusted_memory_anchors.json  <- UNTOUCHED (your policy anchor file)" -ForegroundColor Gray
Write-Host "  data\benchmark_baseline.json      <- NEW frozen benchmark scores (read-only)" -ForegroundColor Green
Write-Host ""
Write-Host "Now apply the two patches from meta_learner_patch.py to meta_learner.py" -ForegroundColor Yellow
Write-Host "Then MECOS hardening is fully complete." -ForegroundColor Yellow
Write-Host ""
