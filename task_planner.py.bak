"""
MECOS Cognition Layer — Task Planner
Phase-aware planning for autonomous runtime goals.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    layer: str = "core"
    phase: str = "foundation"
    status: str = "PENDING"
    subtasks: List["Task"] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class TaskPlanner:
    def __init__(self):
        self.active_plan: List[Task] = []

    def create_plan(self, goal: str) -> List[Task]:
        plan = [
            Task(
                title="Local Orchestrator Boot",
                description=f"Initialize autonomous runtime for goal: {goal}",
                layer="orchestration",
                phase="foundation",
            ),
            Task(
                title="Memory Synchronization",
                description="Load vector memory and knowledge graph context",
                layer="memory",
                phase="foundation",
            ),
            Task(
                title="Autonomous Research Sweep",
                description="Crawl and analyze local-first knowledge sources",
                layer="research",
                phase="learning",
            ),
            Task(
                title="Coding and Sandbox Iteration",
                description="Generate/refactor code and validate in sandbox",
                layer="coding",
                phase="learning",
            ),
            Task(
                title="Evolution Scoring",
                description="Benchmark outcomes and feed self-improvement loop",
                layer="evolution",
                phase="evolution",
            ),
            Task(
                title="Trading Performance Review",
                description="Ingest Sharpe and drawdown metrics into optimization loop",
                layer="trading",
                phase="evolution",
            ),
        ]
        self.active_plan = plan
        return plan

    def update_task_status(self, task_id: str, status: str):
        for task in self.active_plan:
            if task.id == task_id:
                task.status = status
                return
            for subtask in task.subtasks:
                if subtask.id == task_id:
                    subtask.status = status
                    return

