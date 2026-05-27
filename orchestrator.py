"""
MECOS Orchestration Layer — Autonomous Orchestrator
Central coordinator for cognition/research/coding/memory/evolution layers.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict

from loguru import logger

from task_planner import TaskPlanner, Task


class AutonomousOrchestrator:
    def __init__(self, components: Dict[str, Any] | None = None):
        self.planner = TaskPlanner()
        self.is_running = False
        self.components: Dict[str, Any] = {}
        self.layer_priority = {
            "research": 100,
            "trading": 90,
            "memory": 85,
            "coding": 80,
            "orchestration": 70,
            "evolution": 60,
        }
        self.max_tasks_per_run = 8
        if components:
            self.attach_components(components)
        logger.info("AutonomousOrchestrator initialized")

    def attach_components(self, components: Dict[str, Any]):
        self.components.update(components or {})

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
        handlers = {
            "research": self._dispatch_research,
            "memory": self._dispatch_memory,
            "coding": self._dispatch_coding,
            "trading": self._dispatch_trading,
            "evolution": self._dispatch_evolution,
            "orchestration": self._dispatch_orchestration,
        }
        handler = handlers.get(task.layer, self._dispatch_generic)
        try:
            await handler(task)
            task.status = "COMPLETED"
        except Exception:
            task.status = "FAILED"
            raise

    async def _dispatch_research(self, task: Task):
        research_agent = self.components.get("research_agent")
        if not research_agent:
            await asyncio.sleep(0)
            return
        topic = task.description or task.title
        if hasattr(research_agent, "crawl_web"):
            await research_agent.crawl_web([topic])
            return
        if hasattr(research_agent, "deep_research"):
            await research_agent.deep_research(topic, depth=1)

    async def _dispatch_memory(self, task: Task):
        memory = self.components.get("memory")
        if not memory:
            await asyncio.sleep(0)
            return
        query = task.description or task.title
        if hasattr(memory, "retrieve_context"):
            await memory.retrieve_context(query, n_results=3)
            return
        if hasattr(memory, "search"):
            memory.search(query)

    async def _dispatch_coding(self, task: Task):
        coding_agent = self.components.get("coding_agent")
        if not coding_agent:
            await asyncio.sleep(0)
            return
        if hasattr(coding_agent, "build_module"):
            await coding_agent.build_module("runtime_probe", task.description or task.title)
            return
        if hasattr(coding_agent, "generate_code"):
            await coding_agent.generate_code(task.description or task.title)

    async def _dispatch_trading(self, task: Task):
        trading_system = self.components.get("trading_system")
        if not trading_system:
            await asyncio.sleep(0)
            return
        performance_monitor = getattr(trading_system, "performance_monitor", None)
        metrics = performance_monitor.get_metrics() if performance_monitor else {}
        self.components["latest_trading_metrics"] = metrics
        status = trading_system.get_status() if hasattr(trading_system, "get_status") else {}
        self.components["latest_trading_status"] = status

    async def _dispatch_evolution(self, task: Task):
        evolution_agent = self.components.get("evolution_agent")
        if not evolution_agent:
            await asyncio.sleep(0)
            return
        trading_metrics = self.components.get("latest_trading_metrics", {})
        if trading_metrics and hasattr(evolution_agent, "ingest_trading_performance"):
            await evolution_agent.ingest_trading_performance(trading_metrics)
            return
        if hasattr(evolution_agent, "run_benchmark"):
            await evolution_agent.run_benchmark("runtime_orchestration", {"success_rate": 1.0})

    async def _dispatch_orchestration(self, task: Task):
        router = self.components.get("runtime_router")
        if not router:
            await asyncio.sleep(0)
            return
        if hasattr(router, "route_request"):
            await router.route_request(task.description or task.title, "long_term_planning")

    async def _dispatch_generic(self, task: Task):
        await asyncio.sleep(0)

    def stop(self):
        self.is_running = False
        logger.warning("Orchestrator stop requested")

    def set_compute_budget(self, max_tasks_per_run: int):
        self.max_tasks_per_run = max(1, int(max_tasks_per_run))

    def set_layer_priority(self, layer: str, priority: int):
        self.layer_priority[str(layer)] = int(priority)

