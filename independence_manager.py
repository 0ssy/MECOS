"""
MECOS Independence Manager
Monitors learning progress and manages the transition from Ollama to Sovereign Inference.
"""

import os
import shutil
from loguru import logger
from config import settings
from sovereign_inference import SovereignInference

class IndependenceManager:
    def __init__(self, memory, trading_agent=None, meta_learner=None):
        self.memory = memory
        self.trading_agent = trading_agent
        self.meta_learner = meta_learner
        self.sovereign = SovereignInference()
        self.threshold_experiences = settings.GOV_MIN_EXPERIENCES
        self.last_readiness = "LEARNING"

    async def check_readiness(self):
        """Check if MECOS has learned enough to go sovereign."""
        stats = await self.memory.get_stats()
        exp_count = stats.get("experience_count", 0)
        
        logger.info(f"Independence Check: {exp_count}/{self.threshold_experiences} experiences gathered.")
        
        if exp_count < self.threshold_experiences:
            self.last_readiness = "LEARNING"
            return self.last_readiness

        if self.meta_learner and self.meta_learner.meta_episode < settings.GOV_MIN_META_EPISODES:
            logger.info(
                "Independence gate pending: "
                f"meta episodes {self.meta_learner.meta_episode}/{settings.GOV_MIN_META_EPISODES}"
            )
            self.last_readiness = "LEARNING"
            return self.last_readiness

        if self.trading_agent:
            trading_metrics = self.trading_agent.get_performance_metrics()
            analyses = trading_metrics.get("analyses", 0)
            actionable_rate = trading_metrics.get("actionable_rate", 0.0)
            if analyses < settings.GOV_MIN_TRADING_ANALYSES or actionable_rate < settings.GOV_MIN_TRADING_ACTIONABLE_RATE:
                logger.info(
                    "Independence gate pending: "
                    f"trading analyses={analyses}/{settings.GOV_MIN_TRADING_ANALYSES}, "
                    f"actionable_rate={actionable_rate:.2f}/{settings.GOV_MIN_TRADING_ACTIONABLE_RATE:.2f}"
                )
                self.last_readiness = "TRADING_GOVERNANCE_PENDING"
                return self.last_readiness

        if not self.sovereign.is_ready():
            logger.info("MECOS is ready for independence, but model weights are missing.")
            self.last_readiness = "READY_FOR_WEIGHTS"
            return self.last_readiness
        
        logger.info("MECOS is fully ready for Total Sovereignty.")
        self.last_readiness = "TOTAL_SOVEREIGNTY"
        return self.last_readiness
            
        self.last_readiness = "LEARNING"
        return self.last_readiness

    def cleanup_ollama(self, force: bool = False):
        """Tool to remove Ollama from the server once sovereign."""
        if not force and self.last_readiness != "TOTAL_SOVEREIGNTY":
            logger.warning(f"Ollama cleanup blocked by governance gate: {self.last_readiness}")
            return [
                f"Ollama cleanup blocked: readiness={self.last_readiness}.",
                "Run more trading cycles and meta-learning, then re-check readiness.",
            ]
        logger.warning("INITIATING OLLAMA CLEANUP...")
        # This would be executed on the server laptop
        commands = [
            "sudo systemctl stop ollama",
            "sudo systemctl disable ollama",
            "sudo rm /etc/systemd/system/ollama.service",
            "sudo rm $(which ollama)",
            "sudo rm -rf /usr/share/ollama",
            "sudo userdel ollama",
            "sudo groupdel ollama"
        ]
        return commands

    async def transition_to_sovereign(self):
        """Switch the system config to use internal inference."""
        if await self.check_readiness() == "TOTAL_SOVEREIGNTY":
            logger.info("Switching MECOS to Sovereign Inference Mode.")
            # Update config logic here
            return True
        return False
