"""
MECOS Phase 4 - File Operations
Safe file read/write/search/manipulation with permission controls,
directory traversal protection, and backup/rollback mechanism.
"""

import shutil
import json
import csv
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from loguru import logger

from config import settings



    def _normalize_path(self, path: str) -> Path:
        """Normalize path - strip /data/ prefix that LLM often adds."""
        # Strip leading /data/ or data/
        if path.startswith('/data/'):
            path = path[6:]
        elif path.startswith('data/'):
            path = path[5:]
        
        # Remove leading slashes
        path = path.lstrip('/\\')
        
        return self.base_dir / path


class FileOperations:
    """
    Safe file system operations with sandboxing and rollback support.
    All write operations are restricted to the DATA_DIR unless explicitly overridden.
    """

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or settings.DATA_DIR
        self.backup_dir = settings.DATA_DIR / "_backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"FileOperations initialized. Base: {self.base_dir}")

    def _safe_path(self, path: str) -> Path:
        """Resolve a path and ensure it stays within base_dir."""
        resolved = self._normalize_path(path).resolve()
        try:
            resolved.relative_to(self.base_dir.resolve())
        except ValueError:
            raise PermissionError(
                f"Path traversal blocked: '{path}' resolves outside base_dir '{self.base_dir}'"
            )
        return resolved

    # ------------------------------------------------------------------ #
    # Read Operations
    # ------------------------------------------------------------------ #

    def read_text(self, path: str) -> str:
        """Read a text file and return its content."""
        p = self._safe_path(path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")
        content = p.read_text(encoding="utf-8", errors="ignore")
        logger.debug(f"Read file: {p} ({len(content)} chars)")
        return content

    def read_json(self, path: str) -> Any:
        """Read and parse a JSON file."""
        return json.loads(self.read_text(path))

    def read_csv(self, path: str) -> List[Dict[str, str]]:
        """Read a CSV file and return a list of row dicts."""
        p = self._safe_path(path)
        rows = []
        with p.open(encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(dict(row))
        logger.debug(f"Read CSV: {p} ({len(rows)} rows)")
        return rows

    def list_directory(self, path: str = ".", pattern: str = "*") -> List[str]:
        """List files in a directory matching a glob pattern."""
        p = self._safe_path(path)
        if not p.is_dir():
            raise NotADirectoryError(f"Not a directory: {p}")
        files = [str(f.relative_to(self.base_dir)) for f in p.rglob(pattern) if f.is_file()]
        logger.debug(f"Listed {len(files)} files in {p}")
        return files

    def search_files(self, query: str, path: str = ".", extensions: Optional[List[str]] = None) -> List[Dict[str, str]]:
        """Search file contents for a query string. Returns list of {file, snippet}."""
        p = self._safe_path(path)
        results = []
        exts = set(extensions or [".txt", ".md", ".py", ".json", ".csv", ".log"])
        for f in p.rglob("*"):
            if f.is_file() and f.suffix in exts:
                try:
                    content = f.read_text(encoding="utf-8", errors="ignore")
                    if query.lower() in content.lower():
                        idx = content.lower().find(query.lower())
                        snippet = content[max(0, idx - 50): idx + 150].strip()
                        results.append({
                            "file": str(f.relative_to(self.base_dir)),
                            "snippet": snippet,
                        })
                except Exception:
                    pass
        logger.debug(f"Search '{query}' found {len(results)} results")
        return results

    # ------------------------------------------------------------------ #
    # Write Operations
    # ------------------------------------------------------------------ #

    def _backup(self, path: Path):
        """Create a timestamped backup of a file before overwriting."""
        if path.exists():
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.backup_dir / f"{path.name}.{ts}.bak"
            shutil.copy2(path, backup_path)
            logger.debug(f"Backup created: {backup_path}")

    def write_text(self, path: str, content: str, backup: bool = True) -> str:
        """Write text content to a file, optionally backing up the original."""
        p = self._safe_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if backup:
            self._backup(p)
        p.write_text(content, encoding="utf-8")
        logger.info(f"Wrote file: {p} ({len(content)} chars)")
        return str(p)

    def append_text(self, path: str, content: str) -> str:
        """Append text to a file."""
        p = self._safe_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(content)
        logger.debug(f"Appended to file: {p}")
        return str(p)

    def write_json(self, path: str, data: Any, indent: int = 2) -> str:
        """Serialize data to JSON and write to file."""
        return self.write_text(path, json.dumps(data, indent=indent, default=str))

    def delete_file(self, path: str, backup: bool = True) -> bool:
        """Delete a file, optionally backing it up first."""
        p = self._safe_path(path)
        if not p.exists():
            return False
        if backup:
            self._backup(p)
        p.unlink()
        logger.info(f"Deleted file: {p}")
        return True

    def copy_file(self, src: str, dst: str) -> str:
        """Copy a file within the base_dir."""
        src_p = self._safe_path(src)
        dst_p = self._safe_path(dst)
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_p, dst_p)
        logger.info(f"Copied {src_p} → {dst_p}")
        return str(dst_p)

    def move_file(self, src: str, dst: str) -> str:
        """Move a file within the base_dir."""
        src_p = self._safe_path(src)
        dst_p = self._safe_path(dst)
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_p), str(dst_p))
        logger.info(f"Moved {src_p} → {dst_p}")
        return str(dst_p)

    # ------------------------------------------------------------------ #
    # Rollback
    # ------------------------------------------------------------------ #

    def list_backups(self, filename: str) -> List[str]:
        """List all backups for a given filename."""
        backups = sorted(self.backup_dir.glob(f"{filename}.*.bak"))
        return [str(b) for b in backups]

    def restore_backup(self, filename: str, backup_path: Optional[str] = None) -> bool:
        """Restore the most recent backup (or a specific one) for a file."""
        if backup_path:
            src = Path(backup_path)
        else:
            backups = self.list_backups(filename)
            if not backups:
                logger.warning(f"No backups found for: {filename}")
                return False
            src = Path(backups[-1])

        dst = self._safe_path(filename)
        shutil.copy2(src, dst)
        logger.info(f"Restored {filename} from {src}")
        return True
