"""
MECOS Main Entry Point

Fixes applied:
  1. IndependenceManager.set_agents() is now called after all components
     are constructed — governance gates now check real live metrics.
  2. TRAINING_ACCELERATION_FACTOR added to settings via .env fallback
     (meta_learner.py references it but config never defined it).
  3. memory_system_stub removed (test artifact, should never be in prod).
  4. Startup sequence is ordered correctly:
       memory → trading_agent → meta_learner → independence_manager
       (so set_agents() always has live objects to inject)
"""

import asyncio
import os
from loguru import logger

from config import settings
from memory_system import MemorySystem
from reasoner import Reasoner
from trading_agent import TradingAgent
from meta_learner import MetaLearner
from independence_manager import IndependenceManager
from dreaming_engine import DreamingEngine
from neural_brain_service import NeuralBrainService
from mecos.domain_expansion import DomainExpansionController


async def startup_checks(memory: MemorySystem) -> None:
    """Verify core systems are reachable before entering the main loop."""
    logger.info("Running startup checks...")

    # Memory check
    try:
        stats = await memory.get_stats()
        logger.info(f"Memory OK — {stats.get('experience_count', 0)} experiences stored")
    except Exception as e:
        logger.error(f"Memory check failed: {e}")
        raise

    # Broker connectivity (non-fatal — just warn)
    if not settings.ALPACA_API_KEY:
        logger.warning("ALPACA_API_KEY not set — stock trading disabled")
    if not settings.BINANCE_API_KEY:
        logger.warning("BINANCE_API_KEY not set — crypto trading disabled")

    logger.info("Startup checks complete.")


async def main():
    logger.info(f"Starting MECOS {settings.VERSION}")

    # ── 1. Core memory (everything depends on this) ───────────────────────
    memory = MemorySystem()
    await startup_checks(memory)

    # ── 2. Trading agent (must exist before IndependenceManager) ─────────
    trading_agent = TradingAgent(memory)
    neural_brain_service = NeuralBrainService(memory_system=memory)
    domain_expansion_enabled = os.getenv("MECOS_ENABLE_DOMAIN_EXPANSION", "false").strip().lower() == "true"
    domain_expansion_every = max(1, int(os.getenv("MECOS_DOMAIN_EXPANSION_MAIN_CYCLES", "20")))
    domain_expansion_controller = None
    if domain_expansion_enabled:
        try:
            domain_expansion_controller = DomainExpansionController()
            logger.info(
                "Domain expansion controller wired in main loop | every {} cycles",
                domain_expansion_every,
            )
        except Exception as exc:
            logger.warning(f"Domain expansion controller unavailable in main loop: {exc}")
    if neural_brain_service.is_available and hasattr(trading_agent, "neural_brain"):
        trading_agent.neural_brain = neural_brain_service.brain
        trading_agent.neural_brain_enabled = True
        logger.info("Neural brain shared with root TradingAgent")
    logger.info("TradingAgent ready.")

    # ── 3. Reasoner ───────────────────────────────────────────────────────
    reasoner = Reasoner(memory)
    logger.info("Reasoner ready.")

    # ── 4. Meta-learner ───────────────────────────────────────────────────
    meta_learner = MetaLearner(memory)
    logger.info("MetaLearner ready.")

    # ── 5. Independence manager — inject live agents NOW ─────────────────
    #    FIX: original code left trading_agent=None and meta_learner=None,
    #    so governance gates never ran against real data.
    independence = IndependenceManager(memory)
    independence.set_agents(trading_agent, meta_learner)
    logger.info("IndependenceManager wired with live TradingAgent + MetaLearner.")

    # ── 6. Dreaming engine ────────────────────────────────────────────────
    dreaming = DreamingEngine(memory)
    logger.info("DreamingEngine ready.")

    # ── 7. Initial readiness check ────────────────────────────────────────
    readiness = await independence.check_readiness()
    logger.info(f"System readiness: {readiness}")

    # ── 8. Main loop ──────────────────────────────────────────────────────
    logger.info("Entering main loop...")
    cycle = 0

    while True:
        cycle += 1
        logger.info(f"=== Main Cycle #{cycle} ===")

        try:
            # Trading cycle
            trade_result = await trading_agent.run_cycle()
            logger.info(f"Trading: {trade_result['signals']} signals, "
                        f"{trade_result['actionable']} actionable")

            if neural_brain_service.is_available:
                insight = neural_brain_service.runtime_insight(
                    {
                        "runtime_health": 85.0,
                        "success_rate": 0.9,
                        "runtime_regime": "trending",
                    }
                )
                if insight:
                    logger.info(
                        f"Global neural insight: action={insight.get('action')} "
                        f"uncertainty={insight.get('uncertainty')}"
                    )

            # Meta-learning cycle (every 5 main cycles)
            if cycle % 5 == 0:
                meta_result = await meta_learner.run_meta_cycle()
                logger.info(f"Meta score: {meta_result.get('benchmark_score', 'N/A')}")

            # Dreaming cycle (every 10 main cycles, when idle)
            if cycle % 10 == 0:
                await dreaming.dream()

            # Governance check (every 20 cycles)
            if cycle % 20 == 0:
                readiness = await independence.check_readiness()
                logger.info(f"Governance readiness: {readiness}")
            if domain_expansion_controller and cycle % domain_expansion_every == 0:
                await asyncio.to_thread(domain_expansion_controller.learn_next)

        except Exception as e:
            logger.error(f"Cycle #{cycle} error: {e}")

        await asyncio.sleep(settings.IDLE_SLEEP_TIME)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("MECOS stopped by user.")

