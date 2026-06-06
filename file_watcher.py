from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from loguru import logger
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer


class MECOSFileWatcher(FileSystemEventHandler):
    """
    Watches directories for file activity and auto-learns new file types.
    """

    def __init__(self, perception, loop: Optional[asyncio.AbstractEventLoop] = None):
        self.perception = perception
        self.seen_extensions: set[str] = set()
        self.loop = loop

    def _schedule_learn(self, ext: str) -> None:
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.perception.learn_file_type(ext), self.loop)
            return

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.perception.learn_file_type(ext))
        except RuntimeError:
            logger.warning("No active event loop; skipping learn_file_type for {}", ext)

    def _handle_path(self, src_path: str) -> None:
        ext = Path(src_path).suffix.lower()
        if not ext or ext in self.seen_extensions:
            return
        self.seen_extensions.add(ext)
        self._schedule_learn(ext)
        logger.info("New file type encountered: {}", ext)

    def on_created(self, event: FileSystemEvent):
        if event.is_directory:
            return
        self._handle_path(event.src_path)

    def on_opened(self, event: FileSystemEvent):
        if event.is_directory:
            return
        self._handle_path(event.src_path)


def start_file_watcher(perception, watch_dirs: Optional[list[str]] = None) -> Observer:
    dirs = watch_dirs or [
        str(Path.home()),
        str(Path.home() / "Downloads"),
        str(Path.home() / "Desktop"),
        str(Path.home() / "Documents"),
    ]

    loop: Optional[asyncio.AbstractEventLoop] = None
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    observer = Observer()
    handler = MECOSFileWatcher(perception=perception, loop=loop)
    for raw_dir in dirs:
        d = Path(raw_dir).expanduser()
        if d.exists():
            observer.schedule(handler, str(d), recursive=False)
    observer.start()
    logger.info("File watcher started for {} directories", len(dirs))
    return observer

