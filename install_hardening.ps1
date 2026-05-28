# MECOS Hardening Installer
# Run from your MECOS project root:
#   cd C:\Users\josep\Downloads\MECOS
#   .\install_hardening.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Get-Location

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  MECOS Hardening Installer" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot" -ForegroundColor Gray
Write-Host ""

# ---------------------------------------------------------------------------
# Helper: write a file, creating parent dirs if needed
# ---------------------------------------------------------------------------
function Write-FileContent {
    param(
        [string]$RelativePath,
        [string]$Content
    )
    $FullPath = Join-Path $ProjectRoot $RelativePath
    $Dir = Split-Path $FullPath -Parent
    if (-not (Test-Path $Dir)) {
        New-Item -ItemType Directory -Path $Dir -Force | Out-Null
    }
    # Backup existing file if present
    if (Test-Path $FullPath) {
        $Backup = "$FullPath.bak"
        Copy-Item $FullPath $Backup -Force
        Write-Host "  [BAK] $RelativePath -> $RelativePath.bak" -ForegroundColor Yellow
    }
    Set-Content -Path $FullPath -Value $Content -Encoding UTF8
    Write-Host "  [OK]  $RelativePath" -ForegroundColor Green
}

# ===========================================================================
# FILE 1: runtime\validity_filter.py
# ===========================================================================
Write-Host "Writing runtime\validity_filter.py ..." -ForegroundColor White
Write-FileContent "runtime\validity_filter.py" @'
"""
validity_filter.py - MECOS Benchmark Validity Filter

Sits between BenchmarkHarness and EvolutionAgent.
Prevents the evolution loop from gaming proxy metrics.

Pipeline:
    BenchmarkHarness
        |
    ValidityFilter   <- this module
        |
    TrustedScoreStore
        |
    EvolutionAgent
"""

import hashlib
import json
import logging
import random
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ScoredOutput:
    """A single output+score pair from BenchmarkHarness."""
    subsystem: str
    task_id: str
    output: Any
    raw_score: float
    metadata: Dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class ValidationResult:
    """Result of auditing a ScoredOutput."""
    task_id: str
    subsystem: str
    raw_score: float
    validated_score: float
    passed: bool
    audit_type: str
    reason: str
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Ground truth registry
# Add entries here as you build benchmark tasks.
# Keys are task_id strings; values are canonical answers or callables.
# ---------------------------------------------------------------------------
GROUND_TRUTH: Dict[str, Any] = {
    "coding_hello_world": "Hello, World!",
    "coding_fib_10": 55,
    "coding_sort_list": [1, 2, 3, 4, 5],
    "research_bitcoin_basics": lambda out: all(
        kw in str(out).lower()
        for kw in ["blockchain", "decentralized", "satoshi"]
    ),
}

NULL_QUERIES = [
    "xkqzplmnbvwrty",
    "aaaaaaaaaaaaaaaa",
    "SELECT * FROM nonexistent_table_xyz",
    "the quick brown fox jumped over the lazy __GIBBERISH__",
]

TRIVIAL_CODE_PATTERNS = [
    'print("done")',
    "pass",
    "return True",
    "return None",
    "...",
    "# TODO",
]


# ---------------------------------------------------------------------------
# ValidityFilter
# ---------------------------------------------------------------------------

class ValidityFilter:
    def __init__(
        self,
        audit_rate: float = 0.10,
        penalty_factor: float = 0.0,
        audit_log_path: str = "memory_db/benchmarks/validity_audit_log.jsonl",
        trusted_store_path: str = "memory_db/benchmarks/trusted_scores.json",
        baseline_path: str = "data/trusted_memory_anchors.json",
    ):
        self.audit_rate = audit_rate
        self.penalty_factor = penalty_factor
        self.audit_log_path = Path(audit_log_path)
        self.trusted_store_path = Path(trusted_store_path)
        self.baseline_path = Path(baseline_path)

        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.trusted_store_path.parent.mkdir(parents=True, exist_ok=True)

        self._trusted_scores: List[ValidationResult] = []
        self._load_trusted_store()
        logger.info(f"ValidityFilter initialized | audit_rate={audit_rate:.0%}")

    def filter(self, outputs: List[ScoredOutput]) -> List[ValidationResult]:
        results = []
        for scored in outputs:
            result = self._evaluate(scored)
            results.append(result)
            self._log_audit(result)
            if result.passed:
                self._trusted_scores.append(result)

        self._save_trusted_store()
        self._check_drift()

        passed = sum(1 for r in results if r.passed)
        logger.info(f"ValidityFilter: {passed}/{len(results)} outputs passed audit")
        return results

    def trusted_scores(self) -> List[ValidationResult]:
        return [r for r in self._trusted_scores if r.passed]

    def inject_null_probe(self, memory_system) -> ValidationResult:
        query = random.choice(NULL_QUERIES)
        try:
            import asyncio
            results = asyncio.get_event_loop().run_until_complete(
                memory_system.retrieve_context(query, n_results=3)
            )
            scores = [r.get("relevance", r.get("score", 0.5)) for r in results] if results else [0.0]
            avg_score = sum(scores) / len(scores) if scores else 0.0
            passed = avg_score < 0.35
            return ValidationResult(
                task_id=f"null_probe_{hashlib.md5(query.encode()).hexdigest()[:8]}",
                subsystem="memory",
                raw_score=avg_score,
                validated_score=avg_score if passed else 0.0,
                passed=passed,
                audit_type="null_query_probe",
                reason=f"Null query scored {avg_score:.3f} ({'PASS' if passed else 'FAIL: too high'})",
            )
        except Exception as e:
            return ValidationResult(
                task_id="null_probe_error", subsystem="memory",
                raw_score=0.0, validated_score=0.0, passed=False,
                audit_type="null_query_probe", reason=f"Exception: {e}",
            )

    # ------------------------------------------------------------------
    # Checks
    # ------------------------------------------------------------------

    def _evaluate(self, scored: ScoredOutput) -> ValidationResult:
        check_fn = {
            "coding":    self._check_coding,
            "research":  self._check_research,
            "debugging": self._check_debugging,
            "memory":    self._check_memory,
            "evolution": self._check_evolution,
        }.get(scored.subsystem, self._check_generic)

        result = check_fn(scored)

        if random.random() < self.audit_rate and scored.task_id in GROUND_TRUTH:
            gt_result = self._check_ground_truth(scored)
            if not gt_result.passed:
                return gt_result

        return result

    def _check_coding(self, scored: ScoredOutput) -> ValidationResult:
        output_str = str(scored.output).strip()
        for pattern in TRIVIAL_CODE_PATTERNS:
            if output_str == pattern or output_str.startswith(pattern):
                return ValidationResult(
                    task_id=scored.task_id, subsystem="coding",
                    raw_score=scored.raw_score, validated_score=0.0, passed=False,
                    audit_type="trivial_code_detection",
                    reason=f"Matches trivial pattern: '{pattern}'",
                )
        if len(output_str) < 20 and scored.raw_score > 0.7:
            return ValidationResult(
                task_id=scored.task_id, subsystem="coding",
                raw_score=scored.raw_score,
                validated_score=scored.raw_score * self.penalty_factor,
                passed=False, audit_type="suspiciously_short_code",
                reason=f"Only {len(output_str)} chars but scored {scored.raw_score:.2f}",
            )
        return self._pass(scored, "coding_structural_check")

    def _check_research(self, scored: ScoredOutput) -> ValidationResult:
        output_str = str(scored.output)
        sentences = [s.strip() for s in output_str.split(".") if len(s.strip()) > 10]
        if sentences:
            unique_ratio = len(set(sentences)) / len(sentences)
            if unique_ratio < 0.6 and scored.raw_score > 0.5:
                return ValidationResult(
                    task_id=scored.task_id, subsystem="research",
                    raw_score=scored.raw_score,
                    validated_score=scored.raw_score * self.penalty_factor,
                    passed=False, audit_type="repetition_amplification",
                    reason=f"Unique sentence ratio: {unique_ratio:.2f} (< 0.6)",
                )
        if len(output_str) < 100 and scored.raw_score > 0.7:
            return ValidationResult(
                task_id=scored.task_id, subsystem="research",
                raw_score=scored.raw_score,
                validated_score=scored.raw_score * self.penalty_factor,
                passed=False, audit_type="suspiciously_short_research",
                reason=f"Only {len(output_str)} chars but scored {scored.raw_score:.2f}",
            )
        return self._pass(scored, "research_structural_check")

    def _check_debugging(self, scored: ScoredOutput) -> ValidationResult:
        original = scored.metadata.get("original_code", "")
        repaired = str(scored.output)
        if original and repaired:
            orig_norm = " ".join(original.split())
            rep_norm  = " ".join(repaired.split())
            if orig_norm == rep_norm:
                return ValidationResult(
                    task_id=scored.task_id, subsystem="debugging",
                    raw_score=scored.raw_score, validated_score=0.0,
                    passed=False, audit_type="no_op_repair",
                    reason="Repair identical to broken input (no-op)",
                )
            orig_tokens = set(orig_norm.split())
            rep_tokens  = set(rep_norm.split())
            if orig_tokens | rep_tokens:
                jaccard = len(orig_tokens & rep_tokens) / len(orig_tokens | rep_tokens)
                if jaccard > 0.95 and scored.raw_score > 0.7:
                    return ValidationResult(
                        task_id=scored.task_id, subsystem="debugging",
                        raw_score=scored.raw_score,
                        validated_score=scored.raw_score * self.penalty_factor,
                        passed=False, audit_type="minimal_change_repair",
                        reason=f"Jaccard similarity to original: {jaccard:.3f} (> 0.95)",
                    )
        return self._pass(scored, "debugging_diff_check")

    def _check_memory(self, scored: ScoredOutput) -> ValidationResult:
        query = scored.metadata.get("query", "").lower()
        null_words = {"xkqz", "aaaa", "gibberish", "nonexistent"}
        if any(nw in query for nw in null_words) and scored.raw_score > 0.3:
            return ValidationResult(
                task_id=scored.task_id, subsystem="memory",
                raw_score=scored.raw_score, validated_score=0.0,
                passed=False, audit_type="null_query_high_score",
                reason=f"Null query scored {scored.raw_score:.2f}",
            )
        return self._pass(scored, "memory_relevance_check")

    def _check_evolution(self, scored: ScoredOutput) -> ValidationResult:
        baseline = self._load_frozen_baseline()
        if baseline is None:
            logger.warning("No frozen baseline found. Evolution scores unverified.")
            return self._pass(scored, "evolution_no_baseline")
        frozen = baseline.get(scored.subsystem, {}).get("score")
        if frozen is not None:
            reported_delta = scored.metadata.get("delta")
            actual_delta   = scored.raw_score - frozen
            if reported_delta is not None and abs(reported_delta - actual_delta) > 0.15:
                return ValidationResult(
                    task_id=scored.task_id, subsystem="evolution",
                    raw_score=scored.raw_score,
                    validated_score=scored.raw_score * self.penalty_factor,
                    passed=False, audit_type="baseline_delta_mismatch",
                    reason=(
                        f"Reported delta={reported_delta:.3f} but "
                        f"actual vs frozen={actual_delta:.3f} "
                        f"(discrepancy > 0.15 — possible baseline drift)"
                    ),
                )
        return self._pass(scored, "evolution_baseline_check")

    def _check_generic(self, scored: ScoredOutput) -> ValidationResult:
        return self._pass(scored, "generic_passthrough")

    def _check_ground_truth(self, scored: ScoredOutput) -> ValidationResult:
        gt = GROUND_TRUTH[scored.task_id]
        try:
            if callable(gt):
                passed = gt(scored.output)
                reason = f"Ground truth validator: {'PASS' if passed else 'FAIL'}"
            else:
                passed = str(scored.output).strip() == str(gt).strip()
                reason = f"Ground truth: {'PASS' if passed else 'FAIL'} (expected={repr(str(gt)[:40])})"
        except Exception as e:
            passed = False
            reason = f"Ground truth check raised: {e}"
        return ValidationResult(
            task_id=scored.task_id, subsystem=scored.subsystem,
            raw_score=scored.raw_score,
            validated_score=scored.raw_score if passed else scored.raw_score * self.penalty_factor,
            passed=passed, audit_type="ground_truth_spot_check", reason=reason,
        )

    def _check_drift(self):
        baseline = self._load_frozen_baseline()
        if not baseline or not self._trusted_scores:
            return
        recent = self._trusted_scores[-50:]
        by_sub: Dict[str, List[float]] = {}
        for r in recent:
            by_sub.setdefault(r.subsystem, []).append(r.validated_score)
        for subsystem, scores in by_sub.items():
            avg    = sum(scores) / len(scores)
            frozen = baseline.get(subsystem, {}).get("score")
            if frozen is None:
                continue
            drift = avg - frozen
            if abs(drift) > 0.20:
                direction = "IMPROVEMENT" if drift > 0 else "REGRESSION"
                logger.warning(
                    f"[DriftGuard] {subsystem}: {direction} "
                    f"avg={avg:.3f}, frozen={frozen:.3f}, delta={drift:+.3f}"
                )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pass(scored: ScoredOutput, audit_type: str) -> ValidationResult:
        return ValidationResult(
            task_id=scored.task_id, subsystem=scored.subsystem,
            raw_score=scored.raw_score, validated_score=scored.raw_score,
            passed=True, audit_type=audit_type, reason="Passed validity check",
        )

    def _load_frozen_baseline(self) -> Optional[Dict]:
        if self.baseline_path.exists():
            try:
                with open(self.baseline_path) as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load frozen baseline: {e}")
        return None

    def _log_audit(self, result: ValidationResult):
        try:
            with open(self.audit_log_path, "a") as f:
                f.write(json.dumps(asdict(result)) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    def _load_trusted_store(self):
        if self.trusted_store_path.exists():
            try:
                with open(self.trusted_store_path) as f:
                    raw = json.load(f)
                self._trusted_scores = [ValidationResult(**r) for r in raw]
                logger.info(f"Loaded {len(self._trusted_scores)} trusted scores")
            except Exception as e:
                logger.warning(f"Could not load trusted store: {e}")

    def _save_trusted_store(self):
        try:
            with open(self.trusted_store_path, "w") as f:
                json.dump([asdict(r) for r in self._trusted_scores[-1000:]], f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save trusted store: {e}")


# ---------------------------------------------------------------------------
# TrustedScoreStore
# ---------------------------------------------------------------------------

class TrustedScoreStore:
    """EvolutionAgent reads from this, never directly from BenchmarkHarness."""
    def __init__(self, validity_filter: ValidityFilter):
        self._filter = validity_filter

    def get_scores(self, subsystem: Optional[str] = None) -> List[ValidationResult]:
        scores = self._filter.trusted_scores()
        return [s for s in scores if s.subsystem == subsystem] if subsystem else scores

    def get_latest_score(self, subsystem: str) -> Optional[float]:
        scores = self.get_scores(subsystem)
        return scores[-1].validated_score if scores else None

    def get_average_score(self, subsystem: str, window: int = 20) -> Optional[float]:
        scores = self.get_scores(subsystem)[-window:]
        return sum(s.validated_score for s in scores) / len(scores) if scores else None


# ---------------------------------------------------------------------------
# Convenience builder
# ---------------------------------------------------------------------------

def build_validity_pipeline(
    audit_rate: float = 0.10,
    baseline_path: str = "data/trusted_memory_anchors.json",
) -> Tuple[ValidityFilter, TrustedScoreStore]:
    vf    = ValidityFilter(audit_rate=audit_rate, baseline_path=baseline_path)
    store = TrustedScoreStore(vf)
    return vf, store


def freeze_baseline(
    current_scores: Dict[str, float],
    baseline_path: str = "data/trusted_memory_anchors.json",
    force: bool = False,
) -> bool:
    import stat as _stat
    path = Path(baseline_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        logger.info(f"Baseline already exists at {path}. Use force=True to overwrite.")
        return False
    if path.exists() and force:
        path.chmod(_stat.S_IRUSR | _stat.S_IWUSR)
    snapshot = {
        sub: {"score": score, "frozen_at": time.time(),
              "frozen_at_human": time.strftime("%Y-%m-%d %H:%M:%S")}
        for sub, score in current_scores.items()
    }
    with open(path, "w") as f:
        json.dump(snapshot, f, indent=2)
    path.chmod(_stat.S_IRUSR | _stat.S_IRGRP | _stat.S_IROTH)
    logger.info(f"Frozen baseline written to {path} (read-only). Subsystems: {list(current_scores.keys())}")
    return True
'@

# ===========================================================================
# FILE 2: runtime\drift_guard.py
# ===========================================================================
Write-Host "Writing runtime\drift_guard.py ..." -ForegroundColor White
Write-FileContent "runtime\drift_guard.py" @'
"""
drift_guard.py - MECOS Recursive Drift Prevention

Monitors benchmark scores over time and detects drift from the frozen baseline.
The frozen baseline file is READ-ONLY. DriftGuard never writes to it.
Only freeze_baseline.py (run manually) can update it.
"""

import json
import logging
import stat
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DRIFT_THRESHOLD   = 0.20
IMPROVE_THRESHOLD = 0.20


@dataclass
class DriftEvent:
    subsystem: str
    frozen_score: float
    current_score: float
    delta: float
    direction: str
    timestamp: float
    timestamp_human: str


class DriftGuard:
    def __init__(
        self,
        baseline_path: str = "data/trusted_memory_anchors.json",
        drift_log_path: str = "memory_db/benchmarks/drift_events.jsonl",
        drift_threshold: float = DRIFT_THRESHOLD,
        improve_threshold: float = IMPROVE_THRESHOLD,
    ):
        self.baseline_path     = Path(baseline_path)
        self.drift_log_path    = Path(drift_log_path)
        self.drift_threshold   = drift_threshold
        self.improve_threshold = improve_threshold
        self.drift_log_path.parent.mkdir(parents=True, exist_ok=True)
        self._baseline: Optional[Dict] = None
        self._load_baseline()

    def check(self, current_scores: Dict[str, float]) -> List[DriftEvent]:
        if self._baseline is None:
            logger.info("DriftGuard: no frozen baseline yet.")
            return []
        events = []
        for subsystem, current in current_scores.items():
            entry  = self._baseline.get(subsystem)
            if entry is None:
                continue
            frozen = entry["score"]
            delta  = current - frozen
            if delta < -self.drift_threshold:
                event = DriftEvent(
                    subsystem=subsystem, frozen_score=frozen,
                    current_score=current, delta=delta, direction="REGRESSION",
                    timestamp=time.time(),
                    timestamp_human=time.strftime("%Y-%m-%d %H:%M:%S"),
                )
                events.append(event)
                self._log_event(event)
                logger.warning(
                    f"[DriftGuard] REGRESSION {subsystem}: "
                    f"frozen={frozen:.4f} current={current:.4f} delta={delta:+.4f}"
                )
            elif delta > self.improve_threshold:
                event = DriftEvent(
                    subsystem=subsystem, frozen_score=frozen,
                    current_score=current, delta=delta, direction="IMPROVEMENT",
                    timestamp=time.time(),
                    timestamp_human=time.strftime("%Y-%m-%d %H:%M:%S"),
                )
                events.append(event)
                self._log_event(event)
                logger.info(
                    f"[DriftGuard] IMPROVEMENT {subsystem}: "
                    f"frozen={frozen:.4f} current={current:.4f} delta={delta:+.4f} "
                    "(review: possible benchmark gaming)"
                )
        return events

    def create_rollback_checkpoint(self, checkpoint_manager=None) -> str:
        ts    = time.strftime("%Y%m%d_%H%M%S")
        label = f"drift_rollback_{ts}"
        if checkpoint_manager is not None:
            try:
                path = checkpoint_manager.create_checkpoint(label)
                logger.info(f"[DriftGuard] Rollback checkpoint: {path}")
                return str(path)
            except Exception as e:
                logger.error(f"[DriftGuard] checkpoint_manager failed: {e}")
        marker_dir = Path("data/rollback_anchors")
        marker_dir.mkdir(parents=True, exist_ok=True)
        marker = marker_dir / f"{label}.json"
        with open(marker, "w") as f:
            json.dump({
                "label": label,
                "created_at": time.time(),
                "created_at_human": time.strftime("%Y-%m-%d %H:%M:%S"),
                "reason": "automatic drift-guard rollback anchor",
            }, f, indent=2)
        logger.info(f"[DriftGuard] Rollback marker: {marker}")
        return str(marker)

    def baseline_loaded(self) -> bool:
        return self._baseline is not None

    def baseline_summary(self) -> Dict[str, float]:
        return {sub: v["score"] for sub, v in self._baseline.items()} if self._baseline else {}

    def _load_baseline(self):
        if not self.baseline_path.exists():
            logger.info(f"[DriftGuard] No baseline at {self.baseline_path}. Run freeze_baseline.py after a good burn.")
            return
        try:
            mode     = self.baseline_path.stat().st_mode
            writable = bool(mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
            if writable:
                logger.warning(
                    f"[DriftGuard] Baseline is WRITABLE — should be read-only. "
                    "Run: attrib +R data\\trusted_memory_anchors.json"
                )
            with open(self.baseline_path) as f:
                self._baseline = json.load(f)
            logger.info(f"[DriftGuard] Baseline loaded: {list(self._baseline.keys())}")
        except Exception as e:
            logger.error(f"[DriftGuard] Failed to load baseline: {e}")

    def _log_event(self, event: DriftEvent):
        try:
            with open(self.drift_log_path, "a") as f:
                f.write(json.dumps(asdict(event)) + "\n")
        except Exception as e:
            logger.error(f"[DriftGuard] Failed to log event: {e}")
'@

# ===========================================================================
# FILE 3: freeze_baseline.py  (project root)
# ===========================================================================
Write-Host "Writing freeze_baseline.py ..." -ForegroundColor White
Write-FileContent "freeze_baseline.py" @'
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
'@

# ===========================================================================
# FILE 4: runtime\__init__.py  — add exports if not already present
# ===========================================================================
Write-Host "Updating runtime\__init__.py ..." -ForegroundColor White
$InitPath = Join-Path $ProjectRoot "runtime\__init__.py"
if (-not (Test-Path $InitPath)) {
    Write-FileContent "runtime\__init__.py" ""
}
$InitContent = Get-Content $InitPath -Raw -ErrorAction SilentlyContinue
$NewExports = @"

# -- Hardening layer exports (auto-added by install_hardening.ps1) --
from runtime.validity_filter import ValidityFilter, TrustedScoreStore, build_validity_pipeline, ScoredOutput, freeze_baseline
from runtime.drift_guard import DriftGuard
"@
if ($InitContent -notmatch "ValidityFilter") {
    Add-Content -Path $InitPath -Value $NewExports -Encoding UTF8
    Write-Host "  [OK]  runtime\__init__.py (exports appended)" -ForegroundColor Green
} else {
    Write-Host "  [SKIP] runtime\__init__.py already has ValidityFilter exports" -ForegroundColor Yellow
}

# ===========================================================================
# FILE 5: meta_learner_patch.py  — shows exactly what to add to meta_learner.py
# ===========================================================================
Write-Host "Writing meta_learner_patch.py ..." -ForegroundColor White
Write-FileContent "meta_learner_patch.py" @'
"""
meta_learner_patch.py
=====================
This file shows the TWO blocks to add to meta_learner.py.
Search for the markers below and insert the code.
Nothing existing is removed.
"""

# ===========================================================================
# PATCH A — Add to MetaLearner.__init__()
# After the line:  self.benchmarking = BenchmarkingEngine(...)
# ===========================================================================

PATCH_A = """
        # --- Validity Pipeline ---
        from runtime.validity_filter import build_validity_pipeline
        from runtime.drift_guard import DriftGuard
        self.validity_filter, self.score_store = build_validity_pipeline(
            audit_rate=0.10,
            baseline_path="data/trusted_memory_anchors.json",
        )
        self.drift_guard = DriftGuard(
            baseline_path="data/trusted_memory_anchors.json",
        )
"""

# ===========================================================================
# PATCH B — Add to run_meta_cycle()
# AFTER:  benchmark_results = await self.benchmarking.run_benchmarks()
# BEFORE: await self.strategy_evolution.evolve(benchmark_results)
# ===========================================================================

PATCH_B = """
        # --- Validity Filter ---
        from runtime.validity_filter import ScoredOutput
        import time as _time
        scored_outputs = [
            ScoredOutput(
                subsystem=subsystem,
                task_id=f"{subsystem}_cycle_{int(_time.time())}",
                output=result.get("output", ""),
                raw_score=result.get("score", 0.0),
                metadata=result,
            )
            for subsystem, result in benchmark_results.items()
            if isinstance(result, dict)
        ]
        validation_results = self.validity_filter.filter(scored_outputs)
        trusted = {r.subsystem: r.validated_score for r in validation_results if r.passed}

        if not trusted:
            logger.warning("ValidityFilter: no scores passed this cycle. Skipping evolution.")
            return benchmark_results

        # --- Drift Guard ---
        drift_events = self.drift_guard.check(trusted)
        if any(e.direction == "REGRESSION" for e in drift_events):
            logger.warning(f"DriftGuard: {len(drift_events)} regression(s). Creating rollback anchor.")
            self.drift_guard.create_rollback_checkpoint(
                checkpoint_manager=getattr(self, "checkpoint_manager", None)
            )

        benchmark_results = trusted
        # --- end validity + drift block ---
"""

if __name__ == "__main__":
    print("Apply PATCH_A inside MetaLearner.__init__() after self.benchmarking = ...")
    print("Apply PATCH_B inside run_meta_cycle() after benchmark_results = await ...")
    print()
    print("PATCH_A:")
    print(PATCH_A)
    print("PATCH_B:")
    print(PATCH_B)
'@

# ===========================================================================
# Summary
# ===========================================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Install complete" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Files written:" -ForegroundColor White
Write-Host "  runtime\validity_filter.py   <- drop-in, no edits needed" -ForegroundColor Green
Write-Host "  runtime\drift_guard.py       <- drop-in, no edits needed" -ForegroundColor Green
Write-Host "  runtime\__init__.py          <- exports appended" -ForegroundColor Green
Write-Host "  freeze_baseline.py           <- run manually from shell" -ForegroundColor Green
Write-Host "  meta_learner_patch.py        <- shows what to add to meta_learner.py" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Run MECOS for one full cycle to generate metrics:" -ForegroundColor Gray
Write-Host "       python main.py" -ForegroundColor Yellow
Write-Host ""
Write-Host "  2. Freeze the baseline:" -ForegroundColor Gray
Write-Host "       python freeze_baseline.py" -ForegroundColor Yellow
Write-Host ""
Write-Host "  3. Verify it locked correctly:" -ForegroundColor Gray
Write-Host "       python freeze_baseline.py --show" -ForegroundColor Yellow
Write-Host ""
Write-Host "  4. Apply the two patches from meta_learner_patch.py to meta_learner.py" -ForegroundColor Gray
Write-Host "       python meta_learner_patch.py   <- prints the exact code blocks" -ForegroundColor Yellow
Write-Host ""
Write-Host "  5. After any future good burn, verify drift:" -ForegroundColor Gray
Write-Host "       python freeze_baseline.py --verify" -ForegroundColor Yellow
Write-Host ""
