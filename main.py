from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional
from loguru import logger

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from uvicorn import Server, Config

from config import settings
from validate_config import validate_on_startup
from memory_system import MemorySystem
from reasoner import Reasoner
from meta_learner import MetaLearner
from independence_manager import IndependenceManager
from dreaming_engine import DreamingEngine
from neural_brain_service import NeuralBrainService
from mecos.domain_expansion import DomainExpansionController
from agent_reach_bridge import get_bridge
from tool_orchestrator import ToolOrchestrator
from action_engine import ActionExecutionEngine
from app_perception import AppPerception
from app_controller import AppController
from health_monitor import HealthMonitor
from security_agent import SecurityAgent
from guardian_agent import GuardianAgent
from trading_agent import TradingAgent
from outreach.outreach_agent import OutreachAgent
from outreach.dashboard import DashboardService
from ceo_agent import CeoAgent

# Assistant overlay imports
from meeting_assistant import MeetingAssistant
from assistant_engine import AssistantEngine
from kilo_bridge import KiloBridge
from ui_overlay.routes import get_router, set_meeting_active, add_transcript_segment, set_suggestion

TRADING_ENABLED = os.getenv("MECOS_ENABLE_TRADING", "true").strip().lower() == "true"
ASSISTANT_ENABLED = os.getenv("MECOS_ENABLE_ASSISTANT", "false").strip().lower() == "true"


async def startup_checks(memory: MemorySystem) -> None:
    logger.info("Running startup checks...")
    if TRADING_ENABLED and not settings.ALPACA_API_KEY:
        logger.warning("ALPACA_API_KEY not set — stock trading disabled")
    if TRADING_ENABLED and not settings.BINANCE_API_KEY:
        logger.warning("BINANCE_API_KEY not set — crypto trading disabled")
    logger.info("Startup checks complete.")


def build_intelligence_stack() -> dict:
    from mecos.knowledge_core import KnowledgeGraph
    from mecos.domain_graph import DomainGraph
    from mecos.curiosity_engine import CuriosityEngine
    from mecos.cross_domain_inference import CrossDomainInferenceEngine

    kg = KnowledgeGraph()
    dg = DomainGraph()
    curiosity = CuriosityEngine(kg=kg, domain_graph=dg)
    xdi = CrossDomainInferenceEngine(kg=kg, domain_graph=dg)
    logger.info(
        "Intelligence stack ready: kg={} nodes, dg={} domains, {} curiosities",
        kg.graph.number_of_nodes(),
        dg.graph.number_of_nodes(),
        len(curiosity.queue),
    )
    return {
        "knowledge_graph": kg,
        "domain_graph": dg,
        "curiosity_engine": curiosity,
        "cross_domain_inference": xdi,
    }


async def _run_meeting_assistant(
    meeting_assistant: MeetingAssistant,
    assistant_engine: AssistantEngine,
    app_perception: AppPerception,
):
    debounce_counter = 0
    last_meeting_active = False
    capture_task = None

    while True:
        try:
            meeting_state = await app_perception.observe_meeting_apps()
            current_meeting = meeting_state.get("meeting_active", False)

            if current_meeting != last_meeting_active:
                debounce_counter += 1
                if debounce_counter >= 3:
                    if current_meeting and not meeting_assistant.running:
                        logger.info("Meeting detected - starting audio capture")
                        capture_task = asyncio.create_task(
                            _process_transcript_stream(meeting_assistant, assistant_engine)
                        )
                    elif not current_meeting and meeting_assistant.running:
                        await meeting_assistant.stop_capture()
                        if capture_task:
                            capture_task.cancel()
                            capture_task = None
                        logger.info("Meeting ended - stopping audio capture")
                    set_meeting_active(current_meeting)
                    last_meeting_active = current_meeting
                    debounce_counter = 0
            else:
                debounce_counter = 0

        except Exception as e:
            logger.warning(f"Meeting assistant loop error: {e}")

        await asyncio.sleep(3)


async def _process_transcript_stream(meeting_assistant: MeetingAssistant, assistant_engine: AssistantEngine):
    try:
        async for segment in meeting_assistant.start_capture():
            add_transcript_segment(segment)
            if assistant_engine:
                result = await assistant_engine.process_segment(segment)
                if result:
                    set_suggestion(result.get("answer", ""))
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Transcript stream error: {e}")


