"""
MECOS Reasoner — Phase 3 cognitive core. Enhanced with full intelligence layer.

Now uses:
  - KnowledgeGraph for relation lookups
  - CrossDomainInferenceEngine for analogies and cross-domain insight
  - CuriosityEngine to surface gaps in knowledge
  - Richer tool descriptions from ToolOrchestrator
  - Skill-aware planning via skill: prefixed tools
"""

import json
import re
from typing import Any, Dict, List, Optional
from loguru import logger
from config import settings
from memory_system import MemorySystem
from mecos_llm import get_mecos_llm


def _extract_json(text: str) -> Any:
    if not text:
        return None
    fence_match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    candidate = fence_match.group(1) if fence_match else text
    for opener, closer in [("{", "}"), ("[", "]")]:
        start = candidate.find(opener)
        end = candidate.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(candidate[start:end + 1])
            except json.JSONDecodeError:
                continue
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None


def _extract_plan_list(parsed: Any) -> list:
    if parsed is None:
        return []
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        for key in ("plan", "actions", "steps", "tasks"):
            if isinstance(parsed.get(key), list):
                return parsed[key]
        for v in parsed.values():
            if isinstance(v, list):
                return v
    return []


class Reasoner:
    def __init__(self, memory_system: MemorySystem, tool_orchestrator=None, intelligence_stack=None):
        self.memory = memory_system
        self.llm = get_mecos_llm()
        self.tool_orchestrator = tool_orchestrator
        self.intelligence = intelligence_stack or {}
        self.skill_triggers = self._load_skill_triggers()
        logger.info("Reasoner initialized with intelligence layer: {}", list(self.intelligence.keys()))

    def _load_skill_triggers(self) -> Dict[str, List[str]]:
        """Load skill trigger keywords from registered skill tools."""
        triggers = {}
        if self.tool_orchestrator:
            for tool in self.tool_orchestrator.registry.list_tools():
                if tool.name.startswith("skill:"):
                    skill_name = tool.name.replace("skill:", "")
                    triggers[skill_name] = self._extract_triggers(tool.description)
        return triggers

    def _extract_triggers(self, description: str) -> List[str]:
        """Extract trigger keywords from skill description."""
        outreach_patterns = [
            r"outreach", r"email", r"cold.?mail", r"lead", r"sales",
            r"pitch", r"prospect", r"draft", r"send", r"notion",
            r"slack", r"social.?media", r"marketing", r"humanize",
            r"frontend|front.?end", r"seo|search.?optim", r"content",
        ]
        base = re.findall(r"(?:^|\s)(?:marketing|social|legal|humanize|frontend|design|seo|humanizer)[\w-]*", description.lower())
        outreach = re.findall(r"(?:^|\s)(" + "|".join(outreach_patterns) + r")[\w-]*", description.lower())
        return [m.strip() for m in (base + outreach) if m.strip()]

    def _graph_context(self, query: str, max_items: int = 5) -> str:
        kg = self.intelligence.get("knowledge_graph")
        if kg is None:
            return ""
        try:
            relations = kg.get_relations(query)
            if not relations:
                return ""
            lines = []
            for r in relations[:max_items]:
                subj = r.get("subject", "")
                pred = r.get("predicate", "")
                obj = r.get("object", "")
                if pred and subj and obj:
                    lines.append(f"  [{subj}] --[{pred}]--> [{obj}]")
            return "\nKnowledge graph facts:\n" + "\n".join(lines) if lines else ""
        except Exception as exc:
            logger.debug("Graph context failed: {}", exc)
            return ""

    def _curiosity_context(self, query: str, max_items: int = 5) -> str:
        engine = self.intelligence.get("curiosity_engine")
        if engine is None:
            return ""
        try:
            top = engine.top_curiosities(n=max_items)
            if not top:
                return ""
            lines = [f"  curiosity: {q.get('concept', '?')} (priority={q.get('priority', '?')})" for q in top]
            return "\nOpen knowledge gaps:\n" + "\n".join(lines)
        except Exception as exc:
            logger.debug("Curiosity context failed: {}", exc)
            return ""

    def _cross_domain_context(self, query: str) -> str:
        engine = self.intelligence.get("cross_domain_inference")
        if engine is None:
            return ""
        try:
            result = engine.cross_domain_query(query, max_hops=3)
            if not result:
                return ""
            domains = result.get("domains_touched", [])
            insight = result.get("insight", "")
            if domains:
                return f"\nCross-domain insight: spans {', '.join(domains[:5])}\n{insight}"
        except Exception as exc:
            logger.debug("Cross-domain context failed: {}", exc)
        return ""

    def _tool_descriptions(self) -> str:
        orch = self.tool_orchestrator
        if orch is None:
            return "- terminal_command(command: str)\n- file_write(path, content)\n- web_fetch(url)"
        try:
            return orch.describe_tools()
        except Exception:
            return "- (tools unavailable)"

    async def think(self, prompt: str, use_intelligence: bool = True) -> dict:
        context = await self._build_context(prompt, use_intelligence=use_intelligence)
        return await self._call_llm(prompt, context)

    async def generate_plan(self, goal: str) -> list:
        context = await self._build_context(goal)
        prompt = self._build_plan_prompt(goal, context)
        try:
            result = await self.llm.think_and_act(
                prompt,
                system_prompt="You are MECOS, a reasoning agent with access to tools, memory, and cross-domain intelligence. Always respond with valid JSON.",
            )
            await self.llm.save_experience(prompt, result.get("monologue", ""), result.get("response", ""))
            parsed = _extract_json(result.get("response", ""))
            plan = _extract_plan_list(parsed)
            if not plan:
                logger.warning("Reasoner: empty plan from LLM. Raw: {}", result.get("response", "")[:200])
            logger.info("Generated plan with {} steps for goal: {}", len(plan), goal[:80])
            return plan
        except Exception as exc:
            logger.error("Failed to generate plan: {}", exc)
            return []

    async def reflect(self, goal: str, plan: list, results: list) -> str:
        prompt = f"""Goal: {goal}

Executed Plan: {json.dumps(plan)}

Results: {json.dumps(results, default=str)}

What worked? What failed? What should be improved?
Extract a concise lesson (3-5 sentences). Also extract key facts as
  (subject, relation, object) triplets if relevant."""
        try:
            result = await self.llm.think_and_act(
                prompt,
                system_prompt="You are the MECOS Reflection Engine.",
            )
            lesson = result.get("response", "")
            await self.memory.add_experience(
                f"REFLECTION LESSON:\n{lesson}", source="reflection"
            )
            await self._ingest_facts_to_graph(goal, lesson)
            logger.info("Reflection stored.")
            return lesson
        except Exception as exc:
            logger.error("Reflection failed: {}", exc)
            return ""

    async def query_graph(self, concept: str) -> str:
        kg = self.intelligence.get("knowledge_graph")
        if kg is None:
            return "Knowledge graph not available."
        relations = kg.get_relations(concept)
        if not relations:
            return f"No known facts about '{concept}'."
        lines = []
        for r in relations[:15]:
            subj = r.get("subject", concept)
            pred = r.get("predicate", "RELATED_TO")
            obj = r.get("object", "?")
            lines.append(f"  {subj} --[{pred}]--> {obj}")
        return f"Known facts about '{concept}':\n" + "\n".join(lines)

    async def _build_context(self, query: str, use_intelligence: bool = True, n_mem: int = 5) -> str:
        parts = []
        try:
            mem_results = await self.memory.retrieve_context(query, n_results=n_mem)
            docs = (mem_results.get("documents") or [[]])[0]
            if docs:
                parts.append("=== Memory ===\n" + "\n".join(docs))
        except Exception as exc:
            logger.debug("Memory retrieval failed: {}", exc)
        if use_intelligence:
            parts.append(self._graph_context(query))
            parts.append(self._curiosity_context(query))
            parts.append(self._cross_domain_context(query))
        matched_skills = self._match_skills(query)
        if matched_skills:
            parts.append(f"\nMatched skills: {', '.join(matched_skills)}")
            skill_tools = self._skill_tools_context(matched_skills)
            if skill_tools:
                parts.append(f"\nAvailable skill tools:\n{skill_tools}")
        parts = [p for p in parts if p]
        return "\n\n".join(parts) if parts else "(no prior context)"

    def _match_skills(self, query: str) -> List[str]:
        """Match goal query against skill triggers and outreach keywords."""
        query_lower = query.lower()
        matched = []
        outreach_keywords = [
            "outreach", "email", "sales", "lead", "prospect", "cold outreach",
            "send message", "follow up", "notion", "slack", "zapier",
        ]
        for skill_name in self.skill_triggers:
            if skill_name.replace("-", " ") in query_lower or skill_name.replace("-", "") in query_lower:
                matched.append(skill_name)
        for kw in outreach_keywords:
            if kw in query_lower and "outreach" not in matched:
                matched.append("outreach")
                break
        return matched

    def _skill_tools_context(self, skills: List[str]) -> str:
        """Build tool context string for matched skills."""
        if not self.tool_orchestrator:
            return ""
        skill_tools = []
        for t in self.tool_orchestrator.registry.list_tools():
            for skill in skills:
                if f"skill:{skill}" in t.name:
                    skill_tools.append(f"  - {t.name}: {t.description}")
        return "\n".join(skill_tools) if skill_tools else ""

    async def invoke_skill(self, skill_name: str, query: str, args: Optional[Dict] = None) -> str:
        """Invoke a registered skill tool and return result."""
        tool_name = f"skill:{skill_name}"
        spec = self.tool_orchestrator.registry.get(tool_name) if self.tool_orchestrator else None
        if spec is None:
            return f"Skill '{skill_name}' not available"
        try:
            result = await spec.func(query=query, args=args or {})
            await self.memory.add_experience(
                f"SKILL INVOKED: {skill_name} for '{query[:60]}'",
                source="reasoner",
            )
            return str(result)
        except Exception as e:
            logger.error(f"Skill invocation failed: {e}")
            return f"Skill error: {e}"

    def _build_plan_prompt(self, goal: str, context: str) -> str:
        tools_desc = self._tool_descriptions()
        return f"""You are the reasoning core of MECOS with access to a knowledge graph,
curiosity engine, and cross-domain inference. Use all available context.

Goal: {goal}

Context:
{context}

{tools_desc}

Decompose this goal into a structured plan. Return ONLY a JSON object with a
"plan" key containing a list of actions. Each action must have "tool" and
"args" keys. Use the richest tools available (web_perception, agent_reach,
browser_navigate, terminal_command, execute_python, file_write, etc).
When a skill is matched, prefer using skill:skill-name with query and args.

{{
  "plan": [
    {{"tool": "skill:legal-workflow", "args": {{"query": "review contract"}}}},
    {{"tool": "skill:humanizer", "args": {{"query": "polish", "args": {{"text": "..."}}}}}},
    {{"tool": "file_write", "args": {{"path": "report.md", "content": "# Summary"}}}}
  ]
}}

Return only valid JSON. No prose."""

    async def _call_llm(self, prompt: str, context: str) -> dict:
        full_prompt = f"{context}\n\nUser request: {prompt}"
        result = await self.llm.think_and_act(
            full_prompt,
            system_prompt="You are MECOS. Use context from memory, knowledge graph, and cross-domain inference to give grounded answers.",
        )
        return {
            "response": result.get("response", ""),
            "monologue": result.get("monologue", ""),
            "context_used": context[:500],
        }

    async def _ingest_facts_to_graph(self, goal: str, lesson: str):
        kg = self.intelligence.get("knowledge_graph")
        if kg is None:
            return
        try:
            prompt = f"Extract 3-5 key facts from this reflection as (subject, relation, object) triplets.\nReflection:\n{lesson}\nReturn as JSON array of [subject, relation, object]."
            result = await self.llm.think_and_act(prompt, system_prompt="Extract structured triplets only.")
            parsed = _extract_json(result.get("response", ""))
            if isinstance(parsed, list):
                for triplet in parsed[:5]:
                    if isinstance(triplet, (list, tuple)) and len(triplet) == 3:
                        kg.add_triplet(triplet[0], triplet[1], triplet[2], source="reflection")
                kg.save()
        except Exception as exc:
            logger.debug("Fact ingestion failed: {}", exc)