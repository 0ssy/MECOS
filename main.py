"""
MECOS Unified Runtime Entry Point.
Connects cognition, research, perception, coding, orchestration, memory, and trading.
"""
from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

from action_engine import ActionExecutionEngine
from agent_coordinator import AgentCoordinator, AgentRole
from app_controller import AppController
from coding_agent import CodingAgent as CoreCodingAgent
from continuous_loop import ContinuousResearchLoop
from engineer import CodingAgent as RuntimeCodingAgent
from engineer import SandboxExecutor as RuntimeSandboxExecutor
from knowledge_graph import KnowledgeGraph as RuntimeKnowledgeGraph
from memory_system import MemorySystem
from model_router import ModelRouter
from orchestrator import AutonomousOrchestrator
from perception import PerceptionLayer
from reasoner import Reasoner
from research_agent import ResearchAgent as CoreResearchAgent
from runtime import (
    CrashRecovery,
    DriftGuard,
    ExecutionGuard,
    HealthMonitor,
    ResearchGovernor,
    RuntimeBenchmarkHarness,
    RuntimeWatchdog,
    StateCheckpoint,
)
from self_debug import SelfDebugger
from self_improvement import EvolutionAgent
from tool_orchestrator import ToolOrchestrator
from trading.trading_system import TradingSystem
from trading_agent import TradingAgent as QuantTradingAgent
from vector_memory import VectorMemory as RuntimeVectorMemory
from web_perception import WebPerception
from analyzer import ResearchAgent as RuntimeResearchAgent


