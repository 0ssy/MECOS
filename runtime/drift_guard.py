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

    def add_anchor(self, description: str, source: str = "system") -> str:
        """Store a trusted memory anchor entry."""
        anchor_path = Path("data/trusted_memory_anchors.json")
        anchor_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing anchors (temporarily make writable if needed)
        anchors = {}
        if anchor_path.exists():
            try:
                import stat as _stat
                anchor_path.chmod(_stat.S_IRUSR | _stat.S_IWUSR)
                with open(anchor_path) as f:
                    anchors = json.load(f)
            except Exception:
                pass

        # Add the new anchor
        key = f"anchor_{int(time.time())}"
        anchors[key] = {
            "description": description,
            "source": source,
            "created_at": time.time(),
            "created_at_human": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        with open(anchor_path, "w") as f:
            json.dump(anchors, f, indent=2)

        # Re-lock read-only
        import stat as _stat
        anchor_path.chmod(_stat.S_IRUSR | _stat.S_IRGRP | _stat.S_IROTH)

        logger.info(f"[DriftGuard] Anchor added: '{description}' (source={source})")
        return key


    def evaluate(self, current_scores: Dict[str, float]) -> dict:
        """
        Compatible with main.py — returns a dict with:
          drift_detected: bool
          average_delta:  float
          events:         list of DriftEvent dicts
        """
        events = self.check(current_scores)
        regressions = [e for e in events if e.direction == "REGRESSION"]
        average_delta = (
            sum(e.delta for e in regressions) / len(regressions)
            if regressions else 0.0
        )
        return {
            "drift_detected": len(regressions) > 0,
            "average_delta": average_delta,
            "regression_count": len(regressions),
            "improvement_count": len([e for e in events if e.direction == "IMPROVEMENT"]),
            "events": [asdict(e) for e in events],
        }
