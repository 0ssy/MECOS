import asyncio
import sys
import os
import json
import time
from loguru import logger
from config import settings

# Import all MECOS modules
from perception import PerceptionLayer as Perception
from reasoner import Reasoner
from action_engine import ActionEngine
from memory_system import MemorySystem
from trading_agent import TradingAgent
from coding_agent import CodingAgent
from research_agent import ResearchAgent
from agent_coordinator import AgentCoordinator
from rl_trainer import RLTrainer
from self_supervised_trainer import SelfSupervisedTrainer
from curriculum_manager import CurriculumManager
from memory_consolidation import MemoryConsolidation
from benchmarking import BenchmarkingEngine
from genetic_optimizer import GeneticOptimizer
from strategy_evolution import StrategyEvolution
from meta_learner import MetaLearner
from checkpoint_manager import CheckpointManager
from world_model import WorldModel
from dreaming_engine import DreamingEngine
from independence_manager import IndependenceManager

class MECOSEngine:
    def __init__(self):
        logger.info("Initializing MECOS Engine (Sovereign Quant Edition)...")
        
        # Core Systems
        self.memory = MemorySystem()
        self.perception = Perception(self.memory)
        self.reasoner = Reasoner(self.memory)
        self.action_engine = ActionEngine()
        
        # Specialized Agents
        self.trading = TradingAgent(self.memory)
        self.coding = CodingAgent(self.memory)
        self.research = ResearchAgent(self.memory)
        self.coordinator = AgentCoordinator(self.trading, self.coding, self.research)
        
        # Learning Engines
        self.rl_trainer = RLTrainer(self.memory)
        self.self_supervised = SelfSupervisedTrainer(self.memory)
        self.curriculum = CurriculumManager(self.memory)
        self.consolidation = MemoryConsolidation(self.memory)
        self.benchmarking = BenchmarkingEngine(self.memory)
        
        # Evolution & Meta-Learning
        self.genetic_opt = GeneticOptimizer()
        self.strategy_evo = StrategyEvolution(self.memory)
        self.meta_learner = MetaLearner(self.rl_trainer, self.strategy_evo, self.benchmarking)
        self.checkpoint = CheckpointManager(settings.BASE_DIR)
        self.world_model = WorldModel(self.memory)
        
        # Autonomy & Independence
        self.dreaming = DreamingEngine(self.memory)
        self.independence = IndependenceManager(self.memory)
        
        self.is_running = True
        self.cycle_count = 0

    async def startup(self):
        logger.info("MECOS Engine started. All 7 phases initialized.")
        await self.memory.add_experience("System startup initiated.", source="system")

    async def process_goal(self, goal: str):
        """
        The full cognitive cycle for a goal:
        Observe → Simulate → Reason → Act → Learn → Reflect
        """
        logger.info(f"Processing goal: '{goal}'")

        # 1. Observe
        await self.perception.collect()

        # 2. Reason & Plan
        plan = await self.reasoner.generate_plan(goal)

        # 3. Simulate plan risk before execution
        simulation = await self.world_model.simulate_plan(plan)
        risk_score = simulation.get("risk_score", 0)
        logger.info(f"Plan risk: {'HIGH' if risk_score > 0.7 else 'LOW'} (score={risk_score})")

        results = []
        if plan and risk_score < 0.9:
            # 4. Execute plan
            logger.info(f"Executing plan with {len(plan)} steps...")
            results = await self.action_engine.execute_plan(plan)

            # 5. Record transitions in world model
            for r in results:
                self.world_model.record_transition(
                    state=goal,
                    action=r.get("tool", ""),
                    outcome=str(r.get("result", "")),
                    next_state=f"after_{r.get('tool', '')}",
                    reward=1.0 if r.get("success") else -0.5,
                )

            # 6. RL: record experience
            success_rate = sum(1 for r in results if r.get("success")) / max(len(results), 1)
            self.rl_trainer.record_experience(
                state=goal[:100],
                action="execute_plan",
                outcome={"success": success_rate > 0.5},
                next_state="post_execution",
            )

            # 7. Reflect
            await self.reasoner.reflect(goal, plan, results)

            # 8. Strategy performance feedback
            self.meta_learner.strategy_evolution.record_performance(success_rate)
        else:
            logger.warning("Plan rejected or empty.")

        return results

    async def run_away_mode(self):
        """Continuous autonomous operation while the user is away."""
        logger.info("MECOS entering 'Away Mode' (Autonomous Dreaming).")
        while self.is_running:
            # 1. Check for Independence Readiness
            readiness = await self.independence.check_readiness()
            if readiness == "TOTAL_SOVEREIGNTY":
                logger.warning("MECOS HAS REACHED TOTAL SOVEREIGNTY.")
            
            # 2. Generate a self-goal (FIXED: Now inside the loop)
            goal = await self.dreaming.generate_self_goal(context="Focus on Global Macro Quant Trading.")
            
            # 3. Execute the goal
            await self.process_goal(goal)
            
            # 4. Self-reflect & Meta-learn
            await self.dreaming.self_reflect()
            await self.meta_learner.run_meta_cycle()
            
            logger.info(f"Cycle complete. Sleeping for {settings.IDLE_SLEEP_TIME}s...")
            await asyncio.sleep(settings.IDLE_SLEEP_TIME)

    async def main_loop(self):
        """Heartbeat loop for interactive mode."""
        while self.is_running:
            logger.debug(f"Heartbeat #{self.cycle_count}")
            self.cycle_count += 1
            # Run background learning every 5 cycles
            if self.cycle_count % 5 == 0:
                await self.meta_learner.run_meta_cycle()
            await asyncio.sleep(settings.IDLE_SLEEP_TIME)

async def main():
    engine = MECOSEngine()
    await engine.startup()

    mode = sys.argv[1] if len(sys.argv) > 1 else "default"

    if mode == "away":
        await engine.run_away_mode()
    elif mode == "cleanup":
        commands = engine.independence.cleanup_ollama()
        print("To remove Ollama, run these commands:")
        for cmd in commands: print(f"  {cmd}")
    else:
        # INTERACTIVE MODE: Ask for a goal
        print("\n" + "="*50)
        print("MECOS SOVEREIGN QUANT MODE")
        print("="*50)
        user_goal = input("What is your goal for MECOS today? > ")
        
        if user_goal.strip():
            await engine.process_goal(user_goal)
            await engine.main_loop()
        else:
            await engine.main_loop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("MECOS shutdown by user.")
