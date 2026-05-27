"""
MECOS Orchestration Layer — Autonomous Orchestrator
Central coordinator for cognition/research/coding/memory/evolution layers.
"""
from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from task_planner import TaskPlanner, Task


class AutonomousOrchestrator:
    def __init__(self):
        self.planner = TaskPlanner()
        self.is_running = False
        logger.info("AutonomousOrchestrator initialized")

    async def run_goal(self, goal: str):
        self.is_running = True
        plan = self.planner.create_plan(goal)
        logger.info(f"Goal '{goal}' -> {len(plan)} tasks")
        for task in plan:
            if not self.is_running:
                break
            await self._dispatch_task(task)
        self.is_running = False
        logger.info("Goal execution completed")

    async def _dispatch_task(self, task: Task):
        task.status = "RUNNING"
        logger.info(f"Dispatching [{task.phase}:{task.layer}] {task.title}")
        await asyncio.sleep(0.2)
        task.status = "COMPLETED"

    def stop(self):
        self.is_running = False
        logger.warning("Orchestrator stop requested")

