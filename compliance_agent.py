"""
MECOS Compliance Agent
Legal document analysis, contract review, and compliance tools.
Integrates with legal-workflow skill for contract checking and compliance.
"""

import re
from typing import Dict, List, Any, Optional
from loguru import logger

from memory_system import MemorySystem
from tool_orchestrator import ToolOrchestrator
from openai import OpenAI
from config import settings


class ComplianceAgent:
    """
    Handles legal document review, contract analysis, and compliance checking.
    Uses legal-workflow skill for document operations.
    """

    def __init__(self, memory: MemorySystem, orchestrator: ToolOrchestrator):
        self.memory = memory
        self.orchestrator = orchestrator
        self.client = OpenAI(base_url=settings.LOCAL_LLM_URL, api_key="local-no-key")
        logger.info("ComplianceAgent initialized with legal-workflow skill.")

    async def review_document(self, document_path: str, checklist: str = "standard") -> Dict[str, Any]:
        """Review a legal document against a compliance checklist."""
        logger.info(f"Reviewing document: {document_path} with {checklist} checklist")

        # Read document
        content = await self.orchestrator.run_tool("file_read", path=document_path)

        # Run skill invocation
        skill_result = await self.orchestrator.run_tool(
            "skill:legal-workflow",
            query="review",
            args={"file": document_path, "checklist": checklist}
        )

        # Analyze with LLM
        prompt = f"""You are a legal compliance expert reviewing this document.
Checklist: {checklist}
Document content (first 3000 chars):
{content[:3000]}

Provide:
1. Key clauses identified
2. Potential compliance issues
3. Risk level (low/medium/high)
4. Recommendations"""

        try:
            response = self.client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            analysis = response.choices[0].message.content

            await self.memory.add_experience(
                f"LEGAL REVIEW: {document_path} - Risk: {self._extract_risk(analysis)}",
                source="compliance_agent",
            )
            return {"document": document_path, "analysis": analysis, "risk_level": self._extract_risk(analysis)}
        except Exception as e:
            logger.error(f"Document review failed: {e}")
            return {"document": document_path, "error": str(e)}

    def _extract_risk(self, text: str) -> str:
        """Extract risk level from analysis text."""
        text_lower = text.lower()
        if "high" in text_lower:
            return "high"
        if "medium" in text_lower:
            return "medium"
        return "low"

    async def extract_clauses(self, document_path: str, clause_type: str = "all") -> List[str]:
        """Extract specific clauses from a legal document."""
        result = await self.orchestrator.run_tool(
            "skill:legal-workflow",
            query="extract-clauses",
            args={"document": document_path, "type": clause_type}
        )
        return str(result) if result else []

    async def compliance_check(self, document_path: str, jurisdiction: str = "us") -> Dict[str, Any]:
        """Check document compliance against jurisdiction rules."""
        result = await self.orchestrator.run_tool(
            "skill:legal-workflow",
            query="compliance-check",
            args={"jurisdiction": jurisdiction, "document": document_path}
        )
        return {"document": document_path, "result": result}

    async def risk_assess(self, contract_path: str, level: str = "medium") -> Dict[str, Any]:
        """Perform risk assessment on a contract."""
        result = await self.orchestrator.run_tool(
            "skill:legal-workflow",
            query="risk-assess",
            args={"contract": contract_path, "level": level}
        )
        return {"contract": contract_path, "risk_assessment": result}

    async def analyze_legal(self, query: str) -> str:
        """General legal analysis and Q&A."""
        prompt = f"""You are a legal research assistant. Answer the following query based on general legal principles.
Query: {query}

Provide concise, actionable information. If this involves specific legal advice, note that a qualified attorney should be consulted."""

        try:
            response = self.client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            answer = response.choices[0].message.content
            await self.memory.add_experience(
                f"LEGAL ANALYSIS: {query[:100]}",
                source="compliance_agent",
            )
            return answer
        except Exception as e:
            return f"Legal analysis failed: {e}"

    async def run_cycle(self) -> Dict[str, Any]:
        """Run compliance check cycle."""
        return {"status": "ready", "tools": ["review_document", "extract_clauses", "compliance_check", "risk_assess"]}