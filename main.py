"""
MECOS Main Entry Point

Supports both full-system runs (with trading) and stripped-down cognition
loops (without trading) depending on environment flags.

Architecture:
  Memory → Intelligence layer (KG, Curiosity, CrossDomain) → Reasoner
  → ActionExecutionEngine → ToolOrchestrator → tools
  → AppPerception + Agent-Reach perception
  → NeuralBrainService (optional)
  → HealthMonitor + SecurityAgent + GuardianAgent for safety
"""

import asyncio
import os
from typing import Optional
from loguru import logger

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
from outreach.outreach_agent import OutreachAgent

TRADING_ENABLED = os.getenv("MECOS_ENABLE_TRADING", "true").strip().lower() == "true"


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
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("MECOS stopped by user.")

