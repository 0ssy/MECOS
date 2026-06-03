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
from engineer import SandboxExecutor as RuntimeSandboxExecutor
from knowledge_graph import KnowledgeGraph as RuntimeKnowledgeGraph
from memory_system import MemorySystem
from model_router import ModelRouter
from mecos.domain_expansion import DomainExpansionController
from neural_brain_service import NeuralBrainService
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
        self._runtime_research_task: Optional[asyncio.Task] = None
        self._runtime_cognition_task: Optional[asyncio.Task] = None
        self._domain_expansion_task: Optional[asyncio.Task] = None
        self.neural_brain_service: Optional[NeuralBrainService] = None
        self.domain_expansion_controller: Optional[DomainExpansionController] = None
        self.domain_expansion_enabled = os.getenv("MECOS_ENABLE_DOMAIN_EXPANSION", "false").strip().lower() == "true"
        self.domain_expansion_tick_seconds = max(
            60,
            int(float(os.getenv("MECOS_DOMAIN_EXPANSION_TICK_SECONDS", "600"))),
        )

    async def _on_stale_component(self, component: str, stale_for_seconds: float):
        logger.warning(f"Recovery signal: component={component} stale_for={stale_for_seconds:.1f}s")

    async def _heartbeat_loop(self):
        while True:
            self.health_monitor.heartbeat("runtime_main")
            if self._trading_task and not self._trading_task.done():
                self.health_monitor.heartbeat("trading_loop")
            for component in (
                "memory",
                "perception",
                "web_perception",
                "reasoning",
                "agents",
                "runtime_stack",
            ):
                if self.connection_state.get(component, False):
                    self.health_monitor.heartbeat(component)
            await asyncio.sleep(5)

    async def _runtime_cognition_loop(self):
        while True:
            runtime_router: ModelRouter = self.components.get("runtime_router")
            runtime_orchestrator: AutonomousOrchestrator = self.components.get("runtime_orchestrator")
            runtime_evolution: EvolutionAgent = self.components.get("runtime_evolution")
            neural_brain: NeuralBrainService = self.components.get("neural_brain_service")
            if runtime_router and runtime_orchestrator and runtime_evolution:
                try:
                    trading_metrics = {}
                    if self.trading_system and hasattr(self.trading_system, "performance_monitor"):
                        trading_metrics = self.trading_system.performance_monitor.get_metrics()
                        if trading_metrics:
                            self.benchmark_harness.record_trading_metrics(trading_metrics)
                            await runtime_evolution.ingest_trading_performance(trading_metrics)
                            runtime_orchestrator.attach_components({"latest_trading_metrics": trading_metrics})
                    await self.execution_guard.run(
                        "runtime_router_tick",
                        runtime_router.route_request("maintain runtime health", "long_term_planning"),
                        timeout_seconds=60.0,
                    )
                    await runtime_orchestrator.run_goal("Maintain MECOS subsystem coordination")
                    await runtime_evolution.run_benchmark("runtime_governance", {"success_rate": 0.9})
                    if neural_brain and neural_brain.is_available:
                        insight = neural_brain.runtime_insight(
                            {
                                "runtime_health": 85.0,
                                "efficiency_delta": float(self.benchmark_harness.latest().get("score_delta", 0.0))
                                if self.benchmark_harness.latest()
                                else 0.0,
                                "research_quality_index": float(
                                    self.research_governor.evaluate({"useful_discoveries_per_hour": 0.0}).get(
                                        "research_quality_index", 0.0
                                    )
                                ),
                                "success_rate": 0.9,
                                "runtime_regime": "trending",
                            }
                        )
                        if insight:
                            self.components["latest_neural_runtime_insight"] = insight
                            logger.info(
                                f"Neural runtime insight: action={insight.get('action')} "
                                f"uncertainty={insight.get('uncertainty')}"
                            )
                except Exception as exc:
                    logger.warning(f"Runtime cognition tick failed: {exc}")
            await asyncio.sleep(120)

    async def _start_runtime_background_loops(self):
        runtime_loop: ContinuousResearchLoop = self.components.get("runtime_research_loop")
        if runtime_loop and (not self._runtime_research_task or self._runtime_research_task.done()):
            self._runtime_research_task = asyncio.create_task(
                runtime_loop.start(["autonomous runtime", "recursive engineering", "runtime stability"])
            )
        if not self._runtime_cognition_task or self._runtime_cognition_task.done():
            self._runtime_cognition_task = asyncio.create_task(self._runtime_cognition_loop())
        if (
            self.domain_expansion_enabled
            and self.domain_expansion_controller is not None
            and (not self._domain_expansion_task or self._domain_expansion_task.done())
        ):
            self._domain_expansion_task = asyncio.create_task(self._domain_expansion_loop())

    async def _stop_runtime_background_loops(self):
        runtime_loop: ContinuousResearchLoop = self.components.get("runtime_research_loop")
        if runtime_loop:
            runtime_loop.stop()
        for task in (self._runtime_research_task, self._runtime_cognition_task, self._domain_expansion_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._runtime_research_task = None
        self._runtime_cognition_task = None
        self._domain_expansion_task = None

    async def _domain_expansion_loop(self):
        while True:
            if self.domain_expansion_controller is None:
                await asyncio.sleep(self.domain_expansion_tick_seconds)
                continue
            try:
                await self.execution_guard.run(
                    "domain_expansion_tick",
                    asyncio.to_thread(self.domain_expansion_controller.learn_next),
                    timeout_seconds=max(180.0, float(self.domain_expansion_tick_seconds)),
                )
            except Exception as exc:
                logger.warning(f"Domain expansion tick failed: {exc}")
            await asyncio.sleep(self.domain_expansion_tick_seconds)

    async def startup(self):
        self.drift_guard.add_anchor("Stability before expansion", source="operator_policy")
        self.health_monitor.mark_started("runtime_main")
        await self.watchdog.start()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        self.memory = MemorySystem()
        self.connection_state["memory"] = True
        self.components["memory"] = self.memory
        self.health_monitor.mark_started("memory")
        self.neural_brain_service = NeuralBrainService(memory_system=self.memory)
        self.components["neural_brain_service"] = self.neural_brain_service
        try:
            self.domain_expansion_controller = DomainExpansionController()
            self.components["domain_expansion_controller"] = self.domain_expansion_controller
            self.connection_state["domain_expansion"] = True
            logger.info(
                "Domain expansion controller initialized | enabled={} tick={}s",
                self.domain_expansion_enabled,
                self.domain_expansion_tick_seconds,
            )
        except Exception as exc:
            self.domain_expansion_controller = None
            self.connection_state["domain_expansion"] = False
            logger.warning(f"Domain expansion controller init failed: {exc}")

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
        runtime_sandbox = RuntimeSandboxExecutor()
        self.connection_state["reasoning"] = True
        self.components["tools"] = tools
        self.components["action_engine"] = action_engine
        self.components["reasoner"] = reasoner
        self.health_monitor.mark_started("reasoning")

        core_coding = CoreCodingAgent(self.memory, tools, sandbox_executor=runtime_sandbox)
        core_research = CoreResearchAgent(self.memory, self.web)
        coordinator = AgentCoordinator(self.memory)
        self.connection_state["core_coding"] = True
        self.connection_state["core_research"] = True
        self.connection_state["agent_coordinator"] = True
        self.connection_state["agents"] = True
        self.components["core_coding_agent"] = core_coding
        self.components["core_research_agent"] = core_research
        self.components["agent_coordinator"] = coordinator
        self.health_monitor.mark_started("agents")

        runtime_memory = RuntimeVectorMemory()
        runtime_graph = RuntimeKnowledgeGraph()
        runtime_research = core_research
        runtime_coding = core_coding
        runtime_debugger = SelfDebugger(runtime_sandbox)
        runtime_orchestrator = AutonomousOrchestrator()
        runtime_orchestrator.set_layer_priority("research", 120)
        runtime_orchestrator.set_compute_budget(10)
        runtime_evolution = EvolutionAgent(memory_layer=runtime_memory, benchmark_harness=self.benchmark_harness)
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
        self.connection_state["runtime_stack"] = True

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
        self.components["research_agent"] = core_research
        self.components["coding_agent"] = core_coding
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
            if self.neural_brain_service and self.neural_brain_service.is_available:
                self.trading_system.agent.neural_brain = self.neural_brain_service.brain
                self.trading_system.agent.neural_brain_enabled = True
            self.connection_state["trading_system"] = True
            self.components["trading_system"] = self.trading_system
        except Exception as exc:
            logger.warning(f"TradingSystem init failed: {exc}")
            self.connection_state["trading_system"] = False

        runtime_orchestrator.attach_components(
            {
                "research_agent": core_research,
                "coding_agent": core_coding,
                "memory": self.memory,
                "evolution_agent": runtime_evolution,
                "trading_system": self.trading_system,
                "runtime_router": runtime_router,
                "neural_brain_service": self.neural_brain_service,
                "domain_expansion_controller": self.domain_expansion_controller,
            }
        )

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
        runtime_research: CoreResearchAgent = self.components["runtime_research_agent"]
        runtime_coding: CoreCodingAgent = self.components["runtime_coding_agent"]
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
        trading_metrics = {}
        optimization_plan = {}
        if self.trading_system and hasattr(self.trading_system, "performance_monitor"):
            trading_metrics = self.trading_system.performance_monitor.get_metrics()
            if trading_metrics:
                self.benchmark_harness.record_trading_metrics(trading_metrics)
                optimization_plan = await runtime_evolution.ingest_trading_performance(trading_metrics)

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
            "trading_sharpe_ratio": float(trading_metrics.get("sharpe_ratio", 0.0)),
            "trading_max_drawdown": float(trading_metrics.get("max_drawdown", 0.0)),
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
        self.components["trading_optimization_plan"] = optimization_plan
        logger.info(f"Runtime demo complete. memory_hits={len(found)}")

    async def start_trading(self, run_seconds: int):
        if not self.trading_system:
            logger.warning("TradingSystem unavailable; skipping trading start")
            return
        await self._start_runtime_background_loops()
        self._trading_task = asyncio.create_task(self.trading_system.start(use_starter_universe=True))
        await asyncio.sleep(max(1, int(run_seconds)))
        self.trading_system.stop()
        if self._trading_task and not self._trading_task.done():
            self._trading_task.cancel()
            try:
                await self._trading_task
            except asyncio.CancelledError:
                pass
        await self._stop_runtime_background_loops()
        logger.info("Trading segment stopped")

    async def run_full_runtime(self, run_seconds: int, include_trading: bool = False):
        await self._start_runtime_background_loops()
        if include_trading:
            if not self.trading_system:
                logger.warning("TradingSystem unavailable; running full runtime without trading.")
            else:
                self._trading_task = asyncio.create_task(self.trading_system.start(use_starter_universe=True))

        try:
            if int(run_seconds) <= 0:
                while True:
                    await asyncio.sleep(60)
            else:
                await asyncio.sleep(max(1, int(run_seconds)))
        finally:
            if self.trading_system:
                self.trading_system.stop()
            if self._trading_task and not self._trading_task.done():
                self._trading_task.cancel()
                try:
                    await self._trading_task
                except asyncio.CancelledError:
                    pass
            await self._stop_runtime_background_loops()
        logger.info("Full runtime segment stopped")

    async def shutdown(self):
        await self._stop_runtime_background_loops()
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
    parser.add_argument("--start-trading", action="store_true", help="(legacy) Start trading loop after runtime demo")
    parser.add_argument("--trading-seconds", type=int, default=30, help="How long to run trading before stopping")
    parser.add_argument(
        "--runtime-seconds",
        type=int,
        default=0,
        help="How long to keep full MECOS runtime alive. 0 means run until interrupted.",
    )
    parser.add_argument(
        "--no-trading",
        action="store_true",
        help="Run full MECOS runtime without trading loop.",
    )
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
        include_trading = (not args.no_trading) or args.start_trading
        if args.runtime_seconds != 0:
            await runtime.run_full_runtime(args.runtime_seconds, include_trading=include_trading)
        else:
            # Default behavior for main.py: run full MECOS architecture continuously.
            await runtime.run_full_runtime(0, include_trading=include_trading)
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

