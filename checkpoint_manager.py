"""
MECOS Phase 7 - Checkpoint Manager
Full system state snapshots, versioned checkpoints, rollback capability,
and incremental state diffing for safe evolution.
"""

import asyncio
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from loguru import logger

from config import settings


class CheckpointManager:
    """
    Manages system state checkpoints for MECOS.
    Supports creating, listing, comparing, and restoring checkpoints.
    """

    def __init__(self, max_checkpoints: int = 10):
        self.max_checkpoints = max_checkpoints
        self.checkpoint_dir = settings.MEMORY_DIR / "checkpoints"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.checkpoint_dir / "manifest.json"
        self.manifest: List[Dict[str, Any]] = self._load_manifest()
        logger.info(f"CheckpointManager initialized: {len(self.manifest)} checkpoints")

    def _load_manifest(self) -> List[Dict[str, Any]]:
        if self.manifest_path.exists():
            return json.loads(self.manifest_path.read_text())
        return []

    def _save_manifest(self):
        self.manifest_path.write_text(json.dumps(self.manifest, default=str))

    def _get_state_files(self) -> List[Path]:
        """Return all state files that should be included in a checkpoint."""
        state_patterns = [
            "*.json",
            "rl/*.json",
            "ssl/*.json",
            "curriculum/*.json",
            "consolidation/*.json",
            "benchmarks/*.json",
            "evolution/*.json",
            "meta/*.json",
        ]
        files = []
        for pattern in state_patterns:
            files.extend(settings.MEMORY_DIR.glob(pattern))
        return files

    async def create_checkpoint(self, label: str = "", metadata: Optional[Dict] = None) -> str:
        """
        Create a full system state checkpoint.
        Returns the checkpoint ID.
        """
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        checkpoint_id = f"ckpt_{ts}"
        checkpoint_path = self.checkpoint_dir / checkpoint_id
        checkpoint_path.mkdir(exist_ok=True)

        # Copy all state files
        state_files = self._get_state_files()
        copied = 0
        for src in state_files:
            try:
                rel = src.relative_to(settings.MEMORY_DIR)
                dst = checkpoint_path / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                copied += 1
            except Exception as e:
                logger.warning(f"Could not checkpoint {src}: {e}")

        # Save checkpoint metadata
        entry = {
            "id": checkpoint_id,
            "timestamp": datetime.now().isoformat(),
            "label": label or f"Checkpoint {len(self.manifest) + 1}",
            "files_saved": copied,
            "metadata": metadata or {},
        }
        self.manifest.append(entry)

        # Prune old checkpoints
        if len(self.manifest) > self.max_checkpoints:
            oldest = self.manifest.pop(0)
            old_path = self.checkpoint_dir / oldest["id"]
            if old_path.exists():
                shutil.rmtree(old_path)
                logger.info(f"Pruned old checkpoint: {oldest['id']}")

        self._save_manifest()
        logger.info(f"Checkpoint created: {checkpoint_id} ({copied} files)")
        return checkpoint_id

    async def restore_checkpoint(self, checkpoint_id: str) -> bool:
        """
        Restore system state from a checkpoint.
        Creates a backup of current state before restoring.
        """
        checkpoint_path = self.checkpoint_dir / checkpoint_id
        if not checkpoint_path.exists():
            logger.error(f"Checkpoint not found: {checkpoint_id}")
            return False

        # Backup current state first
        backup_id = await self.create_checkpoint(label=f"pre_restore_backup_for_{checkpoint_id}")
        logger.info(f"Current state backed up as: {backup_id}")

        # Restore files
        restored = 0
        for src in checkpoint_path.rglob("*"):
            if src.is_file():
                try:
                    rel = src.relative_to(checkpoint_path)
                    dst = settings.MEMORY_DIR / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    restored += 1
                except Exception as e:
                    logger.warning(f"Could not restore {src}: {e}")

        logger.info(f"Checkpoint restored: {checkpoint_id} ({restored} files)")
        return True

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """Return a list of all available checkpoints."""
        return list(reversed(self.manifest))  # Most recent first

    def get_checkpoint_info(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """Return metadata for a specific checkpoint."""
        return next((c for c in self.manifest if c["id"] == checkpoint_id), None)

    def diff_checkpoints(self, id1: str, id2: str) -> Dict[str, Any]:
        """Compare two checkpoints and return a diff summary."""
        path1 = self.checkpoint_dir / id1
        path2 = self.checkpoint_dir / id2

        if not path1.exists() or not path2.exists():
            return {"error": "One or both checkpoints not found"}

        files1 = {str(f.relative_to(path1)) for f in path1.rglob("*") if f.is_file()}
        files2 = {str(f.relative_to(path2)) for f in path2.rglob("*") if f.is_file()}

        added = files2 - files1
        removed = files1 - files2
        common = files1 & files2

        # Check for modified files
        modified = []
        for f in common:
            content1 = (path1 / f).read_text(errors="ignore")
            content2 = (path2 / f).read_text(errors="ignore")
            if content1 != content2:
                modified.append(f)

        return {
            "checkpoint_1": id1,
            "checkpoint_2": id2,
            "added": list(added),
            "removed": list(removed),
            "modified": modified,
            "total_changes": len(added) + len(removed) + len(modified),
        }
