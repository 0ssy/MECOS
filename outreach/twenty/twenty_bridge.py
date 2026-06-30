"""
MECOS Outreach - Twenty CRM Bridge
GraphQL client for syncing leads, briefs, drafts, and payments to Twenty CRM.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import requests
from loguru import logger

from config import settings
from outreach.twenty.models import (
    build_brief_payload,
    build_draft_payload,
    build_lead_payload,
    build_payment_payload,
)


class TwentyBridge:
    def __init__(self):
        self.enabled = getattr(settings, "TWENTY_CRM_ENABLED", False)
        self.api_url = getattr(settings, "TWENTY_CRM_API_URL", "").rstrip("/")
        self.api_key = getattr(settings, "TWENTY_CRM_API_KEY", "")
        self.graphql_url = f"{self.api_url}/graphql" if self.api_url else ""

        self.session = requests.Session()
        if not self.api_key:
            logger.warning("TwentyBridge: missing TWENTY_CRM_API_KEY")
        self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})
        self.session.headers.update({"Content-Type": "application/json"})

        if not self.api_url:
            logger.warning("TwentyBridge: missing TWENTY_CRM_API_URL")

    def _request(self, query: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
        if not self.enabled:
            return {"data": None, "errors": [{"message": "Twenty CRM disabled"}]}

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            resp = self.session.post(self.graphql_url, json=payload, timeout=30)
            resp.raise_for_status()
            body = resp.json()
            if body.get("errors"):
                logger.error(f"Twenty CRM GraphQL errors: {body['errors']}")
            return body
        except requests.exceptions.RequestException as e:
            logger.error(f"Twenty CRM request failed: {e}")
            return {"data": None, "errors": [{"message": str(e)}]}

    def find_lead_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        query = """
        query FindLead($url: String!) {
          mecosLeads(first: 1) {
            edges {
              node { id url domain }
            }
          }
        }
        """
        result = self._request(query, {"url": url})
        data = result.get("data") or {}
        edges = data.get("mecosLeads", {}).get("edges", [])
        for edge in edges:
            node = edge.get("node", {})
            if node.get("url") == url:
                return node
        return None

    def find_brief_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        query = """
        query FindBrief($url: String!) {
          mecosLeadBriefs(first: 1) {
            edges {
              node { id url }
            }
          }
        }
        """
        result = self._request(query, {"url": url})
        data = result.get("data") or {}
        edges = data.get("mecosLeadBriefs", {}).get("edges", [])
        for edge in edges:
            node = edge.get("node", {})
            if node.get("url") == url:
                return node
        return None

    def find_draft_by_brief_url(
        self, url: str, draft_type: str = "email"
    ) -> List[Dict[str, Any]]:
        query = """
        query FindDrafts($url: String!, $type: String!) {
          mecosEmailDrafts(first: 10) {
            edges {
              node {
                id subject status
                leadBrief {
                  id url
                }
              }
            }
          }
        }
        """
        result = self._request(query, {"url": url, "type": draft_type})
        data = result.get("data") or {}
        matches = []
        for e in data.get("mecosEmailDrafts", {}).get("edges", []):
            node = e.get("node", {})
            lead_brief = node.get("leadBrief") or {}
            if lead_brief.get("url") == url and node.get("type") == draft_type:
                matches.append(node)
        return matches

    def find_payment_by_invoice_id(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        query = """
        query FindPayment($invoiceId: String!) {
          mecosPayments(first: 1) {
            edges {
              node { id invoiceId status }
            }
          }
        }
        """
        result = self._request(query, {"invoiceId": invoice_id})
        data = result.get("data") or {}
        edges = data.get("mecosPayments", {}).get("edges", [])
        for edge in edges:
            node = edge.get("node", {})
            if node.get("invoiceId") == invoice_id:
                return node
        return None

    def sync_lead(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        url = lead.get("url", "")
        if not url:
            return {"status": "skipped", "reason": "no_url"}

        existing = self.find_lead_by_url(url)
        payload = build_lead_payload(lead)

        if existing:
            twenty_id = existing["id"]
            mutation = """
            mutation UpdateLead($id: ID!, $data: MecosLeadUpdateInput!) {
              updateMecosLead(id: $id, data: $data) {
                id url
              }
            }
            """
            result = self._request(mutation, {"id": twenty_id, "data": payload})
            data = result.get("data") or {}
            node = data.get("updateMecosLead")
            if node:
                logger.info(f"Twenty CRM lead updated: {url}")
                return {"status": "updated", "twenty_id": node.get("id")}
            return {"status": "error", "details": result.get("errors")}
        else:
            mutation = """
            mutation CreateLead($data: MecosLeadCreateInput!) {
              createMecosLead(data: $data) {
                id url domain
              }
            }
            """
            result = self._request(mutation, {"data": payload})
            data = result.get("data") or {}
            node = data.get("createMecosLead")
            if node:
                logger.info(f"Twenty CRM lead created: {url}")
                return {"status": "created", "twenty_id": node.get("id")}
            return {"status": "error", "details": result.get("errors")}

    def sync_brief(
        self, brief: Dict[str, Any], twenty_lead_id: Optional[str] = None
    ) -> Dict[str, Any]:
        url = brief.get("url", "")
        if not url:
            return {"status": "skipped", "reason": "no_url"}

        existing = self.find_brief_by_url(url)
        payload = build_brief_payload(brief, twenty_lead_id)

        if existing:
            twenty_id = existing["id"]
            mutation = """
            mutation UpdateBrief($id: ID!, $data: MecosLeadBriefUpdateInput!) {
              updateMecosLeadBrief(id: $id, data: $data) {
                id url
              }
            }
            """
            result = self._request(mutation, {"id": twenty_id, "data": payload})
            node = (result.get("data") or {}).get("updateMecosLeadBrief")
            if node:
                logger.info(f"Twenty CRM brief updated: {url}")
                return {"status": "updated", "twenty_id": node.get("id")}
            return {"status": "error", "details": result.get("errors")}
        else:
            mutation = """
            mutation CreateBrief($data: MecosLeadBriefCreateInput!) {
              createMecosLeadBrief(data: $data) {
                id url domain
              }
            }
            """
            result = self._request(mutation, {"data": payload})
            node = (result.get("data") or {}).get("createMecosLeadBrief")
            if node:
                logger.info(f"Twenty CRM brief created: {url}")
                return {"status": "created", "twenty_id": node.get("id")}
            return {"status": "error", "details": result.get("errors")}

    def sync_draft(
        self, draft: Dict[str, Any], twenty_brief_id: Optional[str] = None
    ) -> Dict[str, Any]:
        subject = draft.get("subject", "")
        if not subject:
            return {"status": "skipped", "reason": "no_subject"}

        brief_url = draft.get("lead_brief", {}).get("url", "")
        existing = (
            self.find_draft_by_brief_url(brief_url, draft.get("type", "email"))
            if brief_url
            else []
        )
        payload = build_draft_payload(draft, twenty_brief_id)

        if existing:
            twenty_id = existing[0]["id"]
            mutation = """
            mutation UpdateDraft($id: ID!, $data: MecosEmailDraftUpdateInput!) {
              updateMecosEmailDraft(id: $id, data: $data) {
                id subject status
              }
            }
            """
            result = self._request(mutation, {"id": twenty_id, "data": payload})
            node = (result.get("data") or {}).get("updateMecosEmailDraft")
            if node:
                logger.info(f"Twenty CRM draft updated: {subject}")
                return {"status": "updated", "twenty_id": node.get("id")}
            return {"status": "error", "details": result.get("errors")}
        else:
            mutation = """
            mutation CreateDraft($data: MecosEmailDraftCreateInput!) {
              createMecosEmailDraft(data: $data) {
                id subject status
              }
            }
            """
            result = self._request(mutation, {"data": payload})
            node = (result.get("data") or {}).get("createMecosEmailDraft")
            if node:
                logger.info(f"Twenty CRM draft created: {subject}")
                return {"status": "created", "twenty_id": node.get("id")}
            return {"status": "error", "details": result.get("errors")}

    def sync_payment(
        self, payment: Dict[str, Any], twenty_lead_id: Optional[str] = None
    ) -> Dict[str, Any]:
        invoice_id = payment.get("invoice_id", "")
        if not invoice_id:
            return {"status": "skipped", "reason": "no_invoice_id"}

        existing = self.find_payment_by_invoice_id(invoice_id)
        payload = build_payment_payload(payment, twenty_lead_id)

        if existing:
            twenty_id = existing["id"]
            mutation = """
            mutation UpdatePayment($id: ID!, $data: MecosPaymentUpdateInput!) {
              updateMecosPayment(id: $id, data: $data) {
                id invoiceId status
              }
            }
            """
            result = self._request(mutation, {"id": twenty_id, "data": payload})
            node = (result.get("data") or {}).get("updateMecosPayment")
            if node:
                logger.info(f"Twenty CRM payment updated: {invoice_id}")
                return {"status": "updated", "twenty_id": node.get("id")}
            return {"status": "error", "details": result.get("errors")}
        else:
            mutation = """
            mutation CreatePayment($data: MecosPaymentCreateInput!) {
              createMecosPayment(data: $data) {
                id invoiceId status
              }
            }
            """
            result = self._request(mutation, {"data": payload})
            node = (result.get("data") or {}).get("createMecosPayment")
            if node:
                logger.info(f"Twenty CRM payment created: {invoice_id}")
                return {"status": "created", "twenty_id": node.get("id")}
            return {"status": "error", "details": result.get("errors")}

    def get_approved_drafts(self, limit: int = 50) -> List[Dict[str, Any]]:
        query = """
        query GetApprovedDrafts($first: Int!) {
          mecosEmailDrafts(
            first: $first
            orderBy: { createdAt: DescNullsFirst }
          ) {
            edges {
              node {
                id subject body
                status
                leadBrief {
                  id url
                  lead { id url }
                  contacts { emails }
                }
              }
            }
          }
        }
        """
        result = self._request(query, {"first": limit})
        data = result.get("data") or {}
        return [e["node"] for e in data.get("mecosEmailDrafts", {}).get("edges", []) if e.get("node", {}).get("status") == "approved_send"]

    def get_leads_by_status(self, status: str, limit: int = 50) -> List[Dict[str, Any]]:
        query = """
        query GetLeadsByStatus($first: Int!) {
          mecosLeads(
            first: $first
            orderBy: { createdAt: DescNullsFirst }
          ) {
            edges {
              node {
                id url domain totalScore contacts status
              }
            }
          }
        }
        """
        result = self._request(query, {"first": limit})
        data = result.get("data") or {}
        nodes = [e["node"] for e in data.get("mecosLeads", {}).get("edges", [])]
        return [n for n in nodes if n.get("status") == status]

    def mark_draft_sent(self, twenty_draft_id: str) -> Dict[str, Any]:
        mutation = """
        mutation MarkDraftSent($id: ID!, $data: MecosEmailDraftUpdateInput!) {
          updateMecosEmailDraft(id: $id, data: $data) {
            id status
          }
        }
        """
        payload = {"status": "sent", "sentAt": time.strftime("%Y-%m-%dT%H:%M:%SZ")}
        result = self._request(mutation, {"id": twenty_draft_id, "data": payload})
        node = (result.get("data") or {}).get("updateMecosEmailDraft")
        if node:
            return {"status": "ok", "draft": node}
        return {"status": "error", "details": result.get("errors")}
