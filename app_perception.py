"""
MECOS App Perception
Learns local application landscape and captures workflow traces.
"""

import asyncio
from datetime import datetime
from loguru import logger

from memory_system import MemorySystem
from app_controller import AppController
from config import settings


class AppPerception:
    def __init__(self, memory_system: MemorySystem, controller: AppController):
        self.memory = memory_system
        self.controller = controller

    async def map_computer(self):
        """Capture a system-wide app/process map and store it."""
        machine_map = self.controller.map_computer(
            process_limit=settings.APP_PERCEPTION_MAX_PROCESSES,
            executable_limit=settings.APP_PERCEPTION_MAX_EXECUTABLES,
        )
        await self.memory.add_experience(
            content=f"APP MAP [{datetime.now().isoformat()}]: {machine_map}",
            source="app_perception",
        )
        logger.info(
            "App perception mapped machine: "
            f"{len(machine_map.get('running_processes', []))} processes, "
            f"{len(machine_map.get('installed_executables', []))} executables."
        )
        return machine_map

    async def learn_workflow(self, workflow_name: str, commands: list, timeout: int = 30):
        """
        Learn a command-driven workflow by executing each step and saving outputs.
        Commands must pass AppController allowlist.
        """
        traces = []
        for index, command in enumerate(commands, start=1):
            result = await self.controller.run_command(command, timeout=timeout)
            traces.append(
                {
                    "step": index,
                    "command": command,
                    "exit_code": result.get("exit_code", "-1"),
                    "stdout": (result.get("stdout", "") or "")[:1500],
                    "stderr": (result.get("stderr", "") or "")[:500],
                }
            )
            await asyncio.sleep(0)

        payload = {
            "workflow": workflow_name,
            "timestamp": datetime.now().isoformat(),
            "steps": traces,
        }
        await self.memory.add_experience(
            content=f"APP WORKFLOW TRACE: {payload}",
            source="app_workflow_learning",
        )
        logger.info(f"Captured workflow '{workflow_name}' with {len(traces)} steps.")
        return payload
