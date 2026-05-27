from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

from checkpoint_manager import CheckpointManager
from config import settings


class StateCheckpoint:
    def __init__(self):
        self.manager = CheckpointManager()
        self.runtime_state_path: Path = settings.DATA_DIR / "runtime_state.json"

    async def save_runtime_state(self, state: Dict[str, Any]):
        payload = {
            "timestamp": datetime.now().isoformat(),
            "state": state,
        }
        self.runtime_state_path.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
        logger.info(f"Runtime state saved: {self.runtime_state_path}")

    def load_runtime_state(self) -> Optional[Dict[str, Any]]:
        if not self.runtime_state_path.exists():
            return None
        return json.loads(self.runtime_state_path.read_text(encoding="utf-8"))

    async def create_checkpoint(self, label: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        return await self.manager.create_checkpoint(label=label, metadata=metadata or {})

