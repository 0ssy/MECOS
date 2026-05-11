"""
MECOS Phase 5 - Agent Coordinator
Multi-agent communication protocol, task routing, consensus mechanisms,
inter-agent memory sharing, and collaborative problem solving.
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
from loguru import logger

from memory_system import MemorySystem
from openai import OpenAI
from config import settings


class AgentRole(Enum):
    TRADING = "trading"
    CODING = "coding"
    RESEARCH = "research"
    PLANNING = "planning"
    REFLECTION = "reflection"
    SAFETY = "safety"


class AgentMessage:
    """A message passed between agents."""

    def __init__(self, sender: str, recipient: str, content: str, msg_type: str = "info"):
        self.sender = sender
        self.recipient = recipient
        self.content = content
        self.msg_type = msg_type  # info | request | response | vote
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, str]:
        return {
            "sender": self.sender,
            "recipient": self.recipient,
            "content": self.content,
            "type": self.msg_type,
            "timestamp": self.timestamp,
        }


class AgentCoordinator:
    """
    Coordinates multiple specialized agents.
    Routes tasks to appropriate agents, facilitates inter-agent debate,
    builds consensus, and manages collaborative problem solving.
    """

    def __init__(self, memory: MemorySystem):
        self.memory = memory
        self.client = OpenAI(base_url=settings.LOCAL_LLM_URL, api_key="local-no-key")
        self._agents: Dict[str, Any] = {}
        self._message_log: List[AgentMessage] = []
        logger.info("AgentCoordinator initialized.")

    def register_agent(self, name: str, agent: Any, role: AgentRole):
        """Register a specialized agent with the coordinator."""
        self._agents[name] = {"agent": agent, "role": role}
        logger.info(f"Agent registered: {name} ({role.value})")

    def _classify_task(self, task: str) -> str:
        """Classify a task to determine which agent(s) should handle it."""
        task_lower = task.lower()

        keywords = {
            "trading": ["trade", "market", "price", "stock", "crypto", "bitcoin", "rsi", "macd", "invest", "portfolio"],
            "coding": ["code", "program", "function", "debug", "test", "script", "python", "javascript", "bug", "implement"],
            "research": ["research", "find", "search", "analyze", "summarize", "report", "information", "study", "learn"],
        }

        scores = {role: 0 for role in keywords}
        for role, kws in keywords.items():
            for kw in kws:
                if kw in task_lower:
                    scores[role] += 1

        best_role = max(scores, key=scores.get)
        if scores[best_role] == 0:
            return "research"  # Default to research for unknown tasks
        return best_role

    async def route_task(self, task: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Route a task to the most appropriate agent and return the result.
        """
        role = self._classify_task(task)
        logger.info(f"Task routed to: {role} agent — '{task[:60]}'")

        agent_info = self._agents.get(role)
        if not agent_info:
            return {"role": role, "result": f"No agent registered for role: {role}", "success": False}

        agent = agent_info["agent"]
        result = None

        try:
            if role == "research":
                result = await agent.deep_research(task)
            elif role == "coding":
                result = await agent.generate_code(task)
            elif role == "trading":
                result = f"Trading analysis requested: {task}. Provide market data for full analysis."
            else:
                result = f"Task acknowledged by {role} agent."

            await self.memory.add_experience(
                f"AGENT TASK [{role}]: {task[:100]}\nResult: {str(result)[:200]}",
                source="agent_coordinator",
            )
            return {"role": role, "result": result, "success": True}

        except Exception as e:
            logger.error(f"Agent '{role}' failed on task: {e}")
            return {"role": role, "result": str(e), "success": False}

    async def multi_agent_debate(self, problem: str, agents_to_consult: Optional[List[str]] = None) -> str:
        """
        Facilitate a multi-agent debate to solve a complex problem.
        Each agent provides its perspective, then consensus is reached.
        """
        logger.info(f"Starting multi-agent debate on: '{problem[:60]}'")
        perspectives = []

        consult = agents_to_consult or list(self._agents.keys())

        # Gather perspectives from each agent
        for agent_name in consult:
            agent_info = self._agents.get(agent_name)
            if not agent_info:
                continue

            role = agent_info["role"].value
            prompt = f"""You are the {role} specialist agent in MECOS.
Problem: {problem}

Provide your expert perspective on this problem from a {role} standpoint.
Be specific, actionable, and concise (max 150 words)."""

            try:
                response = self.client.chat.completions.create(
                    model=settings.DEFAULT_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                )
                perspective = response.choices[0].message.content.strip()
                perspectives.append({"agent": agent_name, "role": role, "perspective": perspective})

                msg = AgentMessage(agent_name, "coordinator", perspective, "vote")
                self._message_log.append(msg)
                logger.debug(f"Perspective from {agent_name}: {perspective[:80]}")
            except Exception as e:
                logger.error(f"Failed to get perspective from {agent_name}: {e}")

        if not perspectives:
            return "No agent perspectives gathered."

        # Build consensus
        consensus = await self._build_consensus(problem, perspectives)

        # Store in memory
        await self.memory.add_experience(
            f"MULTI-AGENT DEBATE [{problem[:60]}]:\n"
            f"Agents consulted: {[p['agent'] for p in perspectives]}\n"
            f"Consensus: {consensus[:200]}",
            source="agent_coordinator",
        )
        return consensus

    async def _build_consensus(self, problem: str, perspectives: List[Dict]) -> str:
        """Synthesize multiple agent perspectives into a consensus decision."""
        perspectives_text = "\n\n".join(
            f"[{p['role'].upper()} Agent]: {p['perspective']}"
            for p in perspectives
        )

        prompt = f"""You are the MECOS consensus engine.

Problem: {problem}

Agent perspectives:
{perspectives_text}

Synthesize these perspectives into a unified, actionable recommendation.
Consider all viewpoints and identify the best course of action.
Format as: Decision | Rationale | Action Steps"""

        try:
            response = self.client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Consensus building failed: {e}")
            return "\n".join(f"[{p['role']}]: {p['perspective']}" for p in perspectives)

    async def collaborative_solve(self, goal: str) -> Dict[str, Any]:
        """
        Full collaborative problem-solving pipeline:
        Problem → Multi-agent analysis → Debate → Consensus → Execution plan
        """
        logger.info(f"Collaborative solve: '{goal[:60]}'")

        # Step 1: Route to primary agent
        primary_result = await self.route_task(goal)

        # Step 2: Multi-agent debate if multiple agents available
        consensus = ""
        if len(self._agents) > 1:
            consensus = await self.multi_agent_debate(goal)

        # Step 3: Generate execution plan
        plan_prompt = f"""Based on this analysis, create a concrete execution plan.

Goal: {goal}
Primary analysis: {primary_result.get('result', '')[:300]}
Consensus: {consensus[:300]}

Return a JSON object with key "plan" containing a list of steps.
Each step: {{"tool": "tool_name", "args": {{...}}}}
Available tools: terminal_command, file_write, file_read, execute_python, web_fetch"""

        try:
            response = self.client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[{"role": "user", "content": plan_prompt}],
                response_format={"type": "json_object"},
            )
            plan_data = json.loads(response.choices[0].message.content)
            plan = plan_data.get("plan", plan_data.get("steps", []))
        except Exception as e:
            logger.error(f"Plan generation in collaborative solve failed: {e}")
            plan = []

        return {
            "goal": goal,
            "primary_agent": primary_result.get("role"),
            "primary_result": primary_result.get("result"),
            "consensus": consensus,
            "execution_plan": plan,
        }

    def get_message_log(self) -> List[Dict]:
        return [m.to_dict() for m in self._message_log[-50:]]

    def get_registered_agents(self) -> List[str]:
        return [f"{name} ({info['role'].value})" for name, info in self._agents.items()]
