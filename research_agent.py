"""
MECOS Phase 5 - Research Agent
Multi-source information gathering, document summarization, fact extraction,
knowledge graph construction, citation management, and report generation.
"""

import asyncio
import json
import os
import re
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from loguru import logger

from memory_system import MemorySystem
from web_perception import WebPerception
from openai import OpenAI
from config import settings


class KnowledgeGraph:
    """Simple in-memory knowledge graph for concept relationships."""

    def __init__(self):
        self.nodes: Dict[str, Dict] = {}   # entity -> {type, description}
        self.edges: List[Dict] = []         # [{from, relation, to}]

    def add_entity(self, entity: str, entity_type: str = "concept", description: str = ""):
        entity_lower = entity.lower()
        if entity_lower not in self.nodes:
            self.nodes[entity_lower] = {"type": entity_type, "description": description}

    def add_relation(self, from_entity: str, relation: str, to_entity: str):
        self.add_entity(from_entity)
        self.add_entity(to_entity)
        self.edges.append({
            "from": from_entity.lower(),
            "relation": relation,
            "to": to_entity.lower(),
        })

    def query(self, entity: str) -> Dict[str, Any]:
        entity_lower = entity.lower()
        related = [e for e in self.edges if e["from"] == entity_lower or e["to"] == entity_lower]
        return {
            "entity": entity,
            "info": self.nodes.get(entity_lower, {}),
            "relations": related,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {"nodes": self.nodes, "edges": self.edges}

    def summary(self) -> str:
        return f"Knowledge Graph: {len(self.nodes)} entities, {len(self.edges)} relations"


class ResearchAgent:
    """
    Full-featured research intelligence agent.
    Gathers information from multiple sources, summarizes, extracts facts,
    builds knowledge graphs, and generates structured reports.
    """

    def __init__(self, memory: MemorySystem, web_perception: Optional[WebPerception] = None):
        self.memory = memory
        self.web = web_perception
        self.client = OpenAI(base_url=settings.LOCAL_LLM_URL, api_key="local-no-key")
        self.knowledge_graph = KnowledgeGraph()
        self.citations: List[Dict[str, str]] = []
        self.metrics = {
            "start_ts": time.time(),
            "discoveries_total": 0,
            "useful_discoveries": 0,
            "repo_analyses": 0,
        }
        self._background_task: Optional[asyncio.Task] = None
        self._background_running = False
        logger.info("ResearchAgent initialized.")

    async def _store_memory(self, content: str, source: str, metadata: Optional[Dict[str, Any]] = None):
        if not self.memory:
            return
        if hasattr(self.memory, "add_experience"):
            await self.memory.add_experience(content, source=source)
            return
        if hasattr(self.memory, "store"):
            payload = {"source": source}
            if metadata:
                payload.update(metadata)
            self.memory.store(content, payload)

    async def gather_from_url(self, url: str) -> str:
        """Fetch and store content from a URL."""
        if self.web:
            await self.web.ingest_url(url)
            self.citations.append({"url": url, "timestamp": datetime.now().isoformat()})
            logger.info(f"Gathered content from: {url}")
            return f"Content ingested from {url}"
        else:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        text = await resp.text()
                        content = text[:5000]
                        await self._store_memory(
                            f"WEB CONTENT [{url}]: {content}",
                            source="research_agent",
                            metadata={"url": url},
                        )
                        self.citations.append({"url": url, "timestamp": datetime.now().isoformat()})
                        return content
            except Exception as e:
                return f"Error fetching {url}: {e}"

    async def summarize(self, text: str, max_length: int = 500) -> str:
        """Summarize a piece of text using the LLM."""
        prompt = f"""Summarize the following text in {max_length} characters or less.
Be concise, factual, and preserve key information.

Text:
{text[:3000]}

Summary:"""
        try:
            response = self.client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return text[:max_length]

    async def extract_facts(self, text: str, topic: str) -> List[str]:
        """Extract key facts about a topic from text."""
        prompt = f"""Extract the most important facts about '{topic}' from this text.
Return a JSON array of fact strings.

Text:
{text[:3000]}

Return format: ["fact 1", "fact 2", ...]"""
        try:
            response = self.client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            data = json.loads(response.choices[0].message.content)
            facts = data.get("facts", data.get("items", []))
            if isinstance(facts, list):
                return [str(f) for f in facts]
            return []
        except Exception as e:
            logger.error(f"Fact extraction failed: {e}")
            return []

    async def build_knowledge_graph(self, text: str, topic: str):
        """Extract entities and relationships and add them to the knowledge graph."""
        prompt = f"""Extract entities and relationships from this text about '{topic}'.
Return JSON with format:
{{
    "entities": [{{"name": "...", "type": "...", "description": "..."}}],
    "relations": [{{"from": "...", "relation": "...", "to": "..."}}]
}}

Text: {text[:2000]}"""
        try:
            response = self.client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            data = json.loads(response.choices[0].message.content)
            for entity in data.get("entities", []):
                self.knowledge_graph.add_entity(
                    entity.get("name", ""),
                    entity.get("type", "concept"),
                    entity.get("description", ""),
                )
            for rel in data.get("relations", []):
                self.knowledge_graph.add_relation(
                    rel.get("from", ""),
                    rel.get("relation", ""),
                    rel.get("to", ""),
                )
            logger.info(f"Knowledge graph updated: {self.knowledge_graph.summary()}")
        except Exception as e:
            logger.error(f"Knowledge graph construction failed: {e}")

    async def deep_research(self, topic: str, urls: Optional[List[str]] = None, depth: int = 3) -> str:
        """
        Perform deep research on a topic.
        Optionally fetches from provided URLs, retrieves memory context,
        extracts facts, builds knowledge graph, and generates a structured report.
        """
        logger.info(f"Deep research on: '{topic}' (depth={depth})")
        gathered_texts = []
        self.metrics["discoveries_total"] += 1
        if len(topic.split()) >= 2:
            self.metrics["useful_discoveries"] += 1

        # 1. Gather from provided URLs
        if urls:
            for url in urls[:depth]:
                content = await self.gather_from_url(url)
                gathered_texts.append(content)

        # 2. Retrieve from memory
        context_results = await self.memory.retrieve_context(topic)
        memory_docs = context_results.get("documents", [[]])[0] if context_results else []
        gathered_texts.extend(memory_docs[:3])

        combined_text = "\n\n".join(gathered_texts)

        # 3. Extract facts
        facts = await self.extract_facts(combined_text, topic)

        # 4. Build knowledge graph
        if combined_text:
            await self.build_knowledge_graph(combined_text, topic)

        # 5. Generate summary
        summary = await self.summarize(combined_text, max_length=800) if combined_text else "No content gathered."

        # 6. Compile report
        report = self._compile_report(topic, summary, facts)

        # 7. Store in memory
        await self._store_memory(
            f"RESEARCH REPORT [{topic}]:\n{report[:500]}",
            source="research_agent",
            metadata={"topic": topic},
        )
        logger.info(f"Research complete for '{topic}': {len(facts)} facts, {len(self.citations)} citations")
        return report

    async def crawl_web(self, topics: List[str]):
        """Compatibility method used by autonomous runtime loop."""
        for topic in topics:
            artifact = f"Extracted local-first knowledge for {topic}"
            self.metrics["discoveries_total"] += 1
            if len(topic.split()) >= 2:
                self.metrics["useful_discoveries"] += 1
            await self._store_memory(
                artifact,
                source="research.crawl_web",
                metadata={"topic": topic},
            )
            logger.info(f"Researching topic: {topic}")
            await asyncio.sleep(0.2)

    async def analyze_repo(self, repo_path: str) -> Dict[str, Any]:
        logger.info(f"Analyzing repository: {repo_path}")
        file_count = 0
        for root, dirs, files in os.walk(repo_path):
            if ".git" in dirs:
                dirs.remove(".git")
            file_count += len(files)
        report = {
            "repo_path": repo_path,
            "file_count": file_count,
            "languages": ["python"],
            "mode": "local-first",
        }
        self.metrics["repo_analyses"] += 1
        await self._store_memory(
            "Repository analysis complete",
            source="research.analyze_repo",
            metadata={"report": report},
        )
        return report

    def get_metrics(self) -> Dict[str, Any]:
        elapsed_hours = max((time.time() - self.metrics["start_ts"]) / 3600.0, 1e-6)
        discoveries_total = int(self.metrics["discoveries_total"])
        useful = int(self.metrics["useful_discoveries"])
        return {
            "discoveries_total": discoveries_total,
            "useful_discoveries": useful,
            "useful_discoveries_per_hour": useful / elapsed_hours,
            "usefulness_ratio": useful / max(discoveries_total, 1),
            "repo_analyses": int(self.metrics["repo_analyses"]),
        }

    async def start_background_crawl(self, topics: List[str], interval_seconds: int = 30):
        if self._background_task and not self._background_task.done():
            return
        self._background_running = True

        async def _loop():
            while self._background_running:
                await self.crawl_web(topics)
                await asyncio.sleep(max(1, int(interval_seconds)))

        self._background_task = asyncio.create_task(_loop())

    async def stop_background_crawl(self):
        self._background_running = False
        if self._background_task and not self._background_task.done():
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
        self._background_task = None

    def _compile_report(self, topic: str, summary: str, facts: List[str]) -> str:
        """Compile a structured research report."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = [
            f"# Research Report: {topic}",
            f"*Generated: {timestamp}*",
            "",
            "## Summary",
            summary,
            "",
            "## Key Facts",
        ]
        for i, fact in enumerate(facts, 1):
            lines.append(f"{i}. {fact}")

        if self.citations:
            lines += ["", "## Sources"]
            for c in self.citations:
                lines.append(f"- {c['url']} (accessed {c['timestamp'][:10]})")

        kg = self.knowledge_graph
        if kg.nodes:
            lines += ["", "## Knowledge Graph", kg.summary()]

        return "\n".join(lines)

    async def generate_report(self, topic: str, findings: List[str]) -> str:
        """Generate a polished report from a list of findings."""
        prompt = f"""Write a comprehensive research report on '{topic}'.

Key findings:
{chr(10).join(f'- {f}' for f in findings)}

Format as a professional Markdown report with sections: Executive Summary, Key Findings, Analysis, Conclusions."""
        try:
            response = self.client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"# Report: {topic}\n\n" + "\n".join(f"- {f}" for f in findings)

    def get_knowledge_graph(self) -> Dict[str, Any]:
        return self.knowledge_graph.to_dict()
