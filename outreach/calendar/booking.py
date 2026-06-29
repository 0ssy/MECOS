"""
MECOS Outreach - Calendar Booking Integration
Generates Google Calendar booking links and parses replies for meeting intent.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from loguru import logger
from config import settings


class CalendarBooking:
    """Generate booking links and detect meeting intent in replies."""

    BUYING_SIGNALS = [
        "meeting", "call", "schedule", "book", "available",
        "calendar", "demo", "chat", "zoom", "time",
    ]

    def __init__(self, calendar_link: str = "", duration_minutes: int = 30):
        self.calendar_link = calendar_link or settings.MECOS_BOOKING_LINK or ""
        self.duration_minutes = duration_minutes

    def generate_booking_link(self, subject: str = "MECOS Discovery Call") -> str:
        now = datetime.now()
        end = now + timedelta(minutes=self.duration_minutes)
        dates = (
            f"{now.strftime('%Y%m%dT%H%M%S')}/{end.strftime('%Y%m%dT%H%M%S')}"
        )
        return (
            f"https://calendar.google.com/calendar/render?action=TEMPLATE"
            f"&text={self._url_encode(subject)}&dates={dates}"
            f"&details=Booked+via+MECOS"
        )

    def _url_encode(self, text: str) -> str:
        import urllib.parse
        return urllib.parse.quote(text, safe="")

    def has_meeting_intent(self, text: str) -> bool:
        text_lower = text.lower()
        return any(signal in text_lower for signal in self.BUYING_SIGNALS)

    def extract_availability(self, text: str) -> List[str]:
        patterns = [
            r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)[\s,]+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)",
            r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*(?:-|to)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)",
        ]
        matches = []
        for pat in patterns:
            matches.extend(re.findall(pat, text, re.IGNORECASE))
        return list(set(matches[:5]))

    def build_booking_email(self, lead_name: str = "", company: str = "") -> str:
        link = self.calendar_link or self.generate_booking_link()
        return (
            f"Hi{(' ' + lead_name) if lead_name else ''},\n\n"
            f"Great to connect with {company or 'you'}!\n\n"
            f"Let's schedule a quick 15-minute call to discuss how "
            f"MECOS can automate your outreach.\n\n"
            f"Pick a time that works for you:\n{link}\n\n"
            f"Looking forward to it.\n"
        )
