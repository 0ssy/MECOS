"""
SalesGPT Conversation Adapter for MECOS
Wraps SalesGPT agents to generate conversational emails for leads.
Enables native tool-calling alongside MECOS tools.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from loguru import logger


class SalesConversationAdapter:
    """Bridge between MECOS leads and SalesGPT conversation flow."""

    def __init__(self, tool_orchestrator=None):
        self.orchestrator = tool_orchestrator
        self._sales_agent = None
        self._initialized = False

    def _get_sales_agent(self):
        """Lazy-load SalesGPT agent."""
        if self._initialized:
            return self._sales_agent

        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent / "libs" / "SalesGPT"))
            from salesgpt.agents import SalesGPT
            from salesgpt.salesgptapi import SalesGPTAPI
            self._sales_agent = {
                "SalesGPT": SalesGPT,
                "SalesGPTAPI": SalesGPTAPI,
            }
            self._initialized = True
        except ImportError as e:
            logger.warning(f"SalesGPT not available: {e}")
        return self._sales_agent

    def prepare_lead_context(self, lead_brief: Dict[str, Any]) -> Dict[str, Any]:
        """Map MECOS lead brief to SalesGPT configuration."""
        domain = lead_brief.get("domain", "their company")
        pain_points = lead_brief.get("pain_points", ["manual tasks"])
        package = lead_brief.get("recommended_package", {})

        # SalesGPT config from lead data
        return {
            "salesperson_name": "MECOS Automation Specialist",
            "salesperson_role": "Automation Consultant",
            "company_name": "MECOS Automation",
            "company_business": f"""MECOS Automation builds custom AI agents and workflow bots that eliminate 
manual work. We specialize in browser automation, data pipelines, and scheduled scripts 
that run on autopilot — typically achieving 60%+ time reduction on target processes.""",
            "product_catalog": self._build_product_context(package, pain_points),
            "lead_context": {
                "domain": domain,
                "pain_points": pain_points,
                "current_process": lead_brief.get("current_process", "manual work"),
            },
        }

    def _build_product_context(self, package: Dict, pain_points: List[str]) -> str:
        """Build product catalog context for SalesGPT."""
        if package:
            return f"""MECOS Automation Service:
- {package.get('name', 'Custom Automation Bot')}
- Price Range: {package.get('price_range', '$500-$1,500')}
- Delivery: {package.get('delivery', '1-2 weeks')}
- Description: {package.get('description', 'Custom AI agent for automation')}"""
        return """MECOS Automation Services:
- Browser Automation Bots - Replace manual web tasks with scheduled scripts
- Data Pipeline Agents - Automate data collection and processing
- Workflow Integration - Connect systems with custom connectors
- CRM Automation - Auto-update customer records and follow-ups"""

    async def generate_conversation_turns(self, lead_brief: Dict[str, Any], n_turns: int = 4) -> List[Dict[str, Any]]:
        """Generate SalesGPT conversation turns for a lead.
        
        Returns list of conversation states: stage, thought, message.
        """
        agent_mod = self._get_sales_agent()
        if not agent_mod:
            logger.warning("SalesGPT unavailable, falling back to template")
            return self._fallback_turns(lead_brief, n_turns)

        SalesGPT = agent_mod["SalesGPT"]
        
        config = self.prepare_lead_context(lead_brief)
        
        try:
            # Initialize agent with context
            agent = SalesGPT.from_llm(
                llm=self._get_mecos_llm_wrapper(),
                verbose=False,
                use_tools=False,  # Will use MECOS tools separately
                **config,
            )
            agent.seed_agent()
            
            turns = []
            for i in range(n_turns):
                agent.determine_conversation_stage()
                
                # Build context for this turn
                context = self._build_turn_context(lead_brief, agent.conversation_history)
                
                # Generate message
                response = agent.step()
                msg = response.get("response", "") if isinstance(response, dict) else str(response)
                
                turns.append({
                    "stage": agent.current_stage if hasattr(agent, 'current_stage') else f"turn_{i+1}",
                    "message": msg,
                    "turn": i + 1,
                })
            
            return turns
        except Exception as e:
            logger.error(f"SalesGPT turn generation failed: {e}")
            return self._fallback_turns(lead_brief, n_turns)

    def _build_turn_context(self, lead_brief: Dict, history: List = None) -> Dict:
        """Build context for SalesGPT turn."""
        return {
            "lead": lead_brief,
            "history": history or [],
            "pain_points": lead_brief.get("pain_points", []),
        }

    def _get_mecos_llm_wrapper(self):
        """Wrap MECOS LLM for SalesGPT compatibility."""
        try:
            from mecos_llm import get_mecos_llm
            mecos_llm = get_mecos_llm()
            
            # Create a LangChain-compatible wrapper
            class MECOSLLMWrapper:
                def __init__(self, mecos_llm):
                    self.llm = mecos_llm
                    
                async def agenerate(self, messages: List) -> Any:
                    prompt = "\n".join(m.get("content", "") for m in messages if isinstance(m, dict))
                    resp = await self.llm.think_and_act(prompt)
                    class MockResponse:
                        def __init__(self, content):
                            self.generations = [{"text": content}]
                    return MockResponse(resp.get("response", ""))
                    
            return MECOSLLMWrapper(mecos_llm)
        except Exception:
            return None

    def _fallback_turns(self, lead_brief: Dict, n_turns: int) -> List[Dict]:
        """Generate fallback conversation turns when SalesGPT unavailable."""
        domain = lead_brief.get("domain", "your company")
        pain = lead_brief.get("pain_points", ["manual tasks"])[0].replace("_", " ")
        
        return [
            {
                "stage": "Introduction",
                "message": f"Hi there! This is MECOS Automation — we specialize in building AI agents that eliminate manual work. I noticed {domain} might benefit from automation around {pain}.",
                "turn": 1,
            },
            {
                "stage": "Value Proposition",
                "message": f"Our bots typically achieve 60%+ time reduction on processes like yours. For example, we recently cut a client's data entry from 4 hours/day to just 15 minutes.",
                "turn": 2,
            },
            {
                "stage": "Solution Presentation",
                "message": f"We'd build a custom automation agent for {pain} that runs on your schedule — no daily management needed. Usually ready in 1-2 weeks.",
                "turn": 3,
            },
            {
                "stage": "Close",
                "message": "Would you be interested in a free 15-minute audit to see what's possible? Or just reply 'DEMO' and I'll send a quick Loom showing how it works.",
                "turn": 4,
            },
        ][:n_turns]

    def generate_email_from_turns(self, turns: List[Dict], lead_brief: Dict) -> str:
        """Convert conversation turns to email body."""
        if not turns:
            return "Hello! I'm reaching out from MECOS Automation..."
        
        # Use the first turn as email opening + close from last turn
        body = turns[0]["message"]
        if len(turns) > 1:
            body += "\n\n" + "\n\n".join(t["message"] for t in turns[1:])
        
        return body

    async def draft_sales_email(self, lead_brief: Dict, referral_code: str = "") -> Dict[str, Any]:
        """Generate a sales email using SalesGPT conversation flow."""
        contacts = lead_brief.get("contacts", {})
        emails = contacts.get("emails", [])
        recipient = emails[0] if emails else "unknown@example.com"
        
        domain = lead_brief.get("domain", "your company")
        
        # Generate conversation turns
        turns = await self.generate_conversation_turns(lead_brief)
        body = self.generate_email_from_turns(turns, lead_brief)
        
        # Add referral note
        if referral_code:
            body += f"\n\nP.S. Know someone who'd benefit? Share this link: https://mecos-automation.com/ref/{referral_code.lower()}"
        
        subject = f"Automation for {domain}"
        
        return {
            "type": "email",
            "to": recipient,
            "subject": subject,
            "body": body,
            "lead_brief": lead_brief,
            "referral_code": referral_code,
            "created_at": datetime.now().isoformat(),
            "status": "pending_send",
            "channel": "salesgpt_sales",
            "source": "salesgpt_conversation",
        }