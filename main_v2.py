"""
MECOS Runtime v2 — local sovereign autonomous intelligence runtime demo.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from loguru import logger

from analyzer import ResearchAgent
from continuous_loop import ContinuousResearchLoop
from engineer import CodingAgent, SandboxExecutor
from knowledge_graph import KnowledgeGraph
from model_router import ModelRouter
from orchestrator import AutonomousOrchestrator
from self_debug import SelfDebugger
from self_improvement import EvolutionAgent
from vector_memory import VectorMemory


async def main():
    logger.info("Starting MECOS Runtime v2 (local-first)")

    memory = VectorMemory()
    graph = KnowledgeGraph()
    research = ResearchAgent(memory_layer=memory)
    sandbox = SandboxExecutor()
    coder = CodingAgent(sandbox)
    debugger = SelfDebugger(sandbox)
    orchestrator = AutonomousOrchestrator()
    evolution = EvolutionAgent(memory_layer=memory)
    router = ModelRouter(main_brain_url="http://192.168.1.88:11434")
    loop = ContinuousResearchLoop(research)

    background = asyncio.create_task(loop.start(["autonomous runtime", "recursive engineering"]))

    await research.analyze_repo(str(Path(__file__).resolve().parent))
    module_code = await coder.build_module("diagnostic_tool", "runtime health checks")
    if module_code:
        await debugger.verify_and_repair(module_code, "diagnostic_tool.py")

    graph.add_node("mecos_core", "runtime", {"mode": "local-first"})
    graph.add_node("sandbox", "component", {"purpose": "safe execution"})
    graph.add_edge("mecos_core", "sandbox", "uses")

    await router.route_request("plan evolution", "long_term_planning")
    await evolution.run_benchmark("coding_agent", {"success_rate": 0.85})
    await orchestrator.run_goal("Evolve MECOS into sovereign autonomous runtime")

    loop.stop()
    background.cancel()
    try:
        await background
    except asyncio.CancelledError:
        pass

    logger.info("MECOS Runtime v2 complete")


if __name__ == "__main__":
    asyncio.run(main())