async def run_cognition_loop(
    memory: MemorySystem,
    reasoner: Reasoner,
    meta_learner: MetaLearner,
    independence: IndependenceManager,
    dreaming: DreamingEngine,
    neural_brain_service: NeuralBrainService,
    action_engine: ActionExecutionEngine,
    app_perception: AppPerception,
    domain_expansion_controller=None,
    domain_expansion_every: int = 20,
    outreach_agent: Optional[OutreachAgent] = None,
    ceo_agent: Optional[CeoAgent] = None,
) -> None:
    logger.info("Entering cognition loop (timer + event hybrid)...")
    cycle = 0
    pending_goals: list = []

    while True:
        cycle += 1

        try:
            # ── Outreach agent cycle (optional, run every cycle if enabled) ─
            if outreach_agent and outreach_agent.enabled:
                outreach_result = await outreach_agent.run_cycle()
                if cycle % 5 == 0:
                    logger.info(f"Outreach status: {outreach_result.get('outreach_status')}")

            # ── CEO supervision (every 3 cycles) ─────────────────────────
            if ceo_agent and cycle % 3 == 0:
                ceo_result = await ceo_agent.run_cycle()
                if ceo_result.get("health", {}).get("status") != "healthy":
                    logger.warning("CEO health alert: {}", ceo_result["health"]["issues"])

            # ── Goal intake (from any source) ───────────────────────────
            for goal_desc in pending_goals[:]:
                logger.info("Goal: {}", goal_desc[:80])
                plan = await reasoner.generate_plan(goal_desc)
                if plan:
                    results = await action_engine.execute_plan(plan)
                    await reasoner.reflect(goal_desc, plan, results)
                pending_goals.remove(goal_desc)

            # ── Intelligence persistence (every 3 cycles) ────────────────
            if cycle % 3 == 0:
                kg = reasoner.intelligence.get("knowledge_graph")
                dg = reasoner.intelligence.get("domain_graph")
                if kg and hasattr(kg, "save"):
                    kg.save()
                if dg and hasattr(dg, "save"):
                    dg.save()

            # ── Curiosity-driven research (every 7 cycles) ───────────────
            if cycle % 7 == 0:
                engine = reasoner.intelligence.get("curiosity_engine")
                if engine and engine.queue_size() > 0:
                    item = engine.next_curiosity()
                    if item:
                        concept = item.get("concept", "")
                        logger.info("Curiosity research: {}", concept)
                        plan = await reasoner.generate_plan(f"Research and learn about: {concept}")
                        if plan:
                            results = await action_engine.execute_plan(plan)
                            kg = reasoner.intelligence.get("knowledge_graph")
                            if kg:
                                kg.add_triplet(concept, "EXPLORED_VIA", "curiosity", source="curiosity", confidence=0.7)
                            await reasoner.reflect(f"Research: {concept}", plan, results)

            # ── Periodic desktop observation (every 4 cycles) ────────────
            if cycle % 4 == 0 and app_perception:
                try:
                    snapshot = await app_perception.observe_current_desktop()
                    unknown = snapshot.get("unknown_apps", 0)
                    if unknown:
                        logger.debug("Desktop snapshot: {} open windows, {} unknown apps", snapshot.get("open_windows", 0), unknown)
                except Exception as exc:
                    logger.debug("App observation failed: {}", exc)

            # ── Meta-learning (every 5 cycles) ───────────────────────────
            if cycle % 5 == 0:
                meta_result = await meta_learner.run_meta_cycle()
                logger.info(f"Meta score: {meta_result.get('benchmark_score', 'N/A')}")

            # ── Dreaming (every 10 cycles) ───────────────────────────────
            if cycle % 10 == 0:
                await dreaming.dream()

            # ── Governance (every 20 cycles) ─────────────────────────────
            if cycle % 20 == 0:
                readiness = await independence.check_readiness()
                logger.info(f"Governance readiness: {readiness}")

            # ── Domain expansion ─────────────────────────────────────────
            if domain_expansion_controller and cycle % domain_expansion_every == 0:
                await asyncio.to_thread(domain_expansion_controller.learn_next)

        except Exception as e:
            logger.error(f"Cycle #{cycle} error: {e}")

        await asyncio.sleep(settings.IDLE_SLEEP_TIME)


async def run_trading_loop(
    trading_agent,
    neural_brain_service: NeuralBrainService,
    domain_expansion_controller=None,
    domain_expansion_every: int = 20,
    outreach_agent: Optional[OutreachAgent] = None,
    ceo_agent: Optional[CeoAgent] = None,
) -> None:
    logger.info("Trading loop active.")
    cycle = 0
    while True:
        cycle += 1
        try:
            if outreach_agent and outreach_agent.enabled:
                outreach_result = await outreach_agent.run_cycle()
                if cycle % 5 == 0:
                    logger.info(f"Outreach status: {outreach_result.get('outreach_status')}")

            # ── CEO supervision (every 3 cycles) ─────────────────────────
            if ceo_agent and cycle % 3 == 0:
                ceo_result = await ceo_agent.run_cycle()
                if ceo_result.get("health", {}).get("status") != "healthy":
                    logger.warning("CEO health alert: {}", ceo_result["health"]["issues"])

            trade_result = await trading_agent.run_cycle()
            logger.info(f"Trading: {trade_result['signals']} signals, {trade_result['actionable']} actionable")

            if neural_brain_service.is_available:
                insight = neural_brain_service.runtime_insight({
                    "runtime_health": 85.0, "success_rate": 0.9, "runtime_regime": "trending",
                })
                if insight:
                    logger.info(f"Global neural insight: action={insight.get('action')} uncertainty={insight.get('uncertainty')}")

            if domain_expansion_controller and cycle % domain_expansion_every == 0:
                await asyncio.to_thread(domain_expansion_controller.learn_next)
        except Exception as e:
            logger.error(f"Trading Cycle #{cycle} error: {e}")
        await asyncio.sleep(settings.IDLE_SLEEP_TIME)


