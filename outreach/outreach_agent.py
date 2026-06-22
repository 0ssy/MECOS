"""
MECOS Outreach - Outreach Agent
Coordinates scanner, synthesizer, delivery agent, and funnel builder
into a single pipeline that runs in the cognition loop.
"""
from __future__ import annotations

import asyncio
import os
from typing import List, Optional

from loguru import logger
from config import settings
from memory_system import MemorySystem
from outreach.scanner import OutreachScanner
from outreach.synthesizer import LeadSynthesizer
from outreach.delivery_agent import DeliveryAgent
from outreach.funnel_builder import FunnelBuilder
from outreach.revenue_ledger import RevenueLedger


class OutreachAgent:
    def __init__(self, memory: MemorySystem):
        self.memory = memory
        self.enabled = os.getenv("MECOS_ENABLE_OUTREACH", "false").strip().lower() == "true"
        self.scanner = OutreachScanner(memory=memory)
        self.synthesizer = LeadSynthesizer(memory=memory)
        self.delivery_agent = DeliveryAgent()
        self.funnel_builder = FunnelBuilder()
        self.revenue_ledger = RevenueLedger()
        self.cycle = 0

    async def startup(self):
        if not self.enabled:
            logger.info("Outreach agent disabled (MECOS_ENABLE_OUTREACH != 'true')")
            return
        await self.scanner.startup()
        logger.info("Outreach agent started.")

    async def shutdown(self):
        if not self.enabled:
            return
        await self.scanner.shutdown()
        self.revenue_ledger._save()
        logger.info("Outreach agent shut down.")

    async def run_cycle(self) -> dict:
        if not self.enabled:
            return {"outreach_status": "disabled"}

        self.cycle += 1
        result = {"outreach_status": "ok", "cycle": self.cycle}

        try:
            if self.cycle % 3 == 1:
                scan_result = await self._run_scan_cycle()
                result["scan"] = scan_result

            if self.cycle % 5 == 2:
                synth_result = await self._run_synth_cycle()
                result["synth"] = synth_result

            if self.cycle % 7 == 4:
                draft_result = await self._run_draft_cycle()
                result["drafts"] = draft_result

            if self.cycle % 11 == 6:
                content_result = await self._run_content_cycle()
                result["content"] = content_result

            if self.cycle % 13 == 0:
                ledger_summary = self.revenue_ledger.get_summary()
                result["revenue"] = ledger_summary
                logger.info(
                    "Revenue summary: total=${:.2f} | ops=${:.2f} | trading=${:.2f} | growth=${:.2f}".format(
                        ledger_summary["total_revenue"],
                        ledger_summary["bucket_balances"]["ops_hardware"]["balance"],
                        ledger_summary["bucket_balances"]["trading_reserve"]["balance"],
                        ledger_summary["bucket_balances"]["growth_profit"]["balance"],
                    )
                )

        except Exception as e:
            logger.error(f"Outreach cycle #{self.cycle} error: {e}")
            result["outreach_status"] = "error"
            result["error"] = str(e)

        return result

    async def _run_scan_cycle(self) -> dict:
        seed_urls = [
            "https://www.reddit.com/r/automation/new/",
            "https://www.reddit.com/r/smallbusiness/new/",
            "https://www.reddit.com/r/Entrepreneur/new/",
            "https://hn.algolia.com/api/v1/search?query=automation&tags=story&hitsPerPage=15",
            "https://www.indiehackers.com/search?q=automation&type=posts",
        ]
        leads = []
        for url in seed_urls:
            try:
                lead = await self.scanner.scan_url(url)
                if lead:
                    leads.append(lead)
            except Exception as e:
                logger.debug(f"Scan skip {url}: {e}")

        social_leads = []
        for source in ["reddit", "hackernews", "indiehackers"]:
            try:
                items = await self.scanner.scan_social_source(source, query="automation", limit=10)
                social_leads.extend(items)
            except Exception as e:
                logger.debug(f"Social scan skip {source}: {e}")

        total = len(leads) + len(social_leads)
        logger.info(f"Outreach scan: {total} leads found ({len(leads)} URLs + {len(social_leads)} social)")
        return {"urls_scanned": len(seed_urls), "new_leads": total}

    async def _run_synth_cycle(self) -> dict:
        new_leads = self.scanner.get_new_leads(min_score=1, limit=10)
        if not new_leads:
            return {"synthesized": 0}

        briefs = await self.synthesizer.synthesize_batch(new_leads)
        count = len(briefs)
        logger.info(f"Outreach synthesis: {count} leads briefed")
        return {"synthesized": count}

    async def _run_draft_cycle(self) -> dict:
        ready = self.synthesizer.get_ready_for_outreach(limit=5)
        if not ready:
            return {"drafts_created": 0}

        total_drafts = 0
        total_sent = 0
        for brief in ready:
            try:
                drafts = self.delivery_agent.draft_for_lead(brief)
                paths = self.delivery_agent.save_drafts(drafts)
                total_drafts += len(paths)

                for draft in drafts:
                    if draft.get("type") == "email" and draft.get("status") == "pending_send":
                        if self.delivery_agent.send_draft(draft):
                            total_sent += 1
            except Exception as e:
                logger.error(f"Draft generation failed for {brief.get('domain')}: {e}")

        pending = len(self.delivery_agent.list_pending())
        logger.info(f"Outreach drafts: {total_drafts} created, {total_sent} sent, {pending} pending review")
        return {"drafts_created": total_drafts, "drafts_sent": total_sent, "pending_review": pending}

    async def _run_content_cycle(self) -> dict:
        published = self.funnel_builder.get_case_studies(limit=20)
        if not published:
            return {"content_generated": 0, "reason": "no_published_case_studies"}

        draft_contents = []
        for cs in published[-3:]:
            for platform in ["twitter", "linkedin", "reddit"]:
                try:
                    content = self.funnel_builder.generate_social_content(cs, platform)
                    draft_contents.append(content)
                except Exception as e:
                    logger.debug(f"Content gen failed for {cs.get('client')} on {platform}: {e}")

        logger.info(f"Outreach content: {len(draft_contents)} social posts drafted")
        return {"content_generated": len(draft_contents), "platforms": ["twitter", "linkedin", "reddit"]}

    def record_payment(self, deal_id: str, amount: float, source: str = "client_payment",
                       description: str = "") -> dict:
        return self.revenue_ledger.record_payment(deal_id, amount, source, description)

    def get_summary(self) -> dict:
        return {
            "outreach_enabled": self.enabled,
            "revenue": self.revenue_ledger.get_summary(),
            "pending_drafts": len(self.delivery_agent.list_pending()),
            "leads_queued": len(self.synthesizer.get_ready_for_outreach()),
        }