class UnifiedMECOSRuntime:
    def __init__(self, trading_execution_mode: str = "paper"):
        self.memory: Optional[MemorySystem] = None
        self.web: Optional[WebPerception] = None
        self.trading_system: Optional[TradingSystem] = None
        self._trading_task: Optional[asyncio.Task] = None
        self.connection_state: Dict[str, bool] = {}
        self.components: Dict[str, Any] = {}
        self.trading_execution_mode = str(trading_execution_mode or "paper").strip().lower()
        self.health_monitor = HealthMonitor(stale_threshold_seconds=45.0)
        self.execution_guard = ExecutionGuard(default_timeout_seconds=120.0, retries=1)
        self.state_checkpoint = StateCheckpoint()
        self.crash_recovery = CrashRecovery(self.state_checkpoint)
        self.benchmark_harness = RuntimeBenchmarkHarness()
        self.drift_guard = DriftGuard()
        self.research_governor = ResearchGovernor()
        self.watchdog = RuntimeWatchdog(
            monitor=self.health_monitor,
            on_stale_component=self._on_stale_component,
            interval_seconds=10.0,
        )
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def _on_stale_component(self, component: str, stale_for_seconds: float):
        logger.warning(f"Recovery signal: component={component} stale_for={stale_for_seconds:.1f}s")

    async def _heartbeat_loop(self):
        while True:
            self.health_monitor.heartbeat("runtime_main")
            if self._trading_task and not self._trading_task.done():
                self.health_monitor.heartbeat("trading_loop")
            await asyncio.sleep(5)

    async def startup(self):
        self.drift_guard.add_anchor("Stability before expansion", source="operator_policy")
        self.health_monitor.mark_started("runtime_main")
        await self.watchdog.start()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        self.memory = MemorySystem()
        self.connection_state["memory"] = True
        self.components["memory"] = self.memory
        self.health_monitor.mark_started("memory")

        app_controller = AppController()
        perception = PerceptionLayer(self.memory, app_controller)
        self.connection_state["perception"] = True
        self.components["app_controller"] = app_controller
        self.components["perception"] = perception
        self.health_monitor.mark_started("perception")

        self.web = WebPerception(self.memory)
        try:
            await self.web.startup()
            self.connection_state["web_perception"] = True
        except Exception as exc:
            logger.warning(f"Web perception startup failed: {exc}")
            self.connection_state["web_perception"] = False
        self.components["web_perception"] = self.web
        self.health_monitor.mark_started("web_perception")

        tools = ToolOrchestrator()
        tools.web_perception = self.web
        action_engine = ActionExecutionEngine(tools, self.memory)
        reasoner = await self.execution_guard.run("reasoner_init", asyncio.to_thread(Reasoner, self.memory))
        self.connection_state["reasoning"] = True
        self.components["tools"] = tools
        self.components["action_engine"] = action_engine
        self.components["reasoner"] = reasoner
        self.health_monitor.mark_started("reasoning")

        core_coding = CoreCodingAgent(self.memory, tools)
        core_research = CoreResearchAgent(self.memory, self.web)
        coordinator = AgentCoordinator(self.memory)
        self.connection_state["core_coding"] = True
        self.connection_state["core_research"] = True
        self.connection_state["agent_coordinator"] = True
        self.components["core_coding_agent"] = core_coding
        self.components["core_research_agent"] = core_research
        self.components["agent_coordinator"] = coordinator
        self.health_monitor.mark_started("agents")

        runtime_memory = RuntimeVectorMemory()
        runtime_graph = RuntimeKnowledgeGraph()
        runtime_research = RuntimeResearchAgent(memory_layer=runtime_memory)
        runtime_sandbox = RuntimeSandboxExecutor()
        runtime_coding = RuntimeCodingAgent(runtime_sandbox)
        runtime_debugger = SelfDebugger(runtime_sandbox)
        runtime_orchestrator = AutonomousOrchestrator()
        runtime_orchestrator.set_layer_priority("research", 120)
        runtime_orchestrator.set_compute_budget(10)
        runtime_evolution = EvolutionAgent(memory_layer=runtime_memory)
        runtime_router = ModelRouter(main_brain_url="http://192.168.1.88:11434")
        runtime_loop = ContinuousResearchLoop(runtime_research)

        self.connection_state["runtime_memory"] = True
        self.connection_state["runtime_knowledge_graph"] = True
        self.connection_state["runtime_research"] = True
        self.connection_state["runtime_coding"] = True
        self.connection_state["runtime_debugger"] = True
        self.connection_state["runtime_orchestrator"] = True
        self.connection_state["runtime_evolution"] = True
        self.connection_state["runtime_router"] = True

        self.components["runtime_memory"] = runtime_memory
        self.components["runtime_graph"] = runtime_graph
        self.components["runtime_research_agent"] = runtime_research
        self.components["runtime_sandbox"] = runtime_sandbox
        self.components["runtime_coding_agent"] = runtime_coding
        self.components["runtime_debugger"] = runtime_debugger
        self.components["runtime_orchestrator"] = runtime_orchestrator
        self.components["runtime_evolution"] = runtime_evolution
        self.components["runtime_router"] = runtime_router
        self.components["runtime_research_loop"] = runtime_loop
        self.health_monitor.mark_started("runtime_stack")

        try:
            quant_trading = QuantTradingAgent(self.memory, quant_mode="balanced")
            coordinator.register_agent("trading", quant_trading, AgentRole.TRADING)
            self.connection_state["quant_trading_agent"] = True
            self.components["quant_trading_agent"] = quant_trading
        except Exception as exc:
            logger.warning(f"Quant trading agent init failed: {exc}")
            self.connection_state["quant_trading_agent"] = False

        coordinator.register_agent("coding", core_coding, AgentRole.CODING)
        coordinator.register_agent("research", core_research, AgentRole.RESEARCH)

        try:
            self.trading_system = TradingSystem(
                memory_system=self.memory,
                quant_mode="balanced",
                execution_mode=self.trading_execution_mode,
            )
            self.connection_state["trading_system"] = True
            self.components["trading_system"] = self.trading_system
        except Exception as exc:
            logger.warning(f"TradingSystem init failed: {exc}")
            self.connection_state["trading_system"] = False

        await self.state_checkpoint.save_runtime_state(
            {
                "connection_state": self.connection_state,
                "trading_execution_mode": self.trading_execution_mode,
            }
        )
        await self.state_checkpoint.create_checkpoint(
            label="runtime_startup",
            metadata={"connection_state": self.connection_state},
        )
        logger.info(f"Unified MECOS startup complete: {self.connection_state}")

    async def run_runtime_demo(self):
        runtime_memory: RuntimeVectorMemory = self.components["runtime_memory"]
        runtime_graph: RuntimeKnowledgeGraph = self.components["runtime_graph"]
        runtime_research: RuntimeResearchAgent = self.components["runtime_research_agent"]
        runtime_coding: RuntimeCodingAgent = self.components["runtime_coding_agent"]
        runtime_debugger: SelfDebugger = self.components["runtime_debugger"]
        runtime_orchestrator: AutonomousOrchestrator = self.components["runtime_orchestrator"]
        runtime_evolution: EvolutionAgent = self.components["runtime_evolution"]
        runtime_router: ModelRouter = self.components["runtime_router"]
        runtime_loop: ContinuousResearchLoop = self.components["runtime_research_loop"]

        background = asyncio.create_task(runtime_loop.start(["autonomous runtime", "recursive engineering"]))
        await self.execution_guard.run(
            "runtime_research_analyze_repo",
            runtime_research.analyze_repo(str(Path(__file__).resolve().parent)),
        )
        module_code = await runtime_coding.build_module("diagnostic_tool", "runtime health checks")
        debug_result = {"success": True}
        if module_code:
            debug_result = await self.execution_guard.run(
                "runtime_debugger_verify_and_repair",
                runtime_debugger.verify_and_repair(module_code, "diagnostic_tool.py"),
                timeout_seconds=180.0,
            )

        runtime_graph.add_node("mecos_core", "runtime", {"mode": "local-first"})
        runtime_graph.add_node("sandbox", "component", {"purpose": "safe execution"})
        runtime_graph.add_edge("mecos_core", "sandbox", "uses")

        await self.execution_guard.run(
            "runtime_router_route_request",
            runtime_router.route_request("plan evolution", "long_term_planning"),
        )
        evolution_result = await runtime_evolution.run_benchmark("coding_agent", {"success_rate": 0.85})
        planning_summary = await runtime_orchestrator.run_goal("Evolve MECOS into sovereign autonomous runtime")

        runtime_loop.stop()
        background.cancel()
        try:
            await background
        except asyncio.CancelledError:
            pass

        found = runtime_memory.search("runtime")
        memory_retrieval = await self.memory.retrieve_context("runtime health", n_results=5) if self.memory else {"metadatas": [[]]}
        meta_rows = (memory_retrieval.get("metadatas") or [[]])[0]
        retrieval_scores = [
            float(m.get("retrieval_score", 0.0))
            for m in meta_rows
            if isinstance(m, dict) and isinstance(m.get("retrieval_score", 0.0), (int, float))
        ]
        memory_relevance = sum(retrieval_scores) / max(len(retrieval_scores), 1)
        research_metrics = runtime_research.get_metrics()
        research_governance = self.research_governor.evaluate(research_metrics)
        evolution_scores = [float(b.get("score", 0.0)) for b in runtime_evolution.benchmarks]
        evolution_delta = 0.0
        if len(evolution_scores) >= 2:
            evolution_delta = evolution_scores[-1] - evolution_scores[-2]
        coding_compile_success = 1.0 if module_code else 0.0
        debug_success = 1.0 if bool(debug_result.get("success", False)) else 0.0
        benchmark_metrics = {
            "research_useful_discoveries_per_hour": float(research_metrics.get("useful_discoveries_per_hour", 0.0)),
            "coding_compile_success_rate": coding_compile_success,
            "debug_repair_success_rate": debug_success,
            "memory_retrieval_relevance": float(memory_relevance),
            "evolution_benchmark_delta": float(evolution_delta),
            "planning_task_completion_efficiency": float(planning_summary.get("efficiency", 0.0)),
            "research_quality_index": float(research_governance.get("research_quality_index", 0.0)),
        }
        benchmark_entry = self.benchmark_harness.record(benchmark_metrics)
        previous = self.benchmark_harness.previous()
        delta = self.benchmark_harness.benchmark_delta(
            benchmark_metrics,
            previous.get("metrics", {}) if previous else None,
        )
        drift_status = self.drift_guard.evaluate(benchmark_metrics)
        if drift_status.get("drift_detected"):
            await self.state_checkpoint.create_checkpoint(
                label="drift_rollback_anchor",
                metadata={"drift_status": drift_status, "delta": delta},
            )
            logger.warning(
                f"Drift detected: average_delta={drift_status.get('average_delta', 0.0):.3f}. "
                "Rollback anchor checkpoint created."
            )
        self.components["benchmark_entry"] = benchmark_entry
        self.components["benchmark_delta"] = delta
        self.components["drift_status"] = drift_status
        self.components["research_governance"] = research_governance
        logger.info(f"Runtime demo complete. memory_hits={len(found)}")

    async def start_trading(self, run_seconds: int):
        if not self.trading_system:
            logger.warning("TradingSystem unavailable; skipping trading start")
            return
        self._trading_task = asyncio.create_task(self.trading_system.start(use_starter_universe=True))
        await asyncio.sleep(max(1, int(run_seconds)))
        self.trading_system.stop()
        if self._trading_task and not self._trading_task.done():
            self._trading_task.cancel()
            try:
                await self._trading_task
            except asyncio.CancelledError:
                pass
        logger.info("Trading segment stopped")

    async def shutdown(self):
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

        if self.trading_system:
            try:
                self.trading_system.stop()
            except Exception:
                pass
        if self.web:
            try:
                await self.web.shutdown()
            except Exception:
                pass
        await self.state_checkpoint.save_runtime_state(
            {
                "connection_state": self.connection_state,
                "trading_execution_mode": self.trading_execution_mode,
                "shutdown": True,
            }
        )
        await self.state_checkpoint.create_checkpoint(
            label="runtime_shutdown",
            metadata={"connection_state": self.connection_state},
        )
        await self.watchdog.stop()


async def main():
    parser = argparse.ArgumentParser(description="MECOS unified runtime entrypoint")
    parser.add_argument("--start-trading", action="store_true", help="Start trading loop after runtime demo")
    parser.add_argument("--trading-seconds", type=int, default=30, help="How long to run trading before stopping")
    parser.add_argument(
        "--execution-mode",
        choices=["paper", "live"],
        default=str(os.getenv("MECOS_TRADING_EXECUTION_MODE", "paper")).strip().lower(),
        help="Trading execution mode: paper uses simulated fills, live submits real broker orders",
    )
    args = parser.parse_args()

    runtime = UnifiedMECOSRuntime(trading_execution_mode=args.execution_mode)
    try:
        await runtime.startup()
        await runtime.run_runtime_demo()
        if args.start_trading:
            await runtime.start_trading(args.trading_seconds)
    except Exception as exc:
        await runtime.crash_recovery.record_crash(
            exc,
            runtime_state={
                "connection_state": runtime.connection_state,
                "trading_execution_mode": runtime.trading_execution_mode,
            },
        )
        raise
    finally:
        await runtime.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

