"""
MECOS LLM Inference Engine
Handles the 'Internal Monologue' and 'Final Response' cognitive cycle.
Optimized to use the remote Server Laptop for inference.
"""

import json
import time
from loguru import logger
from openai import OpenAI
from config import settings

class MECOSLLM:
    def __init__(self):
        # Connect to the remote server laptop (Ollama)
        # It uses the SERVER_IP you set in config.py
        self.client = OpenAI(base_url=settings.LOCAL_LLM_URL, api_key="local-no-key")
        self.model = settings.DEFAULT_MODEL
        logger.info(f"MECOS LLM connected to remote brain at {settings.LOCAL_LLM_URL}")

    async def think_and_act(self, prompt: str, system_prompt: str = "You are the MECOS AI."):
        """
        The core cognitive cycle:
        1. Generate Internal Monologue (Thinking)
        2. Generate Final Response (Acting)
        """
        start_time = time.time()
        
        # Step 1: Internal Monologue
        thinking_prompt = f"{prompt}\n\n[INTERNAL MONOLOGUE]: Think step-by-step about how to solve this."
        
        logger.info("MECOS LLM is thinking (generating internal monologue)...")
        try:
            thought_response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": thinking_prompt}
                ]
            )
            monologue = thought_response.choices[0].message.content
            
            # Step 2: Final Response
            final_prompt = f"{prompt}\n\n[MY THOUGHTS]: {monologue}\n\n[FINAL RESPONSE]:"
            
            logger.info("MECOS LLM is generating final response...")
            final_response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": final_prompt}
                ]
            )
            response = final_response.choices[0].message.content
            
            # Log the experience for future fine-tuning
            self.save_experience(prompt, monologue, response)
            
            duration = time.time() - start_time
            logger.info(f"MECOS LLM cycle complete in {duration:.2f}s")
            
            return {
                "monologue": monologue,
                "response": response,
                "stats": {
                    "duration": duration,
                    "model": self.model
                }
            }
        except Exception as e:
            logger.error(f"Inference failed: {e}")
            return {
                "monologue": "Error in thinking.",
                "response": f"Error: {e}",
                "stats": {"duration": 0, "model": self.model}
            }

    def save_experience(self, prompt: str, monologue: str, response: str):
        """Save the thought process to a file for future fine-tuning."""
        log_file = settings.DATA_DIR / "llm_experiences.jsonl"
        experience = {
            "timestamp": time.time(),
            "prompt": prompt,
            "monologue": monologue,
            "response": response
        }
        with open(log_file, "a") as f:
            f.write(json.dumps(experience) + "\n")
        logger.info("MECOS LLM experience saved for self-training.")

# Singleton instance
mecos_llm = None

def get_mecos_llm():
    global mecos_llm
    if mecos_llm is None:
        mecos_llm = MECOSLLM()
    return mecos_llm
