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
        baseline_path: str = "data/benchmark_baseline.json",
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
    baseline_path: str = "data/benchmark_baseline.json",
) -> Tuple[ValidityFilter, TrustedScoreStore]:
    vf    = ValidityFilter(audit_rate=audit_rate, baseline_path=baseline_path)
    store = TrustedScoreStore(vf)
    return vf, store


def freeze_baseline(
    current_scores: Dict[str, float],
    baseline_path: str = "data/benchmark_baseline.json",
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

