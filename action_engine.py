"""
MECOS Phase 4 - Action Execution Engine
Executes structured plans step-by-step with retry logic, error handling,
action logging, and success/failure feedback to the reasoning layer.
"""

import asyncio
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from tool_orchestrator import ToolOrchestrator
from memory_system import MemorySystem


class ActionExecutionEngine:
    """
    Executes structured plans produced by the Reasoner.
    Each plan is a list of steps: [{"tool": "...", "args": {...}}, ...]
    
    Features:
    - Step-by-step execution with error detection
    - Retry logic for transient failures
    - Full audit trail stored in memory
    - Early halt on critical errors
    - Execution summary generation
    """

    MAX_RETRIES = 2

    def __init__(self, orchestrator: ToolOrchestrator, memory: MemorySystem):
        self.orchestrator = orchestrator
        self.memory = memory
        logger.info("ActionExecutionEngine initialized.")

    async def execute_plan(self, plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Execute a list of plan steps sequentially.
        Returns a list of result records for each step.
        """
        results = []
        total = len(plan)
        logger.info(f"Starting execution of plan with {total} steps.")

        for i, step in enumerate(plan, start=1):
            tool_name = step.get("tool", "")
            args = step.get("args", {})

            if not tool_name:
                logger.warning(f"Step {i}: Missing tool name, skipping.")
                continue

            logger.info(f"Step {i}/{total}: Executing '{tool_name}'")
            result_text = await self._execute_with_retry(tool_name, args)

            # Determine success
            is_error = isinstance(result_text, str) and (
                result_text.startswith("Error") or
                result_text.startswith("Unknown tool") or
                result_text.startswith("Tool argument error") or
                result_text.startswith("Tool execution error")
            )

            record = {
                "step": i,
                "tool": tool_name,
                "args": args,
                "result": result_text,
                "success": not is_error,
                "timestamp": datetime.now().isoformat(),
            }
            results.append(record)

            # Store in memory
            await self.memory.add_experience(
                f"ACTION EXECUTED: {tool_name}\nARGS: {json.dumps(args)}\nRESULT: {result_text[:500]}",
                source="action_execution",
            )

            if is_error:
                logger.error(f"Plan execution halted at step {i} due to error: {result_text[:200]}")
                break

        # Generate and store execution summary
        await self._store_summary(plan, results)
        return results

    async def _execute_with_retry(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Execute a tool with retry logic for transient failures."""
        last_error = ""
        for attempt in range(1, self.MAX_RETRIES + 2):
            try:
                result = await self.orchestrator.run_tool(tool_name, **args)
                if not (isinstance(result, str) and result.startswith("Error")):
                    return result
                last_error = result
                if attempt <= self.MAX_RETRIES:
                    logger.warning(f"Retry {attempt}/{self.MAX_RETRIES} for '{tool_name}'")
                    await asyncio.sleep(1)
            except Exception as e:
                last_error = f"Exception: {e}"
                logger.error(f"Exception in tool '{tool_name}' (attempt {attempt}): {e}")
                if attempt <= self.MAX_RETRIES:
                    await asyncio.sleep(1)
        return last_error

    async def _store_summary(self, plan: List[Dict], results: List[Dict]):
        """Store a concise execution summary in memory."""
        total = len(plan)
        succeeded = sum(1 for r in results if r.get("success"))
        failed = len(results) - succeeded
        skipped = total - len(results)

        summary = (
            f"EXECUTION SUMMARY: {succeeded}/{total} steps succeeded, "
            f"{failed} failed, {skipped} skipped."
        )
        logger.info(summary)
        await self.memory.add_experience(summary, source="action_execution")

    async def execute_single(self, tool_name: str, **kwargs) -> str:
        """Execute a single tool call outside of a plan context."""
        logger.info(f"Single tool execution: {tool_name}")
        result = await self._execute_with_retry(tool_name, kwargs)
        await self.memory.add_experience(
            f"SINGLE ACTION: {tool_name}\nARGS: {json.dumps(kwargs)}\nRESULT: {result[:500]}",
            source="action_execution",
        )
        return result
