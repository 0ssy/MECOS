import json
import re
import ast
from pathlib import Path
from loguru import logger

from config import settings
from memory_system import MemorySystem
from mecos_llm import get_mecos_llm


def clean_json_string(json_str: str) -> str:
    """Remove comments and clean JSON string before parsing."""

    # Remove // single-line comments
    json_str = re.sub(r'//.*?$', '', json_str, flags=re.MULTILINE)

    # Remove /* multi-line comments */
    json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)

    # Remove trailing commas before } or ]
    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

    return json_str.strip()


class Reasoner:

    MAX_RETRIES = 3

    def __init__(self, memory_system: MemorySystem):

        self.memory = memory_system
        self.llm = get_mecos_llm()

        # Plan persistence
        self.plan_dir = Path("data/plans")
        self.plan_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Reasoner initialized with custom MECOS LLM.")

    def _build_fallback_plan(self, goal: str, reason: str) -> list:
        logger.warning(f"Using fallback plan: {reason}")
        fallback_content = (
            f"MECOS fallback plan generated.\n"
            f"Goal: {goal}\n"
            f"Reason: {reason}\n"
        )
        return [
            {
                "step": 1,
                "objective": "Persist user goal for recovery",
                "tool": "file_write",
                "args": {
                    "path": "plans/fallback_goal.txt",
                    "content": fallback_content
                },
                "state": "pending",
                "reflection": None,
                "result": None,
                "retries": 0,
            },
            {
                "step": 2,
                "objective": "Collect current system telemetry",
                "tool": "system_info",
                "args": {},
                "state": "pending",
                "reflection": None,
                "result": None,
                "retries": 0,
            },
            {
                "step": 3,
                "objective": "List current data workspace files",
                "tool": "file_list",
                "args": {"path": ".", "pattern": "*"},
                "state": "pending",
                "reflection": None,
                "result": None,
                "retries": 0,
            },
        ]

    # =========================================================
    # PLAN PERSISTENCE
    # =========================================================

    def save_plan(self, plan, filename="active_plan.json"):

        try:

            path = self.plan_dir / filename

            with open(path, "w", encoding="utf-8") as f:
                json.dump(plan, f, indent=2)

            logger.info(f"Plan saved: {path}")

        except Exception as e:
            logger.error(f"Failed to save plan: {e}")

    def load_plan(self, filename="active_plan.json"):

        try:

            path = self.plan_dir / filename

            if not path.exists():
                return []

            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

        except Exception as e:

            logger.error(f"Failed to load plan: {e}")
            return []

    # =========================================================
    # PLAN GENERATION
    # =========================================================

    async def generate_plan(self, goal: str):

        try:

            # ---------------------------------------------
            # Retrieve memory context
            # ---------------------------------------------

            context_results = await self.memory.retrieve_context(goal)

            docs = context_results.get("documents", [[]])

            context_str = "\n".join(docs[0]) if docs else ""

            # ---------------------------------------------
            # Planning prompt
            # ---------------------------------------------

            prompt = f"""
You are the reasoning core of MECOS.

GOAL:
{goal}

RELEVANT MEMORY:
{context_str}

AVAILABLE TOOLS:
- terminal_command(command: str)
- file_write(path: str, content: str)
- file_read(path: str)
- execute_python(code: str)

TASK:
Create a sequential execution plan.

RULES:
1. Return ONLY JSON
2. No markdown
3. No explanations
4. Use this schema:

{{
    "plan": [
        {{
            "step": 1,
            "objective": "description",
            "tool": "tool_name",
            "args": {{}}
        }}
    ]
}}
"""

            # ---------------------------------------------
            # LLM inference
            # ---------------------------------------------

            result = await self.llm.think_and_act(
                prompt,
                system_prompt="You are the MECOS Reasoning Core."
            )

            try:

                self.llm.save_experience(
                    prompt,
                    result.get("monologue", ""),
                    result.get("response", "")
                )

            except Exception as e:
                logger.warning(f"Failed saving cognition trace: {e}")

            content = result.get("response", "")

            if not content:

                logger.warning("LLM returned empty response.")
                fallback_plan = self._build_fallback_plan(goal, "llm_empty_response")
                self.save_plan(fallback_plan)
                return fallback_plan

            # ---------------------------------------------
            # Extract JSON
            # ---------------------------------------------

            match = re.search(r"\{.*\}", content, re.DOTALL)

            if not match:

                logger.error("No JSON found in response.")
                fallback_plan = self._build_fallback_plan(goal, "no_json_in_llm_response")
                self.save_plan(fallback_plan)
                return fallback_plan

            json_str = match.group()

            json_str = re.sub(r"```json|```", "", json_str).strip()

            json_str = re.sub(
                r",\s*([\]}])",
                r"\1",
                json_str
            )

            # ---------------------------------------------
            # Parse JSON
            # ---------------------------------------------

            try:

                plan_data = json.loads(json_str)

            except json.JSONDecodeError as e:
                logger.warning(f"Strict JSON parse failed: {e}. Trying tolerant parser...")
                cleaned = clean_json_string(json_str)
                try:
                    plan_data = ast.literal_eval(cleaned)
                except (ValueError, SyntaxError) as fallback_error:

                    logger.error(f"Plan parse failed after fallback: {fallback_error}")

                    logger.debug(f"RAW JSON:\n{json_str}")

                    fallback_plan = self._build_fallback_plan(goal, "json_parse_failure")
                    self.save_plan(fallback_plan)
                    return fallback_plan

            # ---------------------------------------------
            # Extract plan
            # ---------------------------------------------

            raw_plan = []

            if isinstance(plan_data, dict):

                raw_plan = (
                    plan_data.get("plan")
                    or plan_data.get("actions")
                    or []
                )

            elif isinstance(plan_data, list):

                raw_plan = plan_data

            validated_plan = []

            for step in raw_plan:

                if not isinstance(step, dict):
                    continue

                validated_plan.append({

                    "step": step.get(
                        "step",
                        len(validated_plan) + 1
                    ),

                    "objective": step.get(
                        "objective",
                        "undefined"
                    ),

                    "tool": step.get("tool", ""),

                    "args": step.get("args", {}),

                    # Task lifecycle
                    "state": "pending",

                    # Reflection memory
                    "reflection": None,

                    # Execution output
                    "result": None,

                    # Retry counter
                    "retries": 0
                })

            logger.info(
                f"Generated plan with "
                f"{len(validated_plan)} steps."
            )

            if not validated_plan:
                fallback_plan = self._build_fallback_plan(goal, "empty_validated_plan")
                self.save_plan(fallback_plan)
                return fallback_plan

            # Save immediately
            self.save_plan(validated_plan)

            return validated_plan

        except Exception as e:

            logger.exception(
                f"Failed to generate plan: {e}"
            )

            return []

    # =========================================================
    # REFLECTION ENGINE
    # =========================================================

    async def reflect(
        self,
        goal: str,
        plan: list,
        results: list
    ):

        try:

            reflection_prompt = f"""
GOAL:
{goal}

EXECUTED PLAN:
{json.dumps(plan, indent=2)}

RESULTS:
{json.dumps(results, indent=2)}

Analyze:
1. What worked?
2. What failed?
3. What should improve?
4. What should MECOS remember?

Return concise operational lessons.
"""

            result = await self.llm.think_and_act(
                reflection_prompt,
                system_prompt=(
                    "You are the MECOS Reflection Engine."
                )
            )

            lesson = result.get("response", "")

            if lesson:

                await self.memory.add_experience(
                    f"REFLECTION LESSON:\n{lesson}",
                    source="reflection_engine"
                )

                logger.info(
                    "Reflection stored successfully."
                )

            return lesson

        except Exception as e:

            logger.exception(
                f"Reflection failed: {e}"
            )

            return ""

    # =========================================================
    # AUTONOMOUS EXECUTION LOOP
    # =========================================================

    async def execute_plan(
        self,
        goal: str,
        plan: list,
        action_engine
    ):

        try:

            for task in plan:

                # Skip completed tasks
                if task["state"] == "complete":
                    continue

                logger.info(
                    f"Executing Step "
                    f"{task['step']}: "
                    f"{task['objective']}"
                )

                try:

                    task["state"] = "running"

                    # ---------------------------------
                    # Execute tool action
                    # ---------------------------------

                    result = await action_engine.execute(task)

                    task["result"] = result

                    # ---------------------------------
                    # Store execution memory
                    # ---------------------------------

                    await self.memory.add_experience(
                        f"""
TASK:
{task['objective']}

RESULT:
{result}
""",
                        source="execution_engine"
                    )

                    # ---------------------------------
                    # Reflection phase
                    # ---------------------------------

                    task["state"] = "reflecting"

                    lesson = await self.reflect(
                        goal,
                        [task],
                        [result]
                    )

                    # ---------------------------------
                    # Reflection gate
                    # ---------------------------------

                    if lesson:

                        task["reflection"] = lesson

                        task["state"] = "complete"

                        logger.info(
                            f"Task complete: "
                            f"Step {task['step']}"
                        )

                    else:

                        task["state"] = "failed"

                        logger.warning(
                            f"Reflection failed "
                            f"for Step {task['step']}"
                        )

                    # ---------------------------------
                    # Persist updated plan
                    # ---------------------------------

                    self.save_plan(plan)

                except Exception as e:

                    logger.exception(
                        f"Execution failed for "
                        f"Step {task['step']}: {e}"
                    )

                    task["retries"] += 1

                    if (
                        task["retries"]
                        >= self.MAX_RETRIES
                    ):

                        task["state"] = "failed"

                        logger.error(
                            f"Task permanently failed: "
                            f"Step {task['step']}"
                        )

                    else:

                        task["state"] = "pending"

                        logger.warning(
                            f"Retrying Step "
                            f"{task['step']} "
                            f"({task['retries']}/"
                            f"{self.MAX_RETRIES})"
                        )

                    self.save_plan(plan)

            logger.info(
                "Plan execution completed."
            )

        except Exception as e:

            logger.exception(
                f"Autonomous execution loop failed: {e}"
            )
