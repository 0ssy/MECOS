"""
MECOS Reasoner — Phase 3 cognitive core.

Fixes applied:
  1. think_and_act() is now properly awaited everywhere.
  2. JSON extraction is robust: strips markdown fences (```json ... ```)
     before parsing, so the plan is never silently empty.
  3. save_experience() is now awaited (it became async in mecos_llm fix).
"""

import json
import re
from loguru import logger
from config import settings
from memory_system import MemorySystem
from mecos_llm import get_mecos_llm


# ── JSON extraction helper ────────────────────────────────────────────────────

def _extract_json(text: str) -> dict | list | None:
    """
    Robustly pull JSON out of an LLM response that may be wrapped in:
      - raw JSON
      - ```json ... ``` fences
      - ``` ... ``` fences
      - prose surrounding a JSON block
    Returns parsed object or None on failure.
    """
    if not text:
        return None

    # 1. Strip markdown code fences
    fence_match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    candidate = fence_match.group(1) if fence_match else text

    # 2. Find the outermost { ... } or [ ... ]
    for opener, closer in [('{', '}'), ('[', ']')]:
        start = candidate.find(opener)
        end = candidate.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(candidate[start:end + 1])
            except json.JSONDecodeError:
                continue

    # 3. Last resort: try the whole text
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None


def _extract_plan_list(parsed: dict | list | None) -> list:
    """Pull the action list out of whatever shape the LLM returned."""
    if parsed is None:
        return []
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        # Common keys the LLM might use
        for key in ("plan", "actions", "steps", "tasks"):
            if isinstance(parsed.get(key), list):
                return parsed[key]
        # Any list value
        for v in parsed.values():
            if isinstance(v, list):
                return v
    return []


# ── Reasoner ──────────────────────────────────────────────────────────────────

class Reasoner:
    def __init__(self, memory_system: MemorySystem):
        self.memory = memory_system
        self.llm = get_mecos_llm()
        logger.info("Reasoner initialized.")

    async def generate_plan(self, goal: str) -> list:
        """Generate a structured action plan from a goal."""

        # 1. Retrieve relevant context
        context_results = await self.memory.retrieve_context(goal)
        docs = (context_results.get("documents") or [[]])[0]
        context_str = "\n".join(docs) if docs else "(no prior context)"

        # 2. Build prompt
        prompt = f"""You are the reasoning core of MECOS.

Goal: {goal}

Relevant context from memory:
{context_str}

Available tools:
- terminal_command(command: str)
- file_write(path: str, content: str)

Decompose this goal into a structured plan.
Return ONLY a JSON object with a "plan" key containing a list of actions.
Each action must have "tool" and "args" keys.

Example:
{{
  "plan": [
    {{"tool": "file_write", "args": {{"path": "out.txt", "content": "hello"}}}},
    {{"tool": "terminal_command", "args": {{"command": "ls -la"}}}}
  ]
}}

Return only valid JSON. No prose, no markdown fences."""

        try:
            # FIX: properly await the async method
            result = await self.llm.think_and_act(
                prompt,
                system_prompt="You are the MECOS Reasoning Core. Always respond with valid JSON.",
            )

            # FIX: properly await save_experience
            await self.llm.save_experience(
                prompt, result["monologue"], result["response"]
            )

            # FIX: robust JSON extraction (handles fences + any nesting shape)
            parsed = _extract_json(result["response"])
            plan = _extract_plan_list(parsed)

            if not plan:
                logger.warning(
                    f"Reasoner: could not extract plan from response. "
                    f"Raw: {result['response'][:200]}"
                )

            logger.info(f"Generated plan with {len(plan)} steps.")
            return plan

        except Exception as e:
            logger.error(f"Failed to generate plan: {e}")
            return []

    async def reflect(self, goal: str, plan: list, results: list) -> str:
        """Analyse outcomes and store lessons in memory."""
        reflection_prompt = f"""Goal: {goal}

Executed Plan: {json.dumps(plan)}

Results: {json.dumps(results, default=str)}

What worked? What failed? What should be improved?
Extract a concise lesson (3-5 sentences) for future strategies."""

        try:
            # FIX: properly await
            result = await self.llm.think_and_act(
                reflection_prompt,
                system_prompt="You are the MECOS Reflection Engine.",
            )
            lesson = result["response"]
            await self.memory.add_experience(
                f"REFLECTION LESSON:\n{lesson}", source="reflection"
            )
            logger.info("Reflection stored.")
            return lesson

        except Exception as e:
            logger.error(f"Reflection failed: {e}")
            return ""

