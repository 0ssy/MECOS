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
    try:
        with open(BASELINE_PATH) as f:
            return json.load(f)
    except PermissionError:
        print("[ERROR] Baseline is read-only. That is correct — use --force to overwrite.")
        sys.exit(1)


def freeze(force: bool = False):
    metrics = load_metrics()
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)

    if BASELINE_PATH.exists() and not force:
        print(f"[SKIP] Baseline already exists at {BASELINE_PATH}")
        print("       Use --force to overwrite (only after a deliberate improvement).")
        return

    # Make writable for overwrite
    if BASELINE_PATH.exists() and force:
        os.chmod(BASELINE_PATH, stat.S_IRUSR | stat.S_IWUSR)

    snapshot = {}
    for subsystem, values in metrics.items():
        if isinstance(values, dict):
            score = values.get("score") or values.get("latest") or values.get("avg")
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

    # Lock read-only
    os.chmod(BASELINE_PATH, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

    print(f"\n[OK] Frozen baseline written to {BASELINE_PATH} (read-only)")
    print(f"     Subsystems frozen:\n")
    for sub, v in snapshot.items():
        print(f"       {sub:<30}  score={v['score']:.4f}  at={v['frozen_at_human']}")
    print()


def show():
    baseline = load_baseline()
    if baseline is None:
        print("[INFO] No frozen baseline exists yet.")
        return
    print(f"\nFrozen baseline — {BASELINE_PATH}\n")
    print(f"  {'Subsystem':<30}  {'Score':>8}  {'Frozen At'}")
    print("  " + "-" * 62)
    for sub, v in baseline.items():
        print(f"  {sub:<30}  {v['score']:>8.4f}  {v.get('frozen_at_human','unknown')}")
    print()


def verify():
    baseline = load_baseline()
    if baseline is None:
        print("[WARN] No frozen baseline to compare against.")
        return
    metrics = load_metrics()
    print(f"\nVerification — live vs frozen\n")
    print(f"  {'Subsystem':<30}  {'Live':>8}  {'Frozen':>8}  {'Delta':>8}  Status")
    print("  " + "-" * 75)
    any_issue = False
    for sub, fv in baseline.items():
        frozen     = fv["score"]
        lv         = metrics.get(sub, {})
        live_score = lv.get("score") or lv.get("latest") or lv.get("avg") if isinstance(lv, dict) else (float(lv) if isinstance(lv, (int, float)) else None)
        if live_score is None:
            print(f"  {sub:<30}  {'N/A':>8}  {frozen:>8.4f}  {'N/A':>8}  [NO DATA]")
            continue
        delta  = float(live_score) - frozen
        status = ("REGRESSION" if delta < -0.20 else "IMPROVEMENT" if delta > 0.20 else "OK")
        if status != "OK":
            any_issue = True
        print(f"  {sub:<30}  {float(live_score):>8.4f}  {frozen:>8.4f}  {delta:>+8.4f}  {status}")
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
