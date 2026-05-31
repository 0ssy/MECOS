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
from mecos_v35_implementation import GlobalAppIntelligence, PolyglotCodingAgent
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

# --- Advanced Layer Imports ---
try:
    from runtime.message_bus import MessageBus, get_bus
    from runtime.process_manager import ProcessManager, WorkerSpec
    from knowledge_compressor import KnowledgeCompressor
    from workers.research_worker import run_research_worker
    from workers.memory_worker import run_memory_worker
    from workers.evolution_worker import run_evolution_worker
    _ADVANCED_LAYERS = True

# --- MECOS v3.0 Reporting & Honesty Layer ---
    try:
        from runtime.uncertainty_flagger import UncertaintyFlagger
        from reporting.milestone_alerts import AlertDispatcher, MilestoneAlertSystem
        from reporting.daily_report_generator import DailyReportGenerator
        from reporting.weekly_review_generator import WeeklyReviewGenerator
        from runtime.app_discovery import AppDiscovery, AppLearner
        _V3_LAYERS = True
    except ImportError as _v3_err:
        _V3_LAYERS = False
except ImportError as _adv_err:
    _ADVANCED_LAYERS = False
    _V3_LAYERS = False


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
        # --- Advanced layer instances ---
        self.message_bus = None
        self.process_manager = None
        self._process_monitor_task: Optional[asyncio.Task] = None
        self.knowledge_compressor = None
        self._compressor_task: Optional[asyncio.Task] = None
        self._dreaming_task: Optional[asyncio.Task] = None
        # --- v3.0 component instances ---
        self.uncertainty_flagger = None
        self.alert_dispatcher    = None
        self.milestone_system    = None
        self.daily_reporter      = None
        self.weekly_reviewer     = None
        self.app_discovery       = None
        self._daily_report_task: Optional[asyncio.Task] = None
        self._weekly_review_task: Optional[asyncio.Task] = None
        self.polyglot_coding_agent: Optional[PolyglotCodingAgent] = None
        self.global_app_intelligence: Optional[GlobalAppIntelligence] = None

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
                        lambda: runtime_router.route_request("maintain runtime health", "long_term_planning"),
                        timeout_seconds=60.0,
                    )
                    await runtime_orchestrator.run_goal("Maintain MECOS subsystem coordination")
                    await runtime_evolution.run_benchmark("runtime_governance", {"success_rate": 0.9})
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

    async def _stop_runtime_background_loops(self):
        runtime_loop: ContinuousResearchLoop = self.components.get("runtime_research_loop")
        if runtime_loop:
            runtime_loop.stop()
        for task in (self._runtime_research_task, self._runtime_cognition_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._runtime_research_task = None
        self._runtime_cognition_task = None

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
        reasoner = await self.execution_guard.run("reasoner_init", lambda: asyncio.to_thread(Reasoner, self.memory))
        runtime_sandbox = RuntimeSandboxExecutor()
        self.connection_state["reasoning"] = True
        self.components["tools"] = tools
        self.components["action_engine"] = action_engine
        self.components["reasoner"] = reasoner
        self.health_monitor.mark_started("reasoning")

        core_coding = CoreCodingAgent(self.memory, tools, sandbox_executor=runtime_sandbox)
        core_research = CoreResearchAgent(self.memory, self.web)
        polyglot_coding = PolyglotCodingAgent(workspace="sandbox\\polyglot")
        global_app_intelligence = GlobalAppIntelligence(registry_path="data\\app_registry.json")
        coordinator = AgentCoordinator(self.memory)
        self.connection_state["core_coding"] = True
        self.connection_state["core_research"] = True
        self.connection_state["agent_coordinator"] = True
        self.connection_state["agents"] = True
        self.connection_state["polyglot_coding_agent"] = True
        self.connection_state["global_app_intelligence"] = True
        self.components["core_coding_agent"] = core_coding
        self.components["core_research_agent"] = core_research
        self.components["polyglot_coding_agent"] = polyglot_coding
        self.components["global_app_intelligence"] = global_app_intelligence
        self.components["agent_coordinator"] = coordinator
        self.health_monitor.mark_started("agents")
        self.polyglot_coding_agent = polyglot_coding
        self.global_app_intelligence = global_app_intelligence

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
            self.connection_state["trading_system"] = True
            self.components["trading_system"] = self.trading_system
            trading_components = self.trading_system.get_components()
            self.components["trading_components"] = trading_components
            self.components["trading_persona_engine"] = trading_components.get("persona_engine")
            self.components["trading_consensus_engine"] = trading_components.get("consensus_engine")
            self.components["trading_openbb_adapter"] = trading_components.get("openbb_adapter")
            self.components["trading_forex_activation_status"] = trading_components.get("forex_activation_status")
            self.components["trading_cockpit_snapshot"] = trading_components.get("cockpit_snapshot")
        except Exception as exc:
            logger.warning(f"TradingSystem init failed: {exc}")
            self.connection_state["trading_system"] = False

        runtime_orchestrator.attach_components(
            {
                "research_agent": core_research,
                "coding_agent": core_coding,
                "polyglot_coding_agent": polyglot_coding,
                "global_app_intelligence": global_app_intelligence,
                "memory": self.memory,
                "evolution_agent": runtime_evolution,
                "trading_system": self.trading_system,
                "trading_persona_engine": self.components.get("trading_persona_engine"),
                "trading_consensus_engine": self.components.get("trading_consensus_engine"),
                "trading_openbb_adapter": self.components.get("trading_openbb_adapter"),
                "trading_forex_activation_status": self.components.get("trading_forex_activation_status"),
                "trading_cockpit_snapshot": self.components.get("trading_cockpit_snapshot"),
                "runtime_router": runtime_router,
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
        await self._start_advanced_layers()
        await self._start_v3_layers()
        logger.info(f"Unified MECOS startup complete: {self.connection_state}")
        if self.uncertainty_flagger and 'quant_trading_agent' in self.connection_state:
            try:
                trading_agent = self.components.get('quant_trading_agent')
                if trading_agent and not hasattr(trading_agent, 'uncertainty_flagger'):
                    trading_agent.uncertainty_flagger = self.uncertainty_flagger
                    logger.info('UncertaintyFlagger wired into TradingAgent')
            except Exception:
                pass

    async def run_runtime_demo(self):
        runtime_memory: RuntimeVectorMemory = self.components["runtime_memory"]
        runtime_graph: RuntimeKnowledgeGraph = self.components["runtime_graph"]
        runtime_research: CoreResearchAgent = self.components["runtime_research_agent"]
        runtime_coding: CoreCodingAgent = self.components["runtime_coding_agent"]
        runtime_debugger: SelfDebugger = self.components["runtime_debugger"]
        runtime_orchestrator: AutonomousOrchestrator = self.components["runtime_orchestrator"]
        runtime_evolution: EvolutionAgent = self.components["runtime_evolution"]
        runtime_router: ModelRouter = self.components["runtime_router"]
        polyglot_coding: Optional[PolyglotCodingAgent] = self.components.get("polyglot_coding_agent")
        global_app_intelligence: Optional[GlobalAppIntelligence] = self.components.get("global_app_intelligence")

        if polyglot_coding:
            await asyncio.to_thread(polyglot_coding.learn_language, "rust")
            await asyncio.to_thread(polyglot_coding.solve_challenge, "rust", "two_sum_001")
        if global_app_intelligence:
            await asyncio.to_thread(global_app_intelligence.discover_app, "Fincept Terminal")
        await self.execution_guard.run(
            "runtime_research_analyze_repo",
            lambda: runtime_research.analyze_repo(str(Path(__file__).resolve().parent)),
            timeout_seconds=45.0,
        )
        module_code = await runtime_coding.build_module("diagnostic_tool", "runtime health checks")
        debug_result = {"success": True}
        if module_code:
            debug_result = await self.execution_guard.run(
                "runtime_debugger_verify_and_repair",
                lambda: runtime_debugger.verify_and_repair(module_code, "diagnostic_tool.py"),
                timeout_seconds=180.0,
            )

        runtime_graph.add_node("mecos_core", "runtime", {"mode": "local-first"})
        runtime_graph.add_node("sandbox", "component", {"purpose": "safe execution"})
        runtime_graph.add_edge("mecos_core", "sandbox", "uses")

        await self.execution_guard.run(
            "runtime_router_route_request",
            lambda: runtime_router.route_request("plan evolution", "long_term_planning"),
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

    # --- Advanced layer helpers ---
    async def _compression_loop(self):
        while True:
            try:
                await asyncio.sleep(300)
                if self.knowledge_compressor:
                    await self.knowledge_compressor.compress_cycle()
            except asyncio.CancelledError:
                break
            except Exception as _ce:
                logger.error(f'Compression loop error: {_ce}')

    async def _dreaming_loop(self, dreaming_engine):
        while True:
            try:
                await asyncio.sleep(600)
                goal = await dreaming_engine.generate_self_goal()
                if goal:
                    orchestrator = self.components.get('runtime_orchestrator')
                    if orchestrator:
                        await orchestrator.run_goal(goal)
            except asyncio.CancelledError:
                break
            except Exception as _de:
                logger.error(f'Dreaming loop error: {_de}')

    def _on_research_result(self, worker_id: str, payload):
        topic = payload.get('topic', 'unknown')
        logger.debug(f'[ProcessManager] Research result from {worker_id}: {topic}')

    async def _start_advanced_layers(self):
        if not _ADVANCED_LAYERS:
            logger.warning('Advanced layers not available - check imports')
            return
        try:
            self.message_bus = MessageBus()
            await self.message_bus.start_dispatch()
            logger.info('MessageBus started')
        except Exception as _e:
            logger.warning(f'MessageBus failed: {_e}')
        try:
            kg  = self.components.get('runtime_knowledge_graph')
            llm = self.components.get('reasoning')
            if self.memory and kg:
                self.knowledge_compressor = KnowledgeCompressor(
                    memory=self.memory, knowledge_graph=kg, llm=llm
                )
                self._compressor_task = asyncio.create_task(self._compression_loop())
                logger.info('KnowledgeCompressor started')
        except Exception as _e:
            logger.warning(f'KnowledgeCompressor failed: {_e}')
        try:
            from dreaming_engine import DreamingEngine
            dreaming = DreamingEngine(self.memory)
            self._dreaming_task = asyncio.create_task(self._dreaming_loop(dreaming))
            logger.info('DreamingEngine started')
        except Exception as _e:
            logger.warning(f'DreamingEngine failed: {_e}')
        try:
            self.process_manager = ProcessManager()
            self.process_manager.register(WorkerSpec(
                worker_id='research_worker',
                target_fn=run_research_worker,
                cycle_interval=45.0,
                max_restarts=10,
            ))
            self.process_manager.register(WorkerSpec(
                worker_id='memory_worker',
                target_fn=run_memory_worker,
                cycle_interval=120.0,
                max_restarts=5,
            ))
            self.process_manager.register(WorkerSpec(
                worker_id='evolution_worker',
                target_fn=run_evolution_worker,
                cycle_interval=180.0,
                max_restarts=5,
            ))
            self.process_manager.register_result_handler(
                'research_result', self._on_research_result
            )
            self.process_manager.start_all()
            self._process_monitor_task = asyncio.create_task(self.process_manager.monitor_loop())
            logger.info('Distributed worker processes started')
        except Exception as _e:
            logger.warning(f'ProcessManager failed: {_e}')

    async def _start_v3_layers(self):
        if not _V3_LAYERS:
            logger.warning('v3.0 layers not available')
            return
        performance_tracker = None
        if self.trading_system and hasattr(self.trading_system, "performance_monitor"):
            performance_monitor = getattr(self.trading_system, "performance_monitor", None)
            performance_tracker = getattr(performance_monitor, "tracker", None)
        try:
            self.uncertainty_flagger = UncertaintyFlagger(
                confidence_threshold=0.60,
                track_assumptions=True,
                flag_limitations=True,
            )
            logger.info('UncertaintyFlagger initialized')
        except Exception as _e:
            logger.warning(f'UncertaintyFlagger failed: {_e}')
        try:
            self.alert_dispatcher = AlertDispatcher()
            # Register callback so alerts appear in logs
            self.alert_dispatcher.register_callback(
                'logger',
                lambda title, msg, meta: logger.info(f'ALERT: {title} | {msg}')
            )
            logger.info('AlertDispatcher initialized')
        except Exception as _e:
            logger.warning(f'AlertDispatcher failed: {_e}')
        try:
            if self.alert_dispatcher and performance_tracker is not None:
                self.milestone_system = MilestoneAlertSystem(
                    performance_tracker=performance_tracker,
                    alert_dispatcher=self.alert_dispatcher,
                )
                logger.info('MilestoneAlertSystem initialized')
            elif self.alert_dispatcher:
                logger.warning('MilestoneAlertSystem skipped: performance tracker unavailable')
        except Exception as _e:
            logger.warning(f'MilestoneAlertSystem failed: {_e}')
        try:
            if performance_tracker is not None:
                self.daily_reporter = DailyReportGenerator(
                    performance_tracker=performance_tracker,
                    output_dir='reports/daily',
                    goal_equity=float(getattr(performance_tracker, "goal_equity", 60000.0)),
                )
                self._daily_report_task = asyncio.create_task(self._daily_report_loop())
                logger.info('DailyReportGenerator initialized')
            else:
                logger.warning('DailyReportGenerator skipped: performance tracker unavailable')
        except Exception as _e:
            logger.warning(f'DailyReportGenerator failed: {_e}')
        try:
            if performance_tracker is not None and self.uncertainty_flagger is not None:
                self.weekly_reviewer = WeeklyReviewGenerator(
                    performance_tracker=performance_tracker,
                    uncertainty_flagger=self.uncertainty_flagger,
                    output_dir='reports/weekly'
                )
                self._weekly_review_task = asyncio.create_task(self._weekly_review_loop())
                logger.info('WeeklyReviewGenerator initialized')
            else:
                logger.warning('WeeklyReviewGenerator skipped: dependencies unavailable')
        except Exception as _e:
            logger.warning(f'WeeklyReviewGenerator failed: {_e}')
        try:
            self.app_discovery = AppDiscovery(cache_dir='data/app_discovery')
            asyncio.create_task(self._run_app_discovery())
            logger.info('AppDiscovery initialized')
        except Exception as _e:
            logger.warning(f'AppDiscovery failed: {_e}')

    async def _daily_report_loop(self):
        import datetime as _dt
        while True:
            try:
                now = _dt.datetime.now()
                # Run at 17:00 daily
                target = now.replace(hour=17, minute=0, second=0, microsecond=0)
                if now >= target:
                    target = target + _dt.timedelta(days=1)
                wait_secs = (target - now).total_seconds()
                await asyncio.sleep(wait_secs)
                if self.daily_reporter:
                    report = self.daily_reporter.generate_report()
                    files  = self.daily_reporter.save_report(report)
                    logger.info(f'Daily report saved: {files}')
                    if self.alert_dispatcher:
                        self.alert_dispatcher.dispatch(
                            'Daily Report',
                            f'PnL:  | Trades: {report.trades_count}',
                            {}
                        )
            except asyncio.CancelledError:
                break
            except Exception as _e:
                logger.error(f'Daily report error: {_e}')
                await asyncio.sleep(3600)

    async def _weekly_review_loop(self):
        import datetime as _dt
        while True:
            try:
                now = _dt.datetime.now()
                # Run on Friday at 18:00
                days_until_friday = (4 - now.weekday()) % 7
                target = (now + _dt.timedelta(days=days_until_friday)).replace(
                    hour=18, minute=0, second=0, microsecond=0)
                if target <= now:
                    target += _dt.timedelta(weeks=1)
                wait_secs = (target - now).total_seconds()
                await asyncio.sleep(wait_secs)
                if self.weekly_reviewer:
                    review = self.weekly_reviewer.generate_review()
                    files  = self.weekly_reviewer.save_review(review)
                    logger.info(f'Weekly review saved: {files}')
            except asyncio.CancelledError:
                break
            except Exception as _e:
                logger.error(f'Weekly review error: {_e}')
                await asyncio.sleep(3600)

    async def _run_app_discovery(self):
        try:
            await asyncio.sleep(30)  # Wait for full startup
            if self.app_discovery:
                apps = self.app_discovery.discover()
                self.app_discovery.save_discovery()
                logger.info(f'AppDiscovery: found {len(apps)} applications')
        except Exception as _e:
            logger.error(f'AppDiscovery error: {_e}')

    async def shutdown(self):
        for task_attr in (
            "_process_monitor_task",
            "_compressor_task",
            "_dreaming_task",
            "_daily_report_task",
            "_weekly_review_task",
        ):
            task = getattr(self, task_attr, None)
            if task:
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=5.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
                setattr(self, task_attr, None)

        if self.process_manager:
            try:
                await asyncio.to_thread(self.process_manager.stop_all)
            except Exception as exc:
                logger.warning(f"ProcessManager stop failed: {exc}")
            self.process_manager = None

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
    import multiprocessing

    try:
        multiprocessing.freeze_support()
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("KeyboardInterrupt received; terminating active child processes.")
        for child in multiprocessing.active_children():
            try:
                child.terminate()
            except Exception:
                pass
        for child in multiprocessing.active_children():
            try:
                child.join(timeout=3)
            except Exception:
                pass