async def main():
    logger.info(f"Starting MECOS {settings.VERSION} (trading={'enabled' if TRADING_ENABLED else 'disabled'})")

    # Run config validation
    validate_on_startup()

    # ── 1. Core memory ──────────────────────────────────────────────────
    memory = MemorySystem()
    await startup_checks(memory)

    # ── 2. Perception ───────────────────────────────────────────────────
    bridge = get_bridge(memory)
    channel_map = await bridge.initialize()
    active_channel_count = sum(1 for v in channel_map.values() if v.get("status") in ("ok", "warn"))
    logger.info("AgentReachBridge: {} channels active out of {}", active_channel_count, len(channel_map))

    app_controller = AppController()
    app_perception = AppPerception(memory_system=memory, controller=app_controller)
    await app_perception.scan_and_learn_system(learn_web=False)
    logger.info("AppPerception: {} apps, {} file types", len(app_perception.store.apps), len(app_perception.store.file_types))

    # ── 3. Intelligence layer ───────────────────────────────────────────
    intelligence = build_intelligence_stack()

    # ── 4. Tool orchestration + ActionEngine ────────────────────────────
    tool_orchestrator = ToolOrchestrator(memory_system=memory)
    action_engine = ActionExecutionEngine(tool_orchestrator, memory)

    # ── Load Kilo skills ───────────────────────────────────────────────
    skills_dir = settings.KILO_SKILLS_DIR
    if skills_dir.exists():
        for skill_file in sorted(skills_dir.glob("skill-*.md")):
            skill_names = tool_orchestrator.registry.load_skill(str(skill_file))
            for name in skill_names:
                logger.info(f"Loaded skill: {name} from {skill_file.name}")

    # ── MCP tool registration ─────────────────────────────────────
    if os.getenv("MECOS_ENABLE_MCP", "false").strip().lower() == "true":
        asyncio.create_task(tool_orchestrator.mcp_client_register_all())

    # Register skill-based MCP servers (notion, slack, granola, zapier)
    mcp_skill_count = tool_orchestrator.register_mcp_from_config()
    if mcp_skill_count:
        logger.info(f"Registered {mcp_skill_count} MCP skill tools")

    logger.info("ToolOrchestrator + ActionEngine ready: {} tools", len(tool_orchestrator.registry.list_tools()))

    # ── 5. Reasoner (with full intelligence) ────────────────────────────
    reasoner = Reasoner(memory, tool_orchestrator=tool_orchestrator, intelligence_stack=intelligence)
    neural_brain_service = NeuralBrainService(memory_system=memory)

    # ── 7. Meta-learner & independence ──────────────────────────────────
    meta_learner = MetaLearner(memory)
    independence = IndependenceManager(memory)

    trading_agent = None
    compliance_agent = None
    if TRADING_ENABLED:
        try:
            trading_agent = TradingAgent(memory, tool_orchestrator)
            if neural_brain_service.is_available and hasattr(trading_agent, "neural_brain"):
                trading_agent.neural_brain = neural_brain_service.brain
                trading_agent.neural_brain_enabled = True
            independence.set_agents(trading_agent, meta_learner)
            logger.info("IndependenceManager: live TradingAgent + MetaLearner.")
        except Exception as exc:
            logger.warning(f"Trading disabled: {exc}")
    else:
        independence.set_agents(None, meta_learner)
        logger.info("IndependenceManager: no TradingAgent (trading disabled).")

    # Register ComplianceAgent
    try:
        from compliance_agent import ComplianceAgent
        compliance_agent = ComplianceAgent(memory, tool_orchestrator)
        logger.info("ComplianceAgent ready for legal workflow.")
    except Exception as exc:
        logger.warning(f"ComplianceAgent unavailable: {exc}")

    # ── 8. Domain expansion ─────────────────────────────────────────────
    domain_expansion_controller = None
    if os.getenv("MECOS_ENABLE_DOMAIN_EXPANSION", "false").strip().lower() == "true":
        try:
            domain_expansion_controller = DomainExpansionController()
        except Exception as exc:
            logger.warning(f"Domain expansion unavailable: {exc}")

    # ── 9. Dreaming ─────────────────────────────────────────────────────
    dreaming = DreamingEngine(memory)

    # ── 10. Safety agents ─────────────────────────────────────────────
    health_monitor = HealthMonitor(memory)
    security_agent = SecurityAgent(memory, tool_orchestrator.registry)
    guardian = GuardianAgent(memory, health_monitor)

    # Start health monitoring
    asyncio.create_task(health_monitor.periodic_check(interval=120))

    # ── 11. Outreach agent (optional, enable with MECOS_ENABLE_OUTREACH=true) ──
    outreach_agent = OutreachAgent(memory)
    await outreach_agent.startup()
    
    # ── 11b. CEO agent (permanent coordinator) ──
    ceo_agent = CeoAgent(memory, tool_orchestrator=tool_orchestrator, revenue_ledger=outreach_agent.revenue_ledger)
    ceo_agent.attach_outreach(outreach_agent)
    if outreach_agent.enabled:
        await ceo_agent.resume_outreach()
    
    # ── 11c. Outreach scheduler (decoupled daily batch) ──
    scheduler = None
    if outreach_agent.enabled:
        from outreach.scheduler import OutreachScheduler
        scheduler = OutreachScheduler(
            outreach_agent=outreach_agent,
            ceo_agent=ceo_agent,
            delivery_agent=outreach_agent.delivery_agent,
        )
        scheduler.start()

    # ── 11d. Dashboard server + Overlay API ─────────────────────────────
    dashboard_server = None
    if outreach_agent.enabled:
        dashboard_app = FastAPI()
        dashboard_app.include_router(get_router())

        @dashboard_app.get("/")
        async def dashboard_root():
            html = (Path(__file__).parent / "outreach" / "dashboard.html").read_text(encoding="utf-8")
            return HTMLResponse(content=html)

        @dashboard_app.get("/api/status")
        async def dashboard_api():
            return DashboardService.get_status()

        @dashboard_app.get("/api/pending-drafts")
        async def pending_drafts_api():
            from outreach.dashboard import DraftApprovalAPI
            return DraftApprovalAPI.list_pending_drafts()

        @dashboard_app.post("/api/drafts/{filename}/approve")
        async def approve_draft_api(filename: str):
            from outreach.dashboard import DraftApprovalAPI
            return DraftApprovalAPI.approve_draft(filename)

        @dashboard_app.post("/api/drafts/{filename}/reject")
        async def reject_draft_api(filename: str):
            from outreach.dashboard import DraftApprovalAPI
            return DraftApprovalAPI.reject_draft(filename)

        dashboard_config = Config(
            app=dashboard_app,
            host="127.0.0.1",
            port=8080,
            log_level="warning",
        )
        dashboard_server = Server(dashboard_config)
        asyncio.create_task(dashboard_server.serve())
        logger.info("Dashboard available at http://127.0.0.1:8080")

    # ── Assistant overlay (if enabled) ───────────────────────────────────
    meeting_assistant = None
    assistant_engine = None
    if ASSISTANT_ENABLED:
        meeting_assistant = MeetingAssistant(memory_system=memory)
        initialized = await meeting_assistant.initialize()
        if initialized:
            assistant_engine = AssistantEngine(memory, reasoner, action_engine)
            asyncio.create_task(_run_meeting_assistant(meeting_assistant, assistant_engine, app_perception))
            logger.info("Assistant overlay enabled with meeting detection")
        else:
            logger.warning("MeetingAssistant initialization failed - overlay disabled")

    # ── 12. Readiness check ─────────────────────────────────────────────
    readiness = await independence.check_readiness()
    logger.info(f"System readiness: {readiness}")
    outreach_summary = outreach_agent.get_summary()
    logger.info(f"Outreach summary: {outreach_summary}")

    # ── 13. Enter main loop ─────────────────────────────────────────────
    if TRADING_ENABLED and trading_agent is not None:
        await run_trading_loop(
            trading_agent=trading_agent,
            neural_brain_service=neural_brain_service,
            domain_expansion_controller=domain_expansion_controller,
            outreach_agent=outreach_agent,
            ceo_agent=ceo_agent,
        )
    else:
        await run_cognition_loop(
            memory=memory,
            reasoner=reasoner,
            meta_learner=meta_learner,
            independence=independence,
            dreaming=dreaming,
            neural_brain_service=neural_brain_service,
            action_engine=action_engine,
            app_perception=app_perception,
            domain_expansion_controller=domain_expansion_controller,
            outreach_agent=outreach_agent,
            ceo_agent=ceo_agent,
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("MECOS stopped by user.")

