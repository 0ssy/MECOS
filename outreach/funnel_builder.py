"""
MECOS Outreach - Funnel Builder
Creates demo projects, case studies, and social content to feed the audience funnel.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from config import settings


class FunnelBuilder:
    def __init__(self):
        self.funnel_dir = settings.DATA_DIR / "outreach" / "funnel"
        self.funnel_dir.mkdir(parents=True, exist_ok=True)
        self.case_studies_path = self.funnel_dir / "case_studies.json"
        self.content_calendar_path = self.funnel_dir / "content_calendar.json"
        self._load()

    def _load(self):
        if self.case_studies_path.exists():
            try:
                with open(self.case_studies_path) as f:
                    self.case_studies = json.load(f)
            except Exception:
                self.case_studies = []
        else:
            self.case_studies = []

        if self.content_calendar_path.exists():
            try:
                with open(self.content_calendar_path) as f:
                    self.content_calendar = json.load(f)
            except Exception:
                self.content_calendar = []
        else:
            self.content_calendar = []

    def _save(self):
        try:
            self.case_studies_path.write_text(json.dumps(self.case_studies[-50:], default=str, indent=2))
            self.content_calendar_path.write_text(json.dumps(self.content_calendar[-100:], default=str, indent=2))
        except Exception as e:
            logger.error(f"Failed to save funnel data: {e}")

    def create_case_study(self, deal: Dict[str, Any], outcome: Dict[str, Any]) -> Dict[str, Any]:
        client = deal.get("client_name", deal.get("domain", "Client"))
        package = deal.get("package", {})
        description = package.get("description", "Custom automation")
        price = deal.get("amount", "TBD")

        before_hours = outcome.get("before_hours_per_week", 10)
        after_hours = outcome.get("after_hours_per_week", 1)
        time_saved_pct = round((1 - after_hours / max(before_hours, 1)) * 100, 0)

        case_study = {
            "id": f"cs_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "created_at": datetime.now().isoformat(),
            "client": client,
            "package": package.get("name", "custom_automation"),
            "price": price,
            "problem": outcome.get("problem", "Manual operational overhead"),
            "solution": description,
            "before_hours_per_week": before_hours,
            "after_hours_per_week": after_hours,
            "time_saved_pct": time_saved_pct,
            "tech_stack": outcome.get("tech_stack", ["Python", "Playwright", "ChromaDB"]),
            "testimonial": outcome.get("testimonial", ""),
            "status": "draft",
        }

        self.case_studies.append(case_study)
        self._save()
        logger.info(f"Case study created for {client}: {time_saved_pct}% time saved")
        return case_study

    def generate_social_content(self, case_study: Dict[str, Any], platform: str) -> Dict[str, Any]:
        client = case_study.get("client", "a local business")
        problem = case_study.get("problem", "manual data work")
        pct = case_study.get("time_saved_pct", 80)
        tech = ", ".join(case_study.get("tech_stack", ["Python", "automation"]))

        if platform == "twitter":
            text = (
                f"Built a bot for {client} that cut their {problem} by {pct:.0f}%.\n\n"
                f"Stack: {tech}\n"
                f"Result: {case_study.get('after_hours_per_week', 1)} hrs/wk instead of "
                f"{case_study.get('before_hours_per_week', 10)}.\n\n"
                f"I'm documenting the full build. Follow for the open-source breakdown. #automation #python"
            )
        elif platform == "linkedin":
            text = (
                f"I recently finished an automation project for {client} that I'm really proud of.\n\n"
                f"The problem: {problem.title()} was consuming {case_study.get('before_hours_per_week', 10)} hours per week.\n"
                f"The solution: A custom Python bot using browser automation and data pipelines.\n"
                f"The result: Down to {case_study.get('after_hours_per_week', 1)} hour per week. ({pct:.0f}% reduction)\n\n"
                f"What's interesting is that the biggest challenge wasn't the code — it was understanding their workflow well enough to simplify it.\n\n"
                f"Tech used: {tech}\n\n"
                f"If your team is drowning in manual work, happy to do a free 15-min process audit. DM me."
            )
        elif platform == "reddit":
            text = (
                f"[Show MECOS] Built a {pct:.0f}% time-saving automation bot for {client}\n\n"
                f"What it does: Replaces {problem} with a scheduled, monitored script.\n"
                f"Tech: {tech}\n"
                f"Delivery: {case_study.get('package', '2-3 days')}\n\n"
                f"I'm sharing the architecture and open-source components. Full breakdown in comments.\n\n"
                f"If you have similar ops headaches, happy to review your process for free."
            )
        else:
            text = f"Automation case study: {client} saved {pct:.0f}% time on {problem} using {tech}."

        content = {
            "platform": platform,
            "text": text,
            "case_study_id": case_study.get("id"),
            "created_at": datetime.now().isoformat(),
            "status": "draft",
        }
        self.content_calendar.append(content)
        self._save()
        return content

    def generate_demo_project_brief(self, case_study: Dict[str, Any]) -> Dict[str, Any]:
        brief = {
            "id": f"demo_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "case_study_id": case_study.get("id"),
            "title": f"Demo: {case_study.get('problem', 'Automation Bot').title()}",
            "description": case_study.get("solution", "Custom automation demo"),
            "tech_stack": case_study.get("tech_stack", ["Python", "Playwright"]),
            "hosting": "github_pages",
            "repo_name": f"mecos-demo-{case_study.get('id', 'x')}",
            "features": [
                "Browser automation demo",
                "Before/after comparison",
                "Installation guide",
                "Live demo if applicable",
            ],
            "status": "planned",
            "created_at": datetime.now().isoformat(),
        }
        return brief

    def get_case_studies(self, limit: int = 10) -> List[Dict[str, Any]]:
        return [c for c in self.case_studies if c.get("status") == "published"][-limit:]

    def get_draft_content(self, limit: int = 10) -> List[Dict[str, Any]]:
        return [c for c in self.content_calendar if c.get("status") == "draft"][-limit:]
