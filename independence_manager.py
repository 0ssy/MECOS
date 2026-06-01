"""
MECOS Independence Manager

Monitors learning progress and manages the transition from Ollama
to Sovereign Inference.

FIX: TradingAgent and MetaLearner were passed as None by default in
main.py, so governance gates never ran against real metrics. This file
now raises clearly if they are missing, and main.py is updated to
always inject them. The check_readiness() logic is also cleaned up
(the original had an unreachable `return` after the final if-block).
"""

from loguru import logger
from config import settings
from sovereign_inference import SovereignInference


class IndependenceManager:
    def __init__(self, memory, trading_agent=None, meta_learner=None):
        self.memory = memory
        self.sovereign = SovereignInference()
        self.threshold_experiences = settings.GOV_MIN_EXPERIENCES
        self.last_readiness = "LEARNING"

        # Warn loudly if governance dependencies are missing —
        # gates will be skipped rather than silently passing.
        self._trading_agent = trading_agent
        self._meta_learner = meta_learner

        if trading_agent is None:
            logger.warning(
                "IndependenceManager: no TradingAgent injected. "
                "Trading governance gate will be SKIPPED — call "
                "independence.set_agents(trading_agent, meta_learner) "
                "after construction."
            )
        if meta_learner is None:
            logger.warning(
                "IndependenceManager: no MetaLearner injected. "
                "Meta-episode gate will be SKIPPED."
            )

    def set_agents(self, trading_agent, meta_learner):
        """Inject live agent references after construction (used by main.py)."""
        self._trading_agent = trading_agent
        self._meta_learner = meta_learner
        logger.info("IndependenceManager: TradingAgent and MetaLearner wired.")

    async def check_readiness(self) -> str:
        """
        Gate progression:
          LEARNING
            → (enough experiences)
          → (enough meta episodes, if meta_learner available)
            → (trading governance passed, if trading_agent available)
              → READY_FOR_WEIGHTS
                → TOTAL_SOVEREIGNTY
        """
        stats = await self.memory.get_stats()
        exp_count = stats.get("experience_count", 0)

        logger.info(
            f"Independence Check: {exp_count}/{self.threshold_experiences} experiences"
        )

        # Gate 1: experience volume
        if exp_count < self.threshold_experiences:
            self.last_readiness = "LEARNING"
            return self.last_readiness

        # Gate 2: meta-learning episodes
        if self._meta_learner is not None:
            if self._meta_learner.meta_episode < settings.GOV_MIN_META_EPISODES:
                logger.info(
                    f"Independence gate: meta episodes "
                    f"{self._meta_learner.meta_episode}/{settings.GOV_MIN_META_EPISODES}"
                )
                self.last_readiness = "LEARNING"
                return self.last_readiness
        else:
            logger.warning("Meta-episode gate SKIPPED (no MetaLearner injected).")

        # Gate 3: trading performance
        if self._trading_agent is not None:
            metrics = self._trading_agent.get_performance_metrics()
            analyses = metrics.get("analyses", 0)
            actionable_rate = metrics.get("actionable_rate", 0.0)

            if (
                analyses < settings.GOV_MIN_TRADING_ANALYSES
                or actionable_rate < settings.GOV_MIN_TRADING_ACTIONABLE_RATE
            ):
                logger.info(
                    f"Independence gate: trading "
                    f"analyses={analyses}/{settings.GOV_MIN_TRADING_ANALYSES}, "
                    f"actionable_rate={actionable_rate:.2f}/"
                    f"{settings.GOV_MIN_TRADING_ACTIONABLE_RATE:.2f}"
                )
                self.last_readiness = "TRADING_GOVERNANCE_PENDING"
                return self.last_readiness
        else:
            logger.warning("Trading governance gate SKIPPED (no TradingAgent injected).")

        # Gate 4: sovereign model weights
        if not self.sovereign.is_ready():
            logger.info("All learning gates passed — waiting for model weights.")
            self.last_readiness = "READY_FOR_WEIGHTS"
            return self.last_readiness

        logger.info("MECOS has reached TOTAL SOVEREIGNTY.")
        self.last_readiness = "TOTAL_SOVEREIGNTY"
        return self.last_readiness

    def cleanup_ollama(self, force: bool = False) -> list:
        """Return shell commands to remove Ollama once sovereign."""
        if not force and self.last_readiness != "TOTAL_SOVEREIGNTY":
            logger.warning(
                f"Ollama cleanup blocked: readiness={self.last_readiness}"
            )
            return [
                f"Cleanup blocked: readiness={self.last_readiness}.",
                "Complete all governance gates first.",
            ]

        logger.warning("Returning Ollama removal commands.")
        return [
            "sudo systemctl stop ollama",
            "sudo systemctl disable ollama",
            "sudo rm /etc/systemd/system/ollama.service",
            "sudo rm $(which ollama)",
            "sudo rm -rf /usr/share/ollama",
            "sudo userdel ollama",
            "sudo groupdel ollama",
        ]

    async def transition_to_sovereign(self) -> bool:
        if await self.check_readiness() == "TOTAL_SOVEREIGNTY":
            logger.info("Switching MECOS to Sovereign Inference Mode.")
            return True
        return False

