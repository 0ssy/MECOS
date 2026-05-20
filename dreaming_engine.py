"""
MECOS Dreaming Engine
Allows MECOS to talk to itself and generate new goals while the user is away.
"""

import random
from loguru import logger
from mecos_llm import get_mecos_llm
from memory_system import MemorySystem

class DreamingEngine:
    def __init__(self, memory: MemorySystem):
        self.memory = memory
        self.llm = get_mecos_llm()
        self.curiosity_topics = ["trading strategies", "code optimization", "security research", "system efficiency"]

    async def generate_self_goal(self):
        """Generate a new goal based on past experiences and curiosity."""
        # 1. Get recent experiences to inspire the 'dream'
        recent_memories = await self.memory.retrieve_context("recent activities")
        mem_str = "\n".join(recent_memories['documents'][0][:5])
        
        topic = random.choice(self.curiosity_topics)
        
        prompt = f"""
        [SYSTEM]: You are in 'Dreaming Mode'. The user is away at work/school.
        [CONTEXT]: Recent activities: {mem_str}
        [CURIOSITY]: You are currently interested in: {topic}
        
        [INTERNAL MONOLOGUE]:
        What is a productive goal I can pursue autonomously? 
        It should be something that improves my own capabilities or provides value to the user.
        
        [FINAL RESPONSE]:
        Generate a single, clear goal for yourself.
        Example: "Research and implement a new RSI-based trading signal."
        """
        
        logger.info("MECOS is dreaming of new goals...")
        result = await self.llm.think_and_act(prompt, system_prompt="You are the MECOS Dreaming Engine.")
        goal = (result.get('response') or "").strip().strip('"')
        if not goal:
            goal = f"Research and improve {topic} for user benefit."
            logger.warning(f"Dream goal fallback activated: {goal}")
        
        logger.info(f"MECOS has set a new autonomous goal: {goal}")
        return goal

    async def self_reflect(self):
        """Deep reflection on internal state during idle time."""
        prompt = "Analyze your own performance over the last 24 hours. What is your biggest weakness?"
        result = await self.llm.think_and_act(prompt, system_prompt="You are the MECOS Self-Reflection Engine.")
        await self.memory.add_experience(f"SELF-REFLECTION: {result['response']}", source="dreaming_engine")
        logger.info("Deep self-reflection completed.")
