"""
MECOS - Meta-Cognitive Engine for Continuous Operation and Self-improvement
Full system entry point integrating all 7 phases + Dreaming + Independence.
"""

import asyncio
import sys
from loguru import logger

from config import settings

# ── Phase 1-3: Core ──────────────────────────────────────────────────────────
from memory_system import MemorySystem
from perception import PerceptionLayer
from web_perception import WebPerception
from reasoner import Reasoner

# ── Phase 4: Tool Orchestration ───────────────────────────────────────────────
from tool_orchestrator import ToolOrchestrator
from action_engine import ActionExecutionEngine

# ── Phase 5: Specialized Agents ───────────────────────────────────────────────
from trading_agent import TradingAgent
from coding_agent import CodingAgent
from research_agent import ResearchAgent
from agent_coordinator import AgentCoordinator, AgentRole

# ── Phase 6: Learning Engines ─────────────────────────────────────────────────
from rl_trainer import RLTrainer
from self_supervised_trainer import SelfSupervisedTrainer
from curriculum_manager import CurriculumManager
from memory_consolidation import MemoryConsolidation
from benchmarking import BenchmarkingEngine

# ── Phase 7: Evolution & Meta-Learning ───────────────────────────────────────
from meta_learner import MetaLearner
from checkpoint_manager import CheckpointManager
from world_model import WorldModel

# ── Autonomous & Sovereignty ─────────────────────────────────────────────────
from dreaming_engine import DreamingEngine
from independence_manager import IndependenceManager


