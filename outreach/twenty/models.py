"""
MECOS Outreach - Twenty CRM Data Models
Defines schema mappings between MECOS internal structures and Twenty CRM objects.
"""

import json
from typing import Any, Dict, List, Optional


def contacts_to_dict(contacts: Any) -> Dict[str, List[str]]:
    if isinstance(contacts, dict):
        return {
            "emails": contacts.get("emails", []),
            "phones": contacts.get("phones", []),
            "social": contacts.get("social", []),
        }
    return {"emails": [], "phones": [], "social": []}


def signals_to_dict(signals: Any) -> Dict[str, int]:
    if isinstance(signals, dict):
        return {
            "pain_points": signals.get("pain_points", 0),
            "inefficiency_markers": signals.get("inefficiency_markers", 0),
            "organic_intent": signals.get("organic_intent", 0),
            "revenue_fit": signals.get("revenue_fit", 0),
        }
    return {"pain_points": 0, "inefficiency_markers": 0, "organic_intent": 0, "revenue_fit": 0}


def build_lead_payload(lead: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "url": lead.get("url", ""),
        "domain": lead.get("domain", ""),
        "signals": json.dumps(signals_to_dict(lead.get("signals"))),
        "totalScore": lead.get("total_score", 0),
        "contacts": json.dumps(contacts_to_dict(lead.get("contacts"))),
        "status": lead.get("status", "new"),
        "source": lead.get("source", ""),
        "discoveredAt": lead.get("discovered_at", ""),
    }


def build_brief_payload(
    brief: Dict[str, Any], twenty_lead_id: Optional[str] = None
) -> Dict[str, Any]:
    payload = {
        "url": brief.get("url", ""),
        "painPoints": json.dumps(brief.get("pain_points", [])),
        "persona": brief.get("persona", ""),
        "suggestedPitch": brief.get("suggested_pitch", ""),
        "valueProposition": brief.get("value_proposition", ""),
        "recommendedPackage": json.dumps(brief.get("recommended_package", {})),
        "recommendedFirstTool": brief.get("recommended_first_tool", ""),
        "originalSignals": json.dumps(signals_to_dict(brief.get("original_signals"))),
        "matchedTerms": json.dumps(brief.get("matched_terms", [])),
        "status": brief.get("status", "ready_for_outreach"),
    }
    synthesized_at = brief.get("synthesized_at", "")
    if synthesized_at:
        payload["synthesizedAt"] = synthesized_at
    return payload


def build_draft_payload(
    draft: Dict[str, Any], twenty_brief_id: Optional[str] = None
) -> Dict[str, Any]:
    payload = {
        "draftType": draft.get("type", "email"),
        "subject": draft.get("subject", ""),
        "body": draft.get("body", ""),
        "status": draft.get("status", "pending_review"),
        "recipientEmail": draft.get("recipient_email", ""),
        "paymentLink": draft.get("payment_link", ""),
        "invoiceId": draft.get("invoice_id", ""),
    }
    created_at = draft.get("created_at", "")
    if created_at:
        payload["createdAt"] = created_at
    return payload


def build_payment_payload(
    payment: Dict[str, Any], twenty_lead_id: Optional[str] = None
) -> Dict[str, Any]:
    return {
        "amount": payment.get("amount", 0.0),
        "currencyCode": payment.get("currency", "USD"),
        "source": payment.get("source", ""),
        "status": payment.get("status", "pending"),
        "invoiceId": payment.get("invoice_id", ""),
        "paypalOrderId": payment.get("paypal_order_id", ""),
        "paypalCaptureId": payment.get("paypal_capture_id", ""),
        "clientEmail": payment.get("client_email", ""),
        "description": payment.get("description", ""),
        "createdAt": payment.get("created_at", ""),
    }
