"""
MECOS Orchestration Layer — Autonomous Orchestrator
Central coordinator for cognition/research/coding/memory/evolution layers.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from loguru import logger

from task_planner import TaskPlanner, Task


class AutonomousOrchestrator:
    def __init__(self):
        self.planner = TaskPlanner()
        self.is_running = False
        self.layer_priority = {
            "research": 100,
            "memory": 85,
            "coding": 80,
            "orchestration": 70,
            "evolution": 60,
        }
        self.max_tasks_per_run = 8
        logger.info("AutonomousOrchestrator initialized")

    async def run_goal(self, goal: str):
        self.is_running = True
        start = time.monotonic()
        plan = self.planner.create_plan(goal)
        plan = sorted(plan, key=lambda t: self.layer_priority.get(t.layer, 10), reverse=True)
        plan = plan[: self.max_tasks_per_run]
        logger.info(f"Goal '{goal}' -> {len(plan)} tasks")
        completed = 0
        for task in plan:
            if not self.is_running:
                break
            await self._dispatch_task(task)
            completed += 1
        self.is_running = False
        logger.info("Goal execution completed")
        elapsed = max(time.monotonic() - start, 1e-6)
        return {
            "goal": goal,
            "total_tasks": len(plan),
            "completed_tasks": completed,
            "efficiency": completed / max(len(plan), 1),
            "tasks_per_second": completed / elapsed,
        }

    async def _dispatch_task(self, task: Task):
        task.status = "RUNNING"
        logger.info(f"Dispatching [{task.phase}:{task.layer}] {task.title}")
        await asyncio.sleep(0.2)
        task.status = "COMPLETED"

    def stop(self):
        self.is_running = False
        logger.warning("Orchestrator stop requested")

    def set_compute_budget(self, max_tasks_per_run: int):
        self.max_tasks_per_run = max(1, int(max_tasks_per_run))

    def set_layer_priority(self, layer: str, priority: int):
        self.layer_priority[str(layer)] = int(priority)

