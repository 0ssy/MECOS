"""
MECOS Outreach - Demo Deliverer
Creates demo pages and sends reply emails with demo links.
"""

from datetime import datetime
from pathlib import Path

from loguru import logger


class DemoDeliverer:
    def __init__(self, demos_dir: Path | None = None):
        if demos_dir is None:
            from config import settings
            demos_dir = settings.DATA_DIR / "outreach" / "demos"
        self.demos_dir = demos_dir
        self.demos_dir.mkdir(parents=True, exist_ok=True)
        self.funnel_builder = self._get_funnel_builder()

    def _get_funnel_builder(self):
        try:
            from outreach.funnel_builder import FunnelBuilder
            return FunnelBuilder()
        except Exception as exc:
            logger.debug(f"FunnelBuilder unavailable: {exc}")
            return None

    def send_demo_reply(self, reply_event: dict, sent_email: dict | None = None, report_path: str | None = None) -> bool:
        to_addr = (reply_event.get("from") or "").split("<")[-1].split(">")[0].strip()
        if not to_addr:
            to_addr = sent_email.get("to") if sent_email else ""

        referral_code = ""
        lead_brief = {}
        if sent_email:
            referral_code = sent_email.get("referral_code", "")
            lead_brief = sent_email.get("lead_brief", {})

        case_study = self._select_case_study(lead_brief)
        demo_path = self._create_demo_page(case_study, referral_code, to_addr)

        reply_subject = f"Re: {reply_event.get('subject', 'Your automation inquiry')}"
        
        report_link = "\n\n**Automation Opportunity Report attached below**\n\n" if report_path else ""
        
        reply_body = (
            f"Thanks for reaching out!\n\n"
            f"Here's the demo you asked for: {demo_path}{report_link}"
            f"This shows what we're capable of for a similar project.\n"
            f"If it looks like a fit, reply and we'll discuss next steps.\n\n"
            f"Know someone who'd benefit? Refer them and you both get:\n"
            f"- $50 service credit\n"
            f"- 10% off next invoice\n"
            f"- 30 days free service extension\n\n"
            f"Your referral code: {referral_code}\n"
        )

        success = self._send_reply(to_addr, reply_subject, reply_body, reply_event)
        if success:
            reply_event["processed"] = True
            reply_event["demo_triggered"] = True
            reply_event["demo_path"] = demo_path
            logger.info(f"Demo reply sent to {to_addr}: {demo_path}")
        return success

    def _select_case_study(self, lead_brief: dict) -> dict:
        if lead_brief:
            pain_point = (lead_brief.get("pain_points", ["manual data work"]) or ["manual data work"])[0].replace("_", " ")
        else:
            pain_point = "manual data work"
        domain = lead_brief.get("domain", "referred client")
        return {
            "problem": pain_point,
            "solution": f"Custom automation for {domain}",
            "tech_stack": ["Python", "Playwright", "ChromaDB"],
            "time_saved_pct": lead_brief.get("time_saved_pct", 60),
            "before_hours_per_week": 10,
            "after_hours_per_week": 1,
            "package": lead_brief.get("recommended_package", {}).get("name", "single_bot_package"),
        }

    def _create_demo_page(self, case_study: dict, referral_code: str, to_addr: str) -> str:
        safe_code = (referral_code or "demo").lower()
        html_content = self._build_demo_html(case_study, referral_code)

        demo_filename = f"demo_{safe_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        demo_path = self.demos_dir / demo_filename
        demo_path.write_text(html_content, encoding="utf-8")
        logger.info(f"Demo page created: {demo_path.name}")
        return str(demo_path)

    def _build_demo_html(self, case_study: dict, referral_code: str) -> str:
        client = case_study.get("solution", "Automation Bot")
        problem = case_study.get("problem", "Manual processes")
        pct = case_study.get("time_saved_pct", 60)
        before = case_study.get("before_hours_per_week", 10)
        after = case_study.get("after_hours_per_week", 1)
        tech = ", ".join(case_study.get("tech_stack", ["Python", "Playwright"]))
        code = referral_code or "N/A"

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MECOS Demo - {problem}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 700px; margin: 0 auto; padding: 40px 20px; }}
        h1, h2, h3 {{ color: #1a1a1a; }}
        .metric {{ background: #e0f2fe; padding: 15px; border-radius: 8px; margin: 20px 0; }}
        .highlight {{ color: #0284c7; font-weight: bold; }}
        .code {{ font-family: monospace; background: #f5f5f5; padding: 10px; display: inline-block; }}
    </style>
</head>
<body>
    <h1>Automation Demo: {client}</h1>
    <h2>The Problem</h2>
    <p>{problem} was consuming <strong>{before}+ hours per week</strong> of manual effort.</p>
    <div class="metric">
        <h3>Our Guarantee</h3>
        <p>We guarantee <span class="highlight">60%+ time reduction</span> on your targeted process within 30 days, or you pay nothing.</p>
    </div>
    <h2>The Solution</h2>
    <p>Built using: {tech}</p>
    <div class="metric">
        <h3>Result</h3>
        <p><span class="highlight">{pct:.0f}% time saved</span> - {before} hours/week reduced to {after} hour/week</p>
    </div>
    <h2>Your Referral Code</h2>
    <p class="code">{code}</p>
    <p>Share with someone who needs automation — you both get $50 + 10% off + 30 days free.</p>
</body>
</html>"""

    def _send_reply(self, to_addr: str, subject: str, body: str, reply_event: dict) -> bool:
        from outreach.delivery_agent import DeliveryAgent
        delivery = DeliveryAgent()
        reply_message_id = reply_event.get("receiver_uid")
        success, message_id = delivery._send_smtp(to_addr, subject, body, message_id=reply_message_id)
        if success and message_id:
            reply_event["reply_message_id"] = message_id
        return success
