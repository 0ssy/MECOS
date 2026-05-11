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
    def __init__(self, memory):
        self.memory = memory
        self.sovereign = SovereignInference()
        self.threshold_experiences = 100 # Number of experiences before suggesting independence

    async def check_readiness(self):
        """Check if MECOS has learned enough to go sovereign."""
        stats = await self.memory.get_stats()
        exp_count = stats.get("experience_count", 0)
        
        logger.info(f"Independence Check: {exp_count}/{self.threshold_experiences} experiences gathered.")
        
        if exp_count >= self.threshold_experiences and not self.sovereign.is_ready():
            logger.info("MECOS is ready for independence, but model weights are missing.")
            return "READY_FOR_WEIGHTS"
        
        if exp_count >= self.threshold_experiences and self.sovereign.is_ready():
            logger.info("MECOS is fully ready for Total Sovereignty.")
            return "TOTAL_SOVEREIGNTY"
            
        return "LEARNING"

    def cleanup_ollama(self):
        """Tool to remove Ollama from the server once sovereign."""
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