class MECOSEngine:
    """
    The complete MECOS cognitive engine.
    Integrates all 7 phases into a unified autonomous system.
    """

    def __init__(self):
        self.is_running = False

        # Configure logging
        log_path = settings.LOGS_DIR
        log_path.mkdir(parents=True, exist_ok=True)
        logger.add(log_path / "engine.log", rotation="100 MB", retention="7 days", level="DEBUG")
        logger.add(sys.stdout, level="INFO", colorize=True)
        logger.info(f"Initializing {settings.PROJECT_NAME} Engine (all 7 phases + Dreaming + Independence)...")

        # ── Phase 1: Memory ───────────────────────────────────────────────
        self.memory = MemorySystem()

        # ── Phase 2: Perception ───────────────────────────────────────────
        self.perception = PerceptionLayer(self.memory)
        self.web_perception = WebPerception(self.memory)

        # ── Phase 3: Reasoning ────────────────────────────────────────────
        self.reasoner = Reasoner(self.memory)

        # ── Phase 4: Tool Orchestration ───────────────────────────────────
        self.orchestrator = ToolOrchestrator()
        self.orchestrator.web_perception = self.web_perception
        self.action_engine = ActionExecutionEngine(self.orchestrator, self.memory)

        # ── Phase 5: Specialized Agents ───────────────────────────────────
        self.trading_agent = TradingAgent(self.memory)
        self.coding_agent = CodingAgent(self.memory, self.orchestrator)
        self.research_agent = ResearchAgent(self.memory, self.web_perception)
        self.coordinator = AgentCoordinator(self.memory)
        self.coordinator.register_agent("trading", self.trading_agent, AgentRole.TRADING)
        self.coordinator.register_agent("coding", self.coding_agent, AgentRole.CODING)
        self.coordinator.register_agent("research", self.research_agent, AgentRole.RESEARCH)

        # ── Phase 6: Learning Engines ─────────────────────────────────────
        self.rl_trainer = RLTrainer(self.memory, domain="general")
        self.ssl_trainer = SelfSupervisedTrainer(self.memory)
        self.curriculum = CurriculumManager(self.memory)
        self.consolidation = MemoryConsolidation(self.memory)
        self.benchmarking = BenchmarkingEngine(self.memory)

        # ── Phase 7: Evolution & Meta-Learning ───────────────────────────
        self.meta_learner = MetaLearner(self.memory)
        self.checkpoint_manager = CheckpointManager()
        self.world_model = WorldModel(self.memory)

        # ── Autonomous & Sovereignty ──────────────────────────────────────
        self.dreaming = DreamingEngine(self.memory)
        self.independence = IndependenceManager(self.memory)

        logger.info("All 7 phases + Dreaming + Independence initialized successfully.")

    async def startup(self):
        """Initialize all subsystems that require async startup."""
        logger.info("Starting subsystems...")
        await self.web_perception.startup()
        self.is_running = True
        logger.info("MECOS Engine is running.")

    async def shutdown(self):
        """Gracefully shut down all subsystems."""
        logger.info("Shutting down MECOS Engine...")
        await self.web_perception.shutdown()
        self.is_running = False
        logger.info("Shutdown complete.")

    async def process_goal(self, goal: str) -> dict:
        """
        The full cognitive cycle for a goal:
        Observe → Simulate → Reason → Act → Learn → Reflect
        """
        logger.info(f"Processing goal: '{goal}'")

        # 1. Observe — collect environmental data
        await self.perception.collect(str(settings.DATA_DIR))

        # 2. Reason & Plan
        plan = await self.reasoner.generate_plan(goal)

        # 3. Simulate plan risk before execution
        risk = await self.world_model.evaluate_plan_risk(plan, goal)
        logger.info(f"Plan risk: {risk['risk_level']} (score={risk['risk_score']})")

        results = []
        if plan:
            # 4. Execute plan
            results = await self.action_engine.execute_plan(plan)

            # 5. Record transitions in world model
            for r in results:
                self.world_model.record_transition(
                    state=goal,
                    action=r.get("tool", ""),
                    outcome=r.get("result", ""),
                    next_state=f"after_{r.get('tool', '')}",
                    reward=1.0 if r.get("success") else -0.5,
                )

            # 6. RL: record experience
            success_rate = sum(1 for r in results if r.get("success")) / max(len(results), 1)
            self.rl_trainer.record_experience(
                state=goal[:100],
                action="execute_plan",
                outcome={"success": success_rate > 0.5, "partial": 0.3 <= success_rate <= 0.5},
                next_state="post_execution",
            )

            # 7. Reflect
            await self.reasoner.reflect(goal, plan, results)

            # 8. Strategy performance feedback
            self.meta_learner.strategy_evolution.record_performance(success_rate)

        return {
            "goal": goal,
            "plan_steps": len(plan),
            "results": results,
            "risk": risk,
        }


    async def run_away_mode(self):
        """Continuous autonomous operation while the user is away."""
        logger.info("MECOS entering 'Away Mode' (Autonomous Dreaming).")
        while self.is_running:
            # 1. Check for Independence Readiness
            readiness = await self.independence.check_readiness()
            if readiness == "TOTAL_SOVEREIGNTY":
                logger.warning("MECOS HAS REACHED TOTAL SOVEREIGNTY. OLLAMA IS NO LONGER NEEDED.")
            # 2. Generate a self-goal (NOW INSIDE THE LOOP)
            goal = await self.dreaming.generate_self_goal(context="Focus on Quantitative Trading and Algorithmic Self-Improvement.")
            # 3. Execute the goal
            await self.process_goal(goal)
            # 4. Self-reflect
            await self.dreaming.self_reflect()
            # 5. Rest/Idle to manage resources
            logger.info(f"Goal complete. Sleeping for {settings.IDLE_SLEEP_TIME}s...")
            await asyncio.sleep(settings.IDLE_SLEEP_TIME)


    async def run_learning_cycle(self):
        """Run a full meta-learning cycle."""
        logger.info("Running meta-learning cycle...")
        return await self.meta_learner.run_meta_cycle()

    async def create_checkpoint(self, label: str = "") -> str:
        """Create a system state checkpoint."""
        return await self.checkpoint_manager.create_checkpoint(label=label)

    async def collaborative_solve(self, goal: str) -> dict:
        """Use multi-agent collaboration to solve a complex goal."""
        return await self.coordinator.collaborative_solve(goal)

    def get_system_status(self) -> dict:
        """Return a comprehensive system status report."""
        return {
            "running": self.is_running,
            "learning_status": self.meta_learner.get_learning_status(),
            "tools_available": len(self.orchestrator.registry.list_tools()),
            "agents_registered": self.coordinator.get_registered_agents(),
            "world_model": self.world_model.get_model_stats(),
            "checkpoints": len(self.checkpoint_manager.list_checkpoints()),
            "independence_readiness": asyncio.run(self.independence.check_readiness()) if self.is_running else "UNKNOWN"
        }

    async def main_loop(self, learning_interval: int = 300):
        """
        The core autonomous loop.
        Runs a meta-learning cycle every `learning_interval` seconds.
        """
        logger.info(f"Entering core cognitive loop (learning every {learning_interval}s).")
        cycle = 0
        try:
            while self.is_running:
                cycle += 1
                logger.debug(f"Heartbeat #{cycle}: Engine monitoring.")

                # Periodic learning cycle
                if cycle % (learning_interval // 10) == 0:
                    await self.run_learning_cycle()

                await asyncio.sleep(10)
        except asyncio.CancelledError:
            await self.shutdown()


async def main():
    engine = MECOSEngine()
    await engine.startup()

    # Check for command line arguments
    mode = sys.argv[1] if len(sys.argv) > 1 else "default"

    if mode == "away":
        # AUTONOMOUS MODE: MECOS sets its own goals
        await engine.run_away_mode()
    elif mode == "cleanup":
        # CLEANUP MODE: Remove Ollama
        commands = engine.independence.cleanup_ollama()
        print("To remove Ollama from your server, run these commands:")
        for cmd in commands:
            print(f"  {cmd}")
    else:
        # INTERACTIVE MODE: MECOS asks YOU for a goal
        print("\n" + "="*50)
        print("MECOS INTERACTIVE MODE")
        print("="*50)
        user_goal = input("What is your goal for MECOS today? > ")
        
        if user_goal.strip():
            await engine.create_checkpoint(label="user_initiated_task")
            await engine.process_goal(user_goal)
            await engine.main_loop()
        else:
            print("No goal entered. Exiting.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
