import json
from loguru import logger
from config import settings
from memory_system import MemorySystem
from mecos_llm import get_mecos_llm
import re


class Reasoner:
    def __init__(self, memory_system: MemorySystem):
        self.memory = memory_system
        # Using the custom MECOS LLM for autonomous thinking
        self.llm = get_mecos_llm()
        logger.info("Reasoner initialized with custom MECOS LLM.")

    async def generate_plan(self, goal: str):
        """Generate a structured plan based on a goal and current context."""

        # 1. Retrieve relevant context
        context_results = await self.memory.retrieve_context(goal)
        # Ensure we safely access the first document list
        docs = context_results.get('documents', [[]])
        context_str = "\n".join(docs[0]) if docs else ""

        # 2. Construct prompt
        prompt = f"""
        You are the reasoning core of MECOS (Modular Evolutionary Cognitive Operating System).
        Your goal is: {goal}
        
        Relevant context from memory:
        {context_str}
        
        Available tools:
        - terminal_command(command: str)
        - file_write(path: str, content: str)
        
        Decompose this goal into a structured plan.
        You MUST return a JSON object with a key "plan" that contains a list of actions.
        Each action MUST have a "tool" and "args" key.
        
        Example format:
        {{
            "plan": [
                {{"tool": "file_write", "args": {{"path": "test.txt", "content": "hello"}}}},
                {{"tool": "terminal_command", "args": {{"command": "ls -la"}}}}
            ]
        }}

        CRITICAL: 
        1. Return ONLY the JSON object.
        2. Do NOT include markdown code blocks (```json).
        3. Do NOT include any text before or after the JSON.
        4. Ensure all quotes are standard double quotes.
        """

        try:
            # 3. Get response from LLM
            result = await self.llm.think_and_act(prompt, system_prompt="You are the MECOS Reasoning Core.")
            self.llm.save_experience(prompt, result.get(
                'monologue', ''), result.get('response', ''))

            content = result.get('response', '')

            # 4. Robust JSON extraction using regex
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                json_str = match.group()
                try:
                    plan_data = json.loads(json_str)
                except json.JSONDecodeError:
                    # Strip common markdown artifacts if standard loads fails
                    clean_content = json_str.replace(
                        '```json', '').replace('```', '').strip()
                    plan_data = json.loads(clean_content)
            else:
                plan_data = {}

            # 5. Robustly extract the plan list
            plan = []
            if isinstance(plan_data, dict):
                if "plan" in plan_data and isinstance(plan_data["plan"], list):
                    plan = plan_data["plan"]
                elif "actions" in plan_data and isinstance(plan_data["actions"], list):
                    plan = plan_data["actions"]
                else:
                    # Try to find any list in the dict
                    plan = next((v for v in plan_data.values()
                                if isinstance(v, list)), [])
            elif isinstance(plan_data, list):
                plan = plan_data

            logger.info(f"Generated plan with {len(plan)} steps.")
            return plan

        except Exception as e:
            logger.error(f"Failed to generate plan: {e}")
            return []

    async def reflect(self, goal: str, plan: list, results: list):
        """Analyze the outcome of a plan and extract lessons."""
        reflection_prompt = f"""
        Goal: {goal}
        Executed Plan: {json.dumps(plan)}
        Results: {json.dumps(results)}
        
        What worked? What failed? What should be improved? 
        Extract a concise lesson for future strategies.
        """

        try:
            result = await self.llm.think_and_act(reflection_prompt, system_prompt="You are the MECOS Reflection Engine.")
            lesson = result.get('response', '')
            await self.memory.add_experience(f"REFLECTION LESSON:\n{lesson}", source="reflection_engine")
            logger.info("Reflection completed and stored.")
            return lesson
        except Exception as e:
            logger.error(f"Reflection failed: {e}")
            return ""