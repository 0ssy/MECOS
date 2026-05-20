import os
from pathlib import Path
from loguru import logger
from memory_system import MemorySystem
from app_controller import AppController
from app_perception import AppPerception

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
        self.file_perception = FilePerception(memory_system)
        self.app_perception = AppPerception(memory_system, app_controller or AppController())

    async def collect(self, data_dir: str):
        """Perform a collection cycle."""
        logger.info("Starting perception collection cycle...")
        await self.file_perception.scan_directory(data_dir)
        await self.app_perception.map_computer()
