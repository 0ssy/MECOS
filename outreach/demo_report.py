"""
MECOS Outreach - Demo Report Generator
Lightweight mini-audit that takes a URL, detects pain points,
and generates a personalized HTML "Automation Opportunity Report".
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from outreach.scanner import (
    PAIN_KEYWORDS,
    INEFFICIENCY_MARKERS,
    LOCAL_BUSINESS_SIGNALS,
    OutreachScanner,
)


class DemoReportGenerator:
    """Generates personalized automation opportunity reports for leads."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path("data/outreach/demos")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def generate(self, url: str, lead: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not OutreachScanner._is_business_url(url):
            return {"ok": False, "error": "url_blocked", "url": url}

        page = await self._fetch_page(url)
        if not page.get("ok"):
            return {"ok": False, "error": page.get("error", "fetch_failed"), "url": url}

        text = page["text"]
        html = page["html"]
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]

        pain_points = self._detect_pain_points(text)
        inefficiencies = self._detect_inefficiencies(text)
        local_signals = self._detect_local_signals(text, url)
        recommended_tools = self._recommend_tools(pain_points, inefficiencies)

        estimated_savings = self._estimate_savings(pain_points, inefficiencies)
        cta = self._build_cta(domain, pain_points)

        report_html = self._build_html_report(
            domain=domain,
            url=url,
            pain_points=pain_points,
            inefficiencies=inefficiencies,
            local_signals=local_signals,
            recommended_tools=recommended_tools,
            estimated_savings=estimated_savings,
            cta=cta,
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{domain}_demo_report.html"
        report_path = self.output_dir / filename
        report_path.write_text(report_html, encoding="utf-8")

        return {
            "ok": True,
            "url": url,
            "domain": domain,
            "report_path": str(report_path),
            "pain_points": pain_points,
            "inefficiencies": inefficiencies,
            "local_signals": local_signals,
            "recommended_tools": recommended_tools,
            "estimated_savings": estimated_savings,
            "cta": cta,
        }

    async def _fetch_page(self, url: str) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                )
            if response.status_code != 200:
                return {"ok": False, "error": f"HTTP {response.status_code}"}
            html = response.text
            soup = BeautifulSoup(html, "html.parser")
            for script in soup(["script", "style"]):
                script.decompose()
            text = soup.get_text(separator="\n")
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            clean_text = "\n".join(chunk for chunk in chunks if chunk)
            return {"ok": True, "text": clean_text, "html": html}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _detect_pain_points(self, text: str) -> List[str]:
        text_lower = text.lower()
        found = []
        for kw in PAIN_KEYWORDS:
            if kw in text_lower:
                found.append(kw)
        return found[:8]

    def _detect_inefficiencies(self, text: str) -> List[str]:
        text_lower = text.lower()
        found = []
        for marker in INEFFICIENCY_MARKERS:
            if marker in text_lower:
                found.append(marker)
        return found[:8]

    def _detect_local_signals(self, text: str, url: str) -> List[str]:
        text_lower = text.lower()
        found = []
        for signal in LOCAL_BUSINESS_SIGNALS:
            if signal in text_lower:
                found.append(signal)
        parsed = urlparse(url)
        path = parsed.path.lower()
        if any(ext in path for ext in ["/contact", "/about", "/team", "/about-us"]):
            found.append("contact_page")
        if "address" in text_lower or "directions" in text_lower:
            found.append("physical_address")
        if re.search(r"\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}", text):
            found.append("phone_number")
        return found[:8]

    def _recommend_tools(self, pain_points: List[str], inefficiencies: List[str]) -> List[Dict[str, str]]:
        tools = []
        pain_set = set(pain_points)
        ineff_set = set(inefficiencies)

        if "spreadsheet hell" in pain_set or "manual data entry" in pain_set:
            tools.append({
                "name": "Data Pipeline Bot",
                "description": "Automated data entry from spreadsheets/forms into your system",
                "savings": "10-20 hrs/week",
            })
        if "copy paste" in pain_set or "repetitive" in pain_set:
            tools.append({
                "name": "Workflow Automation",
                "description": "Eliminate copy-paste loops with scheduled script automation",
                "savings": "5-15 hrs/week",
            })
        if "no system" in pain_set or "disorganized" in pain_set:
            tools.append({
                "name": "Process Orchestrator",
                "description": "Central dashboard that routes tasks and tracks status",
                "savings": "8-12 hrs/week",
            })
        if "contact form" in ineff_set or "call for pricing" in ineff_set:
            tools.append({
                "name": "Customer Intake Bot",
                "description": "Auto-qualify leads from contact forms and booking pages",
                "savings": "3-8 hrs/week",
            })
        if "appointment only" in ineff_set or "hours of operation" in ineff_set:
            tools.append({
                "name": "Scheduling Integration",
                "description": "Sync calendar bookings with reminders and confirmations",
                "savings": "2-5 hrs/week",
            })
        if not tools:
            tools.append({
                "name": "Custom Automation Audit",
                "description": "Full workflow analysis and prioritized automation roadmap",
                "savings": "varies",
            })
        return tools[:4]

    def _estimate_savings(self, pain_points: List[str], inefficiencies: List[str]) -> str:
        severity = len(pain_points) + len(inefficiencies)
        if severity >= 8:
            return "15-30 hours/week"
        if severity >= 5:
            return "8-15 hours/week"
        if severity >= 3:
            return "3-8 hours/week"
        return "2-5 hours/week"

    def _build_cta(self, domain: str, pain_points: List[str]) -> str:
        primary = pain_points[0].replace("_", " ") if pain_points else "inefficient processes"
        return (
            f"I analyzed {domain} and found key friction around \"{primary}\". "
            f"Based on this audit, I recommend starting with a focused 3-5 day automation build "
            f"at a fixed scope of $500-$1,500. "
            f"If this resonates, reply and I'll send a comparable build demo."
        )

    def _build_html_report(
        self,
        domain: str,
        url: str,
        pain_points: List[str],
        inefficiencies: List[str],
        local_signals: List[str],
        recommended_tools: List[Dict[str, str]],
        estimated_savings: str,
        cta: str,
    ) -> str:
        pain_items = "".join(f"<li>{p}</li>" for p in pain_points) or "<li>None detected</li>"
        ineff_items = "".join(f"<li>{i}</li>" for i in inefficiencies) or "<li>None detected</li>"
        local_items = "".join(f"<li>{s}</li>" for s in local_signals) or "<li>None detected</li>"
        tool_cards = "".join(
            f"<div class='tool'><h4>{t['name']}</h4><p>{t['description']}</p><span class='savings'>{t['savings']}</span></div>"
            for t in recommended_tools
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Automation Opportunity Report — {domain}</title>
<style>
    body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #333; }}
    h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
    h2 {{ color: #34495e; margin-top: 30px; }}
    .meta {{ color: #7f8c8d; font-size: 0.9em; margin-bottom: 30px; }}
    ul {{ line-height: 1.8; }}
    .tool {{ background: #f8f9fa; border-left: 4px solid #3498db; padding: 15px; margin: 10px 0; }}
    .tool h4 {{ margin: 0 0 5px 0; color: #2c3e50; }}
    .savings {{ display: inline-block; background: #3498db; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.85em; margin-top: 8px; }}
    .cta {{ background: #e8f6f3; border: 1px solid #1abc9c; padding: 20px; border-radius: 6px; margin-top: 30px; }}
    .highlight {{ background: #fff3cd; padding: 2px 6px; border-radius: 4px; }}
</style>
</head>
<body>
    <h1>Automation Opportunity Report</h1>
    <div class="meta">
        <strong>Business:</strong> {domain}<br>
        <strong>URL:</strong> <a href="{url}">{url}</a><br>
        <strong>Date:</strong> {datetime.now().strftime("%B %d, %Y")}
    </div>

    <h2>Pain Points Detected</h2>
    <ul>{pain_items}</ul>

    <h2>Inefficiency Markers</h2>
    <ul>{ineff_items}</ul>

    <h2>Local Business Signals</h2>
    <ul>{local_items}</ul>

    <h2>Recommended Automation</h2>
    {tool_cards}

    <h2>Estimated Time Savings</h2>
    <p class="highlight">{estimated_savings}</p>

    <div class="cta">
        <h3>Next Step</h3>
        <p>{cta}</p>
    </div>

    <footer style="margin-top: 40px; color: #95a5a6; font-size: 0.85em; text-align: center;">
        Generated by MECOS Automation Opportunity Scanner
    </footer>
</body>
</html>"""
