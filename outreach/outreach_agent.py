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
from typing import Optional

from loguru import logger

from memory_system import MemorySystem
from outreach.ceo_instincts import CeoInstincts
from outreach.delivery_agent import DeliveryAgent
from outreach.demo_deliverer import DemoDeliverer
from outreach.email_enricher import EmailEnricher
from outreach.followup_engine import FollowupEngine
from outreach.funnel_builder import FunnelBuilder
from outreach.payments.payment_ledger import PaymentLedger
from outreach.payments.paypal_client import PayPalClient
from outreach.reply_monitor import ReplyMonitor
from outreach.research_orchestrator import ResearchOrchestrator
from outreach.revenue_ledger import RevenueLedger
from outreach.scanner import PAIN_KEYWORDS, OutreachScanner
from outreach.lead_sources.base import LeadSource
from outreach.lead_sources import INDUSTRY_SOURCES
from outreach.analytics.funnel import FunnelAnalytics
from outreach.email_sequence import EmailSequence
from outreach.followup_scheduler import FollowupScheduler
from outreach.synthesizer import LeadSynthesizer
from outreach.twenty.twenty_bridge import TwentyBridge
from outreach.worldmonitor_adapter import WorldMonitorAdapter


class OutreachAgent:
    def __init__(self, memory: MemorySystem):
        self.memory = memory
        self.enabled = os.getenv("MECOS_ENABLE_OUTREACH", "false").strip().lower() == "true"
        self.scanner = OutreachScanner(memory=memory)
        self.lead_sources = INDUSTRY_SOURCES
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
        self.twenty_bridge = TwentyBridge()
        self.reply_monitor.attach_demo_deliverer(self.demo_deliverer)

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
            if self.cycle % 20 == 0:
                research_result = await self._run_research_cycle()
                result["research"] = research_result

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

            if self.cycle % 7 == 5:
                approval_result = self._run_approval_cycle()
                result["approvals"] = approval_result

            reply_result = await self._run_reply_check_cycle()
            result["replies"] = reply_result

            if self.cycle % 10 == 0:
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

    async def _run_research_cycle(self) -> dict:
        orchestrator = ResearchOrchestrator()
        keywords = PAIN_KEYWORDS[:6]
        candidates = await orchestrator.discover_lead_signals(keywords)

        new_count = 0
        for candidate in candidates:
            url = candidate.get("url", "")
            if not url:
                continue
            if url in self.scanner.scanned_urls:
                continue
            existing = next(
                (lead_item for lead_item in self.scanner.leads if lead_item.get("url") == url), None
            )
            if existing:
                continue

            lead = {
                "url": url,
                "domain": candidate.get("domain", ""),
                "discovered_at": datetime.now().isoformat(),
                "content_hash": candidate.get("content_hash", ""),
                "signals": candidate.get("signals", {}),
                "total_score": candidate.get("total_score", 0),
                "matched_terms": candidate.get("matched_terms", []),
                "contacts": {"emails": [], "phones": [], "social": []},
                "status": "new",
                "pitch_suggestion": "",
                "source": f"research_cycle/{candidate.get('source_platform', 'unknown')}",
                "local_business_score": 0,
                "enterprise_penalty": 0,
            }
            if candidate.get("text_excerpt"):
                lead["text_excerpt"] = candidate["text_excerpt"]

            if not OutreachScanner._is_business_url(url):
                logger.debug(f"Research cycle blocked bad URL: {url}")
                continue

            self.scanner.leads.append(lead)
            self.scanner.scanned_urls.add(url)
            if candidate.get("content_hash"):
                self.scanner.scanned_content_hashes.add(candidate["content_hash"])
            new_count += 1

        if new_count > 0:
            self.scanner._save_leads()
            for lead_item in self.scanner.leads[-new_count:]:
                self.twenty_bridge.sync_lead(lead_item)

        logger.info(
            f"Research cycle: discovered {len(candidates)} candidates, {new_count} new leads"
        )
        return {"discovered": len(candidates), "new_leads": new_count}

    async def _run_scan_cycle(self) -> dict:
        dir_leads = []
        try:
            dir_leads = await self.scanner.scan_business_directories(limit=15)
        except Exception as e:
            logger.debug(f"Business directory scan skip: {e}")

        searxng_queries = [
            "HVAC scheduling spreadsheet hell small business",
            "auto repair shop manual invoicing small business",
            "dental office patient intake paper forms small business",
            "plumbing dispatch spreadsheet small business",
            "local business appointment booking pain",
            "family owned business manual processes",
            "small business workflow bottleneck",
            "local service business automation needed",
        ]
        search_tasks = [self.scanner.search_leads(q, limit=5) for q in searxng_queries]
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        search_leads = []
        for r in search_results:
            if isinstance(r, list):
                search_leads.extend(r)
            elif isinstance(r, Exception):
                logger.debug(f"SearXNG search error: {r}")

        total = len(dir_leads) + len(search_leads)
        
        source_leads = []
        try:
            for name, source_cls in self.lead_sources.items():
                try:
                    src = source_cls()
                    urls = await src.get_leads()
                    source_leads.extend(urls)
                except Exception as exc:
                    logger.debug(f"Lead source {name} failed: {exc}")
        except Exception as exc:
            logger.debug(f"Lead sources scan skip: {exc}")
        
        all_new = dir_leads + search_leads + source_leads
        total = len(all_new)
        logger.info(f"Outreach scan: {total} leads found ({len(dir_leads)} directories + {len(search_leads)} search + {len(source_leads)} industry sources)")

        if all_new:
            filtered = []
            skipped = []
            for lead in all_new:
                local_score = lead.get("local_business_score", 0)
                enterprise_penalty = lead.get("enterprise_penalty", 0)
                if local_score < 3 or enterprise_penalty > 2:
                    skip_reason = ""
                    if enterprise_penalty > 2:
                        skip_reason = f"enterprise_penalty={enterprise_penalty}"
                    else:
                        skip_reason = f"local_business_score={local_score}"
                    skipped.append({
                        "url": lead.get("url", ""),
                        "domain": lead.get("domain", ""),
                        "reason": skip_reason,
                        "local_business_score": local_score,
                        "enterprise_penalty": enterprise_penalty,
                        "skipped_at": datetime.now().isoformat(),
                    })
                    continue
                filtered.append(lead)

            if skipped:
                skip_path = Path("data/outreach/skipped_leads.jsonl")
                skip_path.parent.mkdir(parents=True, exist_ok=True)
                with open(skip_path, "a", encoding="utf-8") as f:
                    for item in skipped:
                        f.write(json.dumps(item, default=str) + "\n")
                logger.info(f"Outreach scan: skipped {len(skipped)} leads (ICP gate)")

            enriched_new = await self.email_enricher.enrich_batch(filtered)
            for lead in enriched_new:
                if lead.get("contacts", {}).get("emails"):
                    existing = next((l for l in self.scanner.leads if l.get("url") == lead.get("url")), None)
                    if existing:
                        existing["contacts"] = lead["contacts"]
                    else:
                        self.scanner.leads.append(lead)

            scored = self.intel_adapter.enrich_batch(filtered)
            for lead in scored:
                if lead.get("intel_multiplier", 1.0) != 1.0:
                    self.scanner.leads = [l if l.get("url") != lead.get("url") else lead for l in self.scanner.leads]
                    self.scanner._save_leads()

            return {"urls_scanned": len(searxng_queries), "new_leads": len(filtered), "intel_scored": sum(1 for l in scored if l.get("intel_multiplier", 1.0) != 1.0)}

        return {"urls_scanned": len(searxng_queries), "new_leads": 0, "intel_scored": 0}

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
                for i, existing in enumerate(self.scanner.leads):
                    if existing.get("url") == lead.get("url"):
                        self.scanner.leads[i] = lead
                        break
        if updated > 0:
            self.scanner._save_leads()

        logger.info(f"Outreach enrichment: {updated}/{len(batch)} leads got emails")
        return {"enriched": updated, "attempted": len(batch)}

    async def _run_synth_cycle(self) -> dict:
        new_leads = self.scanner.get_new_leads(min_score=1, limit=10)
        if not new_leads:
            return {"synthesized": 0}

        filtered = []
        skipped = []
        for lead in new_leads:
            local_score = lead.get("local_business_score", 0)
            enterprise_penalty = lead.get("enterprise_penalty", 0)
            if local_score < 3 or enterprise_penalty > 2:
                skipped.append({
                    "url": lead.get("url", ""),
                    "domain": lead.get("domain", ""),
                    "reason": f"local_business_score={local_score}" if local_score < 3 else f"enterprise_penalty={enterprise_penalty}",
                    "local_business_score": local_score,
                    "enterprise_penalty": enterprise_penalty,
                    "skipped_at": datetime.now().isoformat(),
                })
                continue
            filtered.append(lead)

        if skipped:
            skip_path = Path("data/outreach/skipped_leads.jsonl")
            skip_path.parent.mkdir(parents=True, exist_ok=True)
            with open(skip_path, "a", encoding="utf-8") as f:
                for item in skipped:
                    f.write(json.dumps(item, default=str) + "\n")
            logger.info(f"Outreach synth: skipped {len(skipped)} leads (ICP gate)")

            skipped_urls = {item["url"] for item in skipped}
            self.scanner.leads = [l for l in self.scanner.leads if l.get("url") not in skipped_urls]
            self.scanner._save_leads()

        new_leads = [self.instincts.score_lead(l) for l in filtered]
        new_leads.sort(key=lambda l: l.get("total_score", 0), reverse=True)

        briefs = await self.synthesizer.synthesize_batch(new_leads)
        count = len(briefs)
        for brief_item in briefs:
            self.twenty_bridge.sync_brief(brief_item)
        logger.info(f"Outreach synthesis: {count} leads briefed (instincts ranked)")
        return {"synthesized": count}

    async def _run_draft_cycle(self) -> dict:
        ready = self.synthesizer.get_ready_for_outreach(limit=5)
        if not ready:
            return {"drafts_created": 0}

        filtered = []
        skipped = []
        for brief in ready:
            lead_url = brief.get("url", "")
            lead = next((l for l in self.scanner.leads if l.get("url") == lead_url), None)
            local_score = (lead or {}).get("local_business_score", 0)
            enterprise_penalty = (lead or {}).get("enterprise_penalty", 0)
            if local_score < 3 or enterprise_penalty > 2:
                skip_reason = ""
                if enterprise_penalty > 2:
                    skip_reason = f"enterprise_penalty={enterprise_penalty}"
                else:
                    skip_reason = f"local_business_score={local_score}"
                skipped.append({
                    "url": lead_url,
                    "domain": brief.get("domain", ""),
                    "reason": skip_reason,
                    "local_business_score": local_score,
                    "enterprise_penalty": enterprise_penalty,
                    "skipped_at": datetime.now().isoformat(),
                })
                continue
            filtered.append(brief)

        if skipped:
            skip_path = Path("data/outreach/skipped_leads.jsonl")
            skip_path.parent.mkdir(parents=True, exist_ok=True)
            with open(skip_path, "a", encoding="utf-8") as f:
                for item in skipped:
                    f.write(json.dumps(item, default=str) + "\n")
            logger.info(f"Outreach draft: skipped {len(skipped)} briefs (ICP gate)")

            skipped_urls = {item["url"] for item in skipped}
            self.scanner.leads = [l for l in self.scanner.leads if l.get("url") not in skipped_urls]
            self.scanner._save_leads()

        research_orchestrator = ResearchOrchestrator()
        self._research_orchestrator = research_orchestrator

        total_drafts = 0
        total_sent = 0
        total_invoiced = 0
        for brief in filtered:
            try:
                lead_url = brief.get("url", "")
                lead = next((l for l in self.scanner.leads if l.get("url") == lead_url), None)
                if lead and research_orchestrator.should_research(lead):
                    signals = await research_orchestrator.research_lead(lead)
                    brief["research_summary"] = research_orchestrator.build_summary(signals)
                    for i, b in enumerate(self.synthesizer.briefs):
                        if b.get("url") == lead_url:
                            self.synthesizer.briefs[i]["research_summary"] = brief["research_summary"]
                            break
                    self.scanner._save_leads()
                    self.synthesizer._save()

                drafts = self.delivery_agent.draft_for_lead(brief)
                for draft in drafts:
                    draft["status"] = "pending_review"
                paths = self.delivery_agent.save_drafts(drafts)
                total_drafts += len(paths)

                for draft_item in drafts:
                    self.twenty_bridge.sync_draft(draft_item)

                brief["status"] = "drafted"
                self.synthesizer._save()

                for draft in drafts:
                    if draft.get("type") == "email":
                        contact_email = (
                            draft.get("lead_brief", {}).get("contacts", {}).get("emails", [""])[0]
                            or "unknown@example.com"
                        )
                        if contact_email in ("unknown@example.com", "client@example.com"):
                            draft["status"] = "skipped_no_email"
                            self.delivery_agent._save_draft(draft)
                            continue
                        recipient_domain = contact_email.split("@")[-1].lower()
                        if recipient_domain in OutreachScanner.AGGREGATOR_DOMAINS or ".example.com" in recipient_domain:
                            draft["status"] = "skipped_bad_domain"
                            self.delivery_agent._save_draft(draft)
                            continue
                        body = draft.get("body", "")
                        if len(body) < 200:
                            draft["status"] = "skipped_low_quality"
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
                                self.twenty_bridge.sync_payment(invoice)
                                logger.info(f"Invoice {invoice['invoice_id']} created: ${amount:.2f} → {paypal_result['checkout_url'][:60]}")
            except Exception as e:
                logger.error(f"Draft generation failed for {brief.get('domain')}: {e}")

        pending = len(self.delivery_agent.list_pending())
        logger.info(f"Outreach drafts: {total_drafts} created, 0 sent (manual review), {pending} pending review, {total_invoiced} invoiced")
        return {"drafts_created": total_drafts, "drafts_sent": 0, "pending_review": pending, "invoices_created": total_invoiced, "skipped_icp": len(skipped)}

    async def _run_reply_check_cycle(self) -> dict:
        new_replies = self.reply_monitor.fetch_new_replies()
        demo_triggered = 0
        booking_triggered = 0

        for reply in new_replies:
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

            lead_url = None
            if sent_email:
                lead_url = sent_email.get("lead_brief", {}).get("url")

            if reply.get("demo_keyword_detected"):
                report_path = None
                if lead_url:
                    try:
                        from outreach.demo_report import DemoReportGenerator
                        report = await asyncio.to_thread(DemoReportGenerator().generate, lead_url)
                        if report.get("ok"):
                            report_path = report.get("report_path")
                            self._log_demo_delivery(reply, report_path)
                    except Exception as exc:
                        logger.error(f"Demo report generation failed: {exc}")

                if self.demo_deliverer.send_demo_reply(reply, sent_email, report_path):
                    demo_triggered += 1
                self.reply_monitor.mark_processed(reply.get("receiver_uid", ""), demo_triggered=(demo_triggered > 0))
            elif reply.get("high_intent"):
                try:
                    from outreach.calendar.booking import CalendarBooking
                    booking = CalendarBooking()
                    to_addr = (reply.get("from") or "").split("<")[-1].split(">")[0].strip()
                    if not to_addr and sent_email:
                        to_addr = sent_email.get("to", "")
                    link = reply.get("booking_link") or booking.generate_booking_link()
                    body = booking.build_booking_email(company=to_addr)
                    success, _ = self.delivery_agent._send_smtp(to_addr, "Let's schedule your MECOS call", body)
                    if success:
                        booking_triggered += 1
                        reply["booking_sent"] = True
                        self.reply_monitor.mark_processed(reply.get("receiver_uid", ""), demo_triggered=False)
                        logger.info(f"Booking link sent to {to_addr}")
                except Exception as exc:
                    logger.error(f"Booking email failed: {exc}")

        logger.info(f"Reply check: {len(new_replies)} replies, {demo_triggered} demo deliveries, {booking_triggered} booking links")
        return {"replies_found": len(new_replies), "demos_sent": demo_triggered, "bookings_sent": booking_triggered}

    def _log_demo_delivery(self, reply: dict, report_path: Optional[str]) -> None:
        delivered_path = Path("data/outreach/demos/delivered.jsonl")
        delivered_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now().isoformat(),
            "receiver": reply.get("from"),
            "subject": reply.get("subject"),
            "report_path": report_path,
        }
        try:
            with open(delivered_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
        except Exception as exc:
            logger.error(f"Failed to log demo delivery: {exc}")

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

    def _run_approval_cycle(self) -> dict:
        if not self.twenty_bridge.enabled:
            return {"approved_sent": 0, "reason": "crm_disabled"}

        approved = self.twenty_bridge.get_approved_drafts(limit=20)
        if not approved:
            return {"approved_sent": 0, "reason": "no_approved_drafts"}

        sent = 0
        skipped = 0
        for draft_node in approved:
            twenty_id = draft_node.get("id")
            subject = draft_node.get("subject", "")
            body = draft_node.get("body", "")
            brief = draft_node.get("leadBrief") or {}
            lead = brief.get("lead") or {}
            contact_email = ""
            contacts = brief.get("contacts") or {}
            if isinstance(contacts, dict):
                contact_email = (contacts.get("emails") or [""])[0]

            if not contact_email or "example.com" in contact_email:
                skipped += 1
                continue

            full_draft = {
                "type": "email",
                "subject": subject,
                "body": body,
                "lead_brief": {
                    "url": brief.get("url", ""),
                    "domain": lead.get("domain", brief.get("domain", "")),
                    "contacts": contacts,
                },
                "status": "approved",
            }
            if self.delivery_agent.send_draft(full_draft):
                sent += 1
                self.twenty_bridge.mark_draft_sent(twenty_id)
                logger.info(f"Sent approved draft via Twenty CRM: {subject}")
            else:
                skipped += 1

        return {"approved_sent": sent, "skipped": skipped, "checked": len(approved)}

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