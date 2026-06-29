"""
MECOS Outreach - Google Sheets CRM Bridge
Syncs leads to Google Sheets with columns: URL, Domain, Contact, Email, Twitter, Status, Last Contact, Notes, Source.
Uses Google Sheets API via service account (free tier).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

from config import settings


class SheetsBridge:
    """Sync leads to Google Sheets CRM."""

    COLUMNS = ["URL", "Domain", "Contact", "Email", "Twitter", "Status", "Last Contact", "Notes", "Source"]

    def __init__(self, credentials_path: Optional[str] = None, sheet_id: Optional[str] = None):
        self.credentials_path = credentials_path or str(settings.DATA_DIR / "crm" / "service_account.json")
        self.sheet_id = sheet_id or str(settings.CRM_SHEET_ID) if hasattr(settings, "CRM_SHEET_ID") else ""
        self.scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        self.service = None

        if not GOOGLE_AVAILABLE:
            logger.warning("Google Sheets API not available. Install google-api-python-client and google-auth.")

    def _ensure_service(self) -> bool:
        """Initialize Google Sheets service."""
        if self.service:
            return True

        if not GOOGLE_AVAILABLE or not Path(self.credentials_path).exists():
            return False

        try:
            creds = Credentials.from_service_account_file(self.credentials_path, scopes=self.scopes)
            self.service = build("sheets", "v4", credentials=creds)
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Sheets service: {e}")
            return False

    def push_leads(self, leads: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Push leads to Google Sheet."""
        if not self._ensure_service():
            return {"status": "error", "reason": "service_unavailable"}

        try:
            # Read existing data to check for duplicates
            existing = self._read_existing_leads()
            existing_urls = {row[0] for row in existing if len(row) > 0}

            # Prepare new rows
            rows = []
            for lead in leads:
                url = lead.get("url", "")
                if url in existing_urls:
                    continue

                row = [
                    url,
                    lead.get("domain", ""),
                    lead.get("contacts", {}).get("decision_maker", {}).get("name", ""),
                    lead.get("contacts", {}).get("emails", [""])[0],
                    lead.get("contacts", {}).get("social_profiles", {}).get("twitter", ""),
                    lead.get("status", "new"),
                    lead.get("discovered_at", ""),
                    lead.get("notes", ""),
                    lead.get("source", "unknown"),
                ]
                rows.append(row)

            if not rows:
                return {"status": "success", "message": "no_new_leads"}

            body = {"values": rows}
            self.service.spreadsheets().values().append(
                spreadsheetId=self.sheet_id,
                range="Leads!A2",
                valueInputOption="RAW",
                body=body,
            ).execute()

            logger.info(f"Pushed {len(rows)} leads to Google Sheet")
            return {"status": "success", "count": len(rows)}

        except Exception as e:
            logger.error(f"Failed to push leads to Sheets: {e}")
            return {"status": "error", "error": str(e)}

    def pull_leads(self) -> List[Dict[str, Any]]:
        """Read leads from Google Sheet."""
        if not self._ensure_service():
            return []

        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range="Leads!A2:I",
            ).execute()

            rows = result.get("values", [])
            leads = []
            for row in rows:
                lead = {
                    "url": row[0] if len(row) > 0 else "",
                    "domain": row[1] if len(row) > 1 else "",
                    "contact_name": row[2] if len(row) > 2 else "",
                    "email": row[3] if len(row) > 3 else "",
                    "twitter": row[4] if len(row) > 4 else "",
                    "status": row[5] if len(row) > 5 else "new",
                    "last_contact": row[6] if len(row) > 6 else "",
                    "notes": row[7] if len(row) > 7 else "",
                    "source": row[8] if len(row) > 8 else "",
                }
                leads.append(lead)
            return leads
        except Exception as e:
            logger.error(f"Failed to pull leads from Sheets: {e}")
            return []

    def _read_existing_leads(self) -> List[List[str]]:
        """Read existing URLs from sheet for deduplication."""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range="Leads!A:A",
            ).execute()
            return result.get("values", [])
        except Exception:
            return []

    def update_lead_status(self, url: str, status: str, notes: str = "") -> Dict[str, Any]:
        """Update lead status in sheet."""
        if not self._ensure_service():
            return {"status": "error", "reason": "service_unavailable"}

        try:
            # Find row with URL
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range="Leads!A:A",
            ).execute()

            rows = result.get("values", [])
            row_num = None
            for i, row in enumerate(rows):
                if row and row[0] == url:
                    row_num = i + 2  # +2 for header row and 1-indexing
                    break

            if not row_num:
                return {"status": "error", "reason": "lead_not_found"}

            # Update status and notes columns (E=5, F=6)
            body = {"values": [[status, notes]]}
            self.service.spreadsheets().values().update(
                spreadsheetId=self.sheet_id,
                range=f"Leads!F{row_num}:G{row_num}",
                valueInputOption="RAW",
                body=body,
            ).execute()

            return {"status": "success", "url": url}
        except Exception as e:
            return {"status": "error", "error": str(e)}


def push_leads_to_crm(leads: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Convenience function to push leads."""
    bridge = SheetsBridge()
    return bridge.push_leads(leads)


def pull_leads_from_crm() -> List[Dict[str, Any]]:
    """Convenience function to pull leads."""
    bridge = SheetsBridge()
    return bridge.pull_leads()