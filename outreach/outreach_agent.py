"""
MECOS Outreach - Outreach Agent
Coordinates scanner, synthesizer, delivery agent, and funnel builder
into a single pipeline that runs in the cognition loop.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from loguru import logger
from config import settings
from memory_system import MemorySystem
from outreach.scanner import OutreachScanner
from outreach.synthesizer import LeadSynthesizer
from outreach.delivery_agent import DeliveryAgent
from outreach.funnel_builder import FunnelBuilder
from outreach.email_enricher import EmailEnricher
from outreach.worldmonitor_adapter import WorldMonitorAdapter
from outreach.ceo_instincts import CeoInstincts
from outreach.revenue_ledger import RevenueLedger
from outreach.payments.payment_ledger import PaymentLedger
from outreach.payments.paypal_client import PayPalClient
from outreach.reply_monitor import ReplyMonitor
from outreach.demo_deliverer import DemoDeliverer
from outreach.followup_engine import FollowupEngine


class OutreachAgent:
    def __init__(self, memory: MemorySystem):
        self.memory = memory
        self.enabled = os.getenv("MECOS_ENABLE_OUTREACH", "false").strip().lower() == "true"
        self.scanner = OutreachScanner(memory=memory)
        self.synthesizer = LeadSynthesizer(memory=memory)
        self.delivery_agent = DeliveryAgent()
        self.funnel_builder = FunnelBuilder()
        self.revenue_ledger = RevenueLedger()
        self.payment_ledger = PaymentLedger()
        self.paypal_client = PayPalClient()
        self.email_enricher = EmailEnricher()
        self.intel_adapter = WorldMonitorAdapter()
        self.instincts = CeoInstincts()
        self.cycle = 0
        self.reply_monitor = ReplyMonitor()
        self.demo_deliverer = DemoDeliverer()
        self.followup_engine = FollowupEngine()

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

            if self.cycle % 4 == 3:
                enrich_result = await self._run_enrich_cycle()
                result["enrich"] = enrich_result

            if self.cycle % 5 == 2:
                synth_result = await self._run_synth_cycle()
                result["synth"] = synth_result

            if self.cycle % 7 == 4:
                draft_result = await self._run_draft_cycle()
                result["drafts"] = draft_result

            reply_result = self._run_reply_check_cycle()
            result["replies"] = reply_result

            if self.cycle % 15 == 0:
                followup_result = self._run_followup_cycle()
                result["followups"] = followup_result

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
            "https://www.reddit.com/r/smallbusiness/new/",
            "https://www.reddit.com/r/Entrepreneur/new/",
            "https://www.reddit.com/r/webdev/new/",
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
                items = await self.scanner.scan_social_source(source, query="automation needed hiring", limit=10)
                social_leads.extend(items)
            except Exception as e:
                logger.debug(f"Social scan skip {source}: {e}")

        searxng_queries = [
            "small business automation needed site:reddit.com",
            "workflow bottleneck startup",
            "manual data entry help",
            "automation tool needed",
        ]
        for query in searxng_queries:
            try:
                found = await self.scanner.search_leads(query, limit=5)
                social_leads.extend(found)
            except Exception as e:
                logger.debug(f"SearXNG search skip {query}: {e}")

        total = len(leads) + len(social_leads)
        logger.info(f"Outreach scan: {total} leads found ({len(leads)} URLs + {len(social_leads)} social)")

        all_new = leads + social_leads

        if all_new:
            enriched_new = await self.email_enricher.enrich_batch(all_new)
            for lead in enriched_new:
                if lead.get("contacts", {}).get("emails"):
                    existing = next((l for l in self.scanner.leads if l.get("url") == lead.get("url")), None)
                    if existing:
                        existing["contacts"] = lead["contacts"]
                    else:
                        self.scanner.leads.append(lead)

        scored = self.intel_adapter.enrich_batch(all_new)
        for lead in scored:
            if lead.get("intel_multiplier", 1.0) != 1.0:
                self.scanner.leads = [l if l.get("url") != lead.get("url") else lead for l in self.scanner.leads]
                self.scanner._save_leads()

        return {"urls_scanned": len(seed_urls), "new_leads": total, "intel_scored": sum(1 for l in scored if l.get("intel_multiplier", 1.0) != 1.0)}

    async def _run_enrich_cycle(self) -> dict:
        unenriched = [l for l in self.scanner.leads if not l.get("contacts", {}).get("emails")]
        if not unenriched:
            return {"enriched": 0, "reason": "all_leads_have_emails"}

        batch = unenriched[:10]
        enriched = await self.email_enricher.enrich_batch(batch)
        
        updated = 0
        for lead in enriched:
            if lead.get("contacts", {}).get("emails"):
                updated += 1
                self.scanner._save_leads()

        logger.info(f"Outreach enrichment: {updated}/{len(batch)} leads got emails")
        return {"enriched": updated, "attempted": len(batch)}

    async def _run_synth_cycle(self) -> dict:
        new_leads = self.scanner.get_new_leads(min_score=1, limit=10)
        if not new_leads:
            return {"synthesized": 0}

        new_leads = [self.instincts.score_lead(l) for l in new_leads]
        new_leads.sort(key=lambda l: l.get("total_score", 0), reverse=True)

        briefs = await self.synthesizer.synthesize_batch(new_leads)
        count = len(briefs)
        logger.info(f"Outreach synthesis: {count} leads briefed (instincts ranked)")
        return {"synthesized": count}

    async def _run_draft_cycle(self) -> dict:
        ready = self.synthesizer.get_ready_for_outreach(limit=5)
        if not ready:
            return {"drafts_created": 0}

        total_drafts = 0
        total_sent = 0
        total_invoiced = 0
        for brief in ready:
            try:
                drafts = self.delivery_agent.draft_for_lead(brief)
                paths = self.delivery_agent.save_drafts(drafts)
                total_drafts += len(paths)

                brief["status"] = "drafted"
                self.synthesizer._save()

                for draft in drafts:
                    if draft.get("type") == "email" and draft.get("status") == "pending_send":
                        contact_email = (
                            draft.get("lead_brief", {}).get("contacts", {}).get("emails", [""])[0]
                            or "client@example.com"
                        )
                        if contact_email in ("unknown@example.com", "client@example.com"):
                            logger.warning(
                                "Skipping send for {}: no valid contact email",
                                draft.get("to", "unknown"),
                            )
                            draft["status"] = "skipped_no_email"
                            self.delivery_agent._save_draft(draft)
                            continue
                        if self.paypal_client.client_id:
                            lead_id = draft.get("lead_brief", {}).get("url", "unknown")[:32]
                            package = draft.get("lead_brief", {}).get("recommended_package", {})
                            price_str = package.get("price_range", "$500-$1,500")
                            amount = self._extract_amount(price_str)
                            invoice = self.payment_ledger.create_invoice(
                                lead_id=lead_id,
                                amount=amount,
                                description=f"MECOS automation: {package.get('name', 'custom')}",
                                client_email=contact_email,
                            )
                            paypal_result = self.paypal_client.create_order(
                                invoice_id=invoice["invoice_id"],
                                amount=amount,
                                description=f"MECOS automation: {package.get('name', 'custom')}",
                                client_email=contact_email,
                            )
                            if paypal_result.get("checkout_url"):
                                self.payment_ledger.link_paypal_order(
                                    invoice["invoice_id"],
                                    paypal_result["order_id"],
                                    paypal_result["checkout_url"],
                                )
                                draft["payment_link"] = paypal_result["checkout_url"]
                                draft["invoice_id"] = invoice["invoice_id"]
                                total_invoiced += 1
                                logger.info(f"Invoice {invoice['invoice_id']} created: ${amount:.2f} → {paypal_result['checkout_url'][:60]}")

                        if self.delivery_agent.send_draft(draft):
                            total_sent += 1
            except Exception as e:
                logger.error(f"Draft generation failed for {brief.get('domain')}: {e}")

        pending = len(self.delivery_agent.list_pending())
        logger.info(f"Outreach drafts: {total_drafts} created, {total_sent} sent, {pending} pending review, {total_invoiced} invoiced")
        return {"drafts_created": total_drafts, "drafts_sent": total_sent, "pending_review": pending, "invoices_created": total_invoiced}

    def _run_reply_check_cycle(self) -> dict:
        new_replies = self.reply_monitor.fetch_new_replies()
        demo_triggered = 0
        for reply in new_replies:
            if reply.get("demo_keyword_detected"):
                sent_file = reply.get("matched_sent_file")
                sent_email = None
                if sent_file:
                    try:
                        from pathlib import Path
                        p = Path(sent_file)
                        if not p.exists():
                            p = self.delivery_agent.sent_dir / p.name
                        if p.exists():
                            sent_email = json.loads(p.read_text())
                    except Exception as exc:
                        logger.debug(f"Failed to load sent email for reply: {exc}")
                if self.demo_deliverer.send_demo_reply(reply, sent_email):
                    demo_triggered += 1
                self.reply_monitor.mark_processed(reply.get("receiver_uid", ""), demo_triggered=(demo_triggered > 0))
        logger.info(f"Reply check: {len(new_replies)} replies, {demo_triggered} demo deliveries")
        return {"replies_found": len(new_replies), "demos_sent": demo_triggered}

    def _run_followup_cycle(self) -> dict:
        if not hasattr(self.followup_engine, "create_followup_drafts"):
            return {"followups_drafted": 0, "reason": "unavailable"}
        drafts = self.followup_engine.create_followup_drafts(limit=10)
        sent = 0
        from outreach.delivery_agent import DeliveryAgent
        delivery = DeliveryAgent()
        for item in drafts:
            try:
                path = Path(item["saved"])
                if path.exists():
                    data = json.loads(path.read_text())
                    if data.get("status") == "pending_send":
                        if delivery.send_draft(data):
                            sent += 1
            except Exception as exc:
                logger.debug(f"Failed to send follow-up draft: {exc}")
        logger.info(f"Follow-up cycle: {len(drafts)} drafted, {sent} sent")
        return {"followups_drafted": len(drafts), "followups_sent": sent}

    def check_replies(self) -> dict:
        return self._run_reply_check_cycle()

    def send_followups(self) -> dict:
        return self._run_followup_cycle()

    def _extract_amount(self, price_str: str) -> float:
        import re
        numbers = re.findall(r"[\d,]+", price_str.replace(",", ""))
        if numbers:
            return float(numbers[0])
        return 500.0

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
