"""
MECOS - Meta-Cognitive Engine for Continuous Operation and Self-improvement
Full system entry point integrating all 7 phases + Dreaming + Independence.
"""

import asyncio
import sys
import random
from contextlib import suppress
from urllib.parse import quote_plus
from loguru import logger
from exploration.browser_explorer import BrowserExplorer
from exploration.config import config as exploration_config
from exploration.knowledge_base import KnowledgeBase
from exploration.vision_analyzer import VisionAnalyzer

from config import settings
from exploration.sync_tool import sync_server_knowledge


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
        self.goal_history = []
        self.background_tasks = []
        self._shutdown_started = False

        # Configure logging
        log_path = settings.LOGS_DIR
        log_path.mkdir(parents=True, exist_ok=True)
        logger.remove()
        logger.add(log_path / "engine.log", rotation="100 MB", retention="7 days", level="DEBUG")
        logger.add(sys.stdout, level="INFO", colorize=True)
        logger.info(f"Initializing {settings.PROJECT_NAME} Engine (all 7 phases + Dreaming + Independence)...")

        # ── Phase 1: Memory ───────────────────────────────────────────────
        self.memory = MemorySystem()

        # ── Phase 4: Tool Orchestration ───────────────────────────────────
        self.orchestrator = ToolOrchestrator()

        # ── Phase 2: Perception ───────────────────────────────────────────
        self.perception = PerceptionLayer(self.memory, self.orchestrator.app_controller)
        self.web_perception = WebPerception(self.memory)

        # ── Phase 3: Reasoning ────────────────────────────────────────────
        self.reasoner = Reasoner(self.memory)

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
        self.independence = IndependenceManager(self.memory, self.trading_agent, self.meta_learner)
        self.knowledge_base = KnowledgeBase()
        self.vision = VisionAnalyzer()

        logger.info("All 7 phases + Dreaming + Independence initialized successfully.")

    async def startup(self):
        """Initialize all subsystems that require async startup."""
        logger.info("Starting subsystems...")
        await self.web_perception.startup()
        self.is_running = True
        logger.info("MECOS Engine is running.")
        self.browser = BrowserExplorer(self.knowledge_base, self.vision)
        await self.browser.startup()

        # Run exploration in background
        self.background_tasks.append(asyncio.create_task(self._run_browser_exploration()))
        self.background_tasks.append(asyncio.create_task(self._run_web_learning_loop()))
        self.background_tasks.append(asyncio.create_task(self._run_app_learning_loop()))
        self.background_tasks.append(asyncio.create_task(self.knowledge_sync_loop()))

    async def knowledge_sync_loop(self):
        while True:
            try:
                await sync_server_knowledge()
                await asyncio.sleep(3600)  # Sync every hour
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Knowledge sync loop error: {e}")
                await asyncio.sleep(30)

    async def _run_browser_exploration(self):
        while self.is_running:
            try:
                focus_goal = random.choice(self.goal_history) if self.goal_history else random.choice(self.dreaming.curiosity_topics)
                seed_urls = self._build_goal_seed_urls(focus_goal, samples=1)
                if seed_urls:
                    await self.browser.explore(seed_urls[0], "goal_exploration")
                await asyncio.sleep(exploration_config.EXPLORATION_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Browser exploration loop error: {e}")
                await asyncio.sleep(10)

    async def _run_web_learning_loop(self):
        while self.is_running:
            try:
                focus_goal = random.choice(self.goal_history) if self.goal_history else random.choice(self.dreaming.curiosity_topics)
                seed_urls = self._build_goal_seed_urls(focus_goal, samples=3)
                await self.web_perception.crawl_web(
                    seed_urls=seed_urls,
                    max_pages=settings.WEB_CRAWL_MAX_PAGES,
                    max_depth=settings.WEB_CRAWL_MAX_DEPTH,
                    same_domain_only=False,
                )
                await asyncio.sleep(exploration_config.EXPLORATION_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Web learning loop error: {e}")
                await asyncio.sleep(10)

    async def _run_app_learning_loop(self):
        while self.is_running:
            try:
                await self.perception.app_perception.map_computer()
                await asyncio.sleep(exploration_config.EXPLORATION_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"App learning loop error: {e}")
                await asyncio.sleep(10)
        

    async def shutdown(self):
        """Gracefully shut down all subsystems."""
        if self._shutdown_started:
            return
        self._shutdown_started = True
        logger.info("Shutting down MECOS Engine...")
        self.is_running = False
        if self.background_tasks:
            wait_timeout = max(10, int(settings.WEB_NAVIGATION_TIMEOUT_MS / 1000) + 5)
            done, pending = await asyncio.wait(self.background_tasks, timeout=wait_timeout)
            for task in pending:
                task.cancel()
            if pending:
                with suppress(Exception):
                    await asyncio.wait_for(
                        asyncio.gather(*pending, return_exceptions=True),
                        timeout=3,
                    )
        self.background_tasks = []
        with suppress(Exception):
            if hasattr(self, "browser") and self.browser:
                await self.browser.shutdown()
        await self.web_perception.shutdown()
        logger.info("Shutdown complete.")

    async def process_goal(self, goal: str) -> dict:
        """
        The full cognitive cycle for a goal:
        Observe → Simulate → Reason → Act → Learn → Reflect
        """
        goal = (goal or "").strip()
        if not goal:
            goal = f"Autonomous learning focus: {random.choice(self.dreaming.curiosity_topics)}"
            logger.warning(f"Received empty goal. Using fallback goal: '{goal}'")

        logger.info(f"Processing goal: '{goal}'")
        await self.memory.add_experience(
            content=f"USER REQUEST: {goal}",
            source="user_goal",
        )
        self.goal_history.append(goal)
        if len(self.goal_history) > 100:
            self.goal_history.pop(0)

        if settings.ASSIST_WEB_LOOKUP_ENABLED and self._needs_web_assist(goal):
            assist_urls = self._build_goal_seed_urls(goal, samples=5)
            await self.web_perception.crawl_web(
                seed_urls=assist_urls,
                max_pages=settings.ASSIST_WEB_MAX_PAGES,
                max_depth=settings.ASSIST_WEB_MAX_DEPTH,
                same_domain_only=False,
            )

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

    def _needs_web_assist(self, goal: str) -> bool:
        goal_l = goal.lower()
        assist_signals = [
            "help",
            "how",
            "what",
            "learn",
            "research",
            "?",
        ]
        return any(signal in goal_l for signal in assist_signals)

    def _build_goal_seed_urls(self, goal: str, samples: int = 3) -> list:
        goal = (goal or "").strip()
        if not goal:
            return []
        query_variants = [
            goal,
            f"{goal} tutorial",
            f"{goal} guide",
            f"{goal} workflow",
            f"{goal} examples",
        ]
        random.shuffle(query_variants)
        templates = list(settings.WEB_SEARCH_URL_TEMPLATES)
        random.shuffle(templates)

        urls = []
        for template in templates:
            for query in query_variants:
                q = quote_plus(query)
                urls.append(template.format(query=q))
                if len(urls) >= max(1, samples):
                    return urls
        return urls[:max(1, samples)]


    async def run_away_mode(self):
        """Continuous autonomous operation while the user is away."""
        logger.info("MECOS entering 'Away Mode' (Autonomous Dreaming).")
        while self.is_running:
            # 1. Check for Independence Readiness
            readiness = await self.independence.check_readiness()
            if readiness == "TOTAL_SOVEREIGNTY":
                logger.warning("MECOS HAS REACHED TOTAL SOVEREIGNTY. OLLAMA IS NO LONGER NEEDED.")
            # 2. Generate a self-goal (NOW INSIDE THE LOOP)
            goal = await self.dreaming.generate_self_goal()

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

    def _recent_memory_fallback(self, user_message: str, limit: int = 3) -> str:
        """Build a deterministic fallback reply from recent memory when LLM is unavailable."""
        entries = list(reversed(self.memory.short_term_buffer[-50:]))
        if not entries:
            return "I couldn't generate a full response right now, and I don't have recent memory entries to summarize yet."

        is_discovery_query = any(
            token in (user_message or "").lower()
            for token in ("discover", "learn", "found", "what have you", "background")
        )

        summary_lines = []
        seen = set()
        for entry in entries:
            source = (entry.get("source") or "general").strip()
            content = (entry.get("content") or "").strip()
            if not content:
                continue

            line = None
            if content.startswith("WEB CONTENT ("):
                right = content.find("):")
                if right > len("WEB CONTENT ("):
                    url = content[len("WEB CONTENT ("):right]
                    line = f"- Web: ingested {url}"
            elif content.startswith("WEB CRAWL SUMMARY:"):
                line = f"- Web: {content[:180]}"
            elif content.startswith("APP MAP ["):
                line = "- Apps: updated local app/process map snapshot."
            elif content.startswith("APP WORKFLOW TRACE:"):
                line = f"- Apps: {content[:180]}"
            elif source in {"web_perception", "web_perception_crawl", "app_perception", "app_workflow_learning"}:
                line = f"- {source}: {content[:180]}"
            elif not is_discovery_query:
                line = f"- {source}: {content[:180]}"

            if line:
                key = line.lower()
                if key not in seen:
                    seen.add(key)
                    summary_lines.append(line)
            if len(summary_lines) >= max(1, int(limit)):
                break

        if not summary_lines:
            return "I couldn't generate a full response right now, but I am still learning in the background."

        if is_discovery_query:
            return "LLM timed out, but here are my latest memory-backed discoveries:\n" + "\n".join(summary_lines)
        return "LLM timed out, but here are recent memory-backed updates:\n" + "\n".join(summary_lines)

    async def chat(self, user_message: str) -> str:
        """Conversational reply using memory context while background learning continues."""
        message = (user_message or "").strip()
        if not message:
            return ""

        context_results = await self.memory.retrieve_context(message)
        docs = context_results.get("documents", [[]])
        context_str = "\n".join(docs[0][:5]) if docs and docs[0] else ""

        prompt = f"""
You are MECOS, a practical personal AI assistant.

USER MESSAGE:
{message}

RELEVANT MEMORY:
{context_str}

Respond directly and clearly.
"""
        result = await self.reasoner.llm.think_and_act(
            prompt,
            system_prompt="You are the MECOS Conversational Assistant.",
        )
        reply = (result.get("response") or "").strip()
        if not reply:
            reply = self._recent_memory_fallback(message, limit=3)

        await self.memory.add_experience(
            content=f"CHAT USER: {message}\nCHAT ASSISTANT: {reply}",
            source="chat",
        )
        return reply

    async def chat_loop(self):
        """
        Interactive chat loop that keeps MECOS learning in the background.
        Commands:
          /goal <text>  -> run full goal execution pipeline
          /status       -> print current system status
          /exit         -> leave chat
        """
        print("\n" + "=" * 50)
        print("MECOS CHAT MODE")
        print("=" * 50)
        print("Type /goal <text> to execute a goal, /status for system status, /exit to quit.")

        learning_task = asyncio.create_task(self.main_loop())
        try:
            while self.is_running:
                user_input = await asyncio.to_thread(input, "You > ")
                user_input = (user_input or "").strip()
                if not user_input:
                    continue

                user_l = user_input.lower()
                if user_l in {"/exit", "exit", "quit"}:
                    break

                if user_l == "/status":
                    status = await self.get_system_status_async()
                    print(f"MECOS > {status}")
                    continue

                if user_l.startswith("/goal "):
                    goal = user_input[6:].strip()
                    if goal:
                        await self.create_checkpoint(label="chat_goal")
                        result = await self.process_goal(goal)
                        print(
                            "MECOS > "
                            f"Goal executed. plan_steps={result.get('plan_steps', 0)}, "
                            f"risk={result.get('risk', {}).get('risk_level', 'UNKNOWN')}"
                        )
                    continue

                reply = await self.chat(user_input)
                print(f"MECOS > {reply}")
        finally:
            self.is_running = False
            learning_task.cancel()
            with suppress(asyncio.CancelledError):
                await learning_task
            await self.shutdown()

    async def collaborative_solve(self, goal: str) -> dict:
        """Use multi-agent collaboration to solve a complex goal."""
        return await self.coordinator.collaborative_solve(goal)

    def get_system_status(self) -> dict:
        """Return a comprehensive system status report."""
        readiness = "UNKNOWN"
        if self.is_running:
            try:
                asyncio.get_running_loop()
                readiness = self.independence.last_readiness
            except RuntimeError:
                readiness = asyncio.run(self.independence.check_readiness())
        return {
            "running": self.is_running,
            "learning_status": self.meta_learner.get_learning_status(),
            "tools_available": len(self.orchestrator.registry.list_tools()),
            "agents_registered": self.coordinator.get_registered_agents(),
            "world_model": self.world_model.get_model_stats(),
            "checkpoints": len(self.checkpoint_manager.list_checkpoints()),
            "independence_readiness": readiness,
        }

    async def get_system_status_async(self) -> dict:
        """Async-safe status report for running event loops (chat mode)."""
        readiness = await self.independence.check_readiness() if self.is_running else "UNKNOWN"
        return {
            "running": self.is_running,
            "learning_status": self.meta_learner.get_learning_status(),
            "tools_available": len(self.orchestrator.registry.list_tools()),
            "agents_registered": self.coordinator.get_registered_agents(),
            "world_model": self.world_model.get_model_stats(),
            "checkpoints": len(self.checkpoint_manager.list_checkpoints()),
            "independence_readiness": readiness,
        }

    async def main_loop(self, learning_interval: int = 300):
        """
        The core autonomous loop.
        Runs a meta-learning cycle every `learning_interval` seconds.
        """
        effective_learning_interval = max(
            60,
            int(learning_interval / max(1, settings.TRAINING_ACCELERATION_FACTOR))
        )
        logger.info(f"Entering core cognitive loop (learning every {effective_learning_interval}s).")
        cycle = 0
        try:
            while self.is_running:
                cycle += 1
                logger.debug(f"Heartbeat #{cycle}: Engine monitoring.")

                # Periodic learning cycle
                cycle_window = max(1, effective_learning_interval // 10)
                if cycle % cycle_window == 0:
                    await self.run_learning_cycle()

                await asyncio.sleep(10)
        except asyncio.CancelledError:
            return


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
        # CHAT MODE: conversational loop + background learning
        await engine.chat_loop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
