from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

from config import settings
from .state_checkpoint import StateCheckpoint


class CrashRecovery:
    def __init__(self, checkpoint: StateCheckpoint):
        self.checkpoint = checkpoint
        self.crash_dir: Path = settings.LOGS_DIR / "crash_reports"
        self.crash_dir.mkdir(parents=True, exist_ok=True)

    async def record_crash(
        self,
        error: Exception,
        runtime_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.crash_dir / f"crash_{ts}.json"
        report = {
            "timestamp": datetime.now().isoformat(),
            "error_type": type(error).__name__,
            "error": str(error),
            "runtime_state": runtime_state or {},
        }
        report_path.write_text(json.dumps(report, default=str, indent=2), encoding="utf-8")
        logger.error(f"Crash report recorded: {report_path}")

        checkpoint_id = await self.checkpoint.create_checkpoint(
            label="crash_snapshot",
            metadata={"error_type": type(error).__name__, "report": str(report_path)},
        )
        report["checkpoint_id"] = checkpoint_id
        return report

