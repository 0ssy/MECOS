import asyncio
from pathlib import Path
from typing import Optional

from loguru import logger

from app_perception import AppPerception
from app_controller import AppController
from file_watcher import start_file_watcher
from memory_system import MemorySystem
from screen_perception import ScreenPerception
from screen_reader import ScreenReader

class FilePerception:
    def __init__(self, memory_system: MemorySystem):
        self.memory = memory_system
        self.supported_extensions = {'.txt', '.md', '.py', '.js', '.json', '.pdf'}

    async def scan_directory(self, directory_path: str):
        """Recursively scan a directory and ingest supported files."""
        path = Path(directory_path)
        if not path.exists():
            logger.warning(f"Directory {directory_path} does not exist.")
            return

        for file_path in path.rglob('*'):
            if file_path.suffix in self.supported_extensions:
                await self.ingest_file(file_path)

    async def ingest_file(self, file_path: Path):
        """Read and store file content in memory."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                await self.memory.add_experience(
                    content=f"FILE CONTENT ({file_path.name}):\n{content}",
                    source="file_perception"
                )
                logger.info(f"Ingested file: {file_path}")
        except Exception as e:
            logger.error(f"Failed to ingest {file_path}: {e}")

class PerceptionLayer:
    def __init__(self, memory_system: MemorySystem, app_controller: AppController = None):
        self.memory = memory_system
        self.file_perception = FilePerception(memory_system)
        self.app_perception = AppPerception(memory_system, app_controller or AppController())
        self.screen_perception = ScreenPerception(memory_system)
        self.screen_reader = ScreenReader()
        self._file_watcher_observer = None
        self._app_observation_task: Optional[asyncio.Task] = None
        self._screen_observation_task: Optional[asyncio.Task] = None

    async def collect(self, data_dir: str):
        """Perform a collection cycle."""
        logger.info("Starting perception collection cycle...")
        await self.file_perception.scan_directory(data_dir)
        await self.app_perception.map_computer()
        await self.screen_perception.collect()

    async def _screen_observation_loop(self, interval_seconds: int = 45):
        interval = max(10, int(interval_seconds))
        while True:
            try:
                await self.screen_perception.collect()
                active_text = self.screen_reader.read_active_window()
                if active_text and active_text.strip():
                    await self.memory.add_experience(
                        content=f"ACTIVE WINDOW OCR:\n{active_text}",
                        source="screen_reader",
                    )
            except Exception as exc:
                logger.warning("Screen observation loop error: {}", exc)
            await asyncio.sleep(interval)

    async def start_background_observation(
        self,
        data_dir: str = "data",
        app_interval_seconds: int = 30,
        screen_interval_seconds: int = 45,
        watch_files: bool = True,
        watch_dirs: Optional[list[str]] = None,
    ):
        if self._app_observation_task and not self._app_observation_task.done():
            logger.debug("Background perception observation already running.")
            return

        await self.collect(data_dir)

        if watch_files and self._file_watcher_observer is None:
            self._file_watcher_observer = start_file_watcher(self.app_perception, watch_dirs=watch_dirs)

        self._app_observation_task = asyncio.create_task(
            self.app_perception.start_continuous_observation(interval_seconds=app_interval_seconds)
        )
        self._screen_observation_task = asyncio.create_task(
            self._screen_observation_loop(interval_seconds=screen_interval_seconds)
        )
        logger.info(
            "Background perception started | app_interval={}s screen_interval={}s watcher={}",
            max(5, int(app_interval_seconds)),
            max(10, int(screen_interval_seconds)),
            watch_files,
        )

    async def stop_background_observation(self):
        for task in (self._app_observation_task, self._screen_observation_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._app_observation_task = None
        self._screen_observation_task = None

        if self._file_watcher_observer is not None:
            self._file_watcher_observer.stop()
            self._file_watcher_observer.join(timeout=5)
            self._file_watcher_observer = None

        logger.info("Background perception stopped.")
