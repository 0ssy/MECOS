"""
MECOS Outreach - Twenty CRM Schema Definitions
Defines the custom object schemas for Twenty CRM integration.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class FieldDef:
    name: str
    type: str
    label: str = ""
    required: bool = False
    options: Optional[List[str]] = None
    relation_to: Optional[str] = None


@dataclass
class ObjectDef:
    name: str
    label_singular: str
    label_plural: str
    fields: List[FieldDef] = field(default_factory=list)


MECOS_LEAD = ObjectDef(
    name="mecosLead",
    label_singular="MECOS Lead",
    label_plural="MECOS Leads",
    fields=[
        FieldDef(name="url", type="TEXT", label="URL", required=True),
        FieldDef(name="domain", type="TEXT", label="Domain", required=True),
        FieldDef(name="signals", type="TEXT", label="Signals (JSON)"),
        FieldDef(name="totalScore", type="NUMBER", label="Total Score"),
        FieldDef(name="contacts", type="TEXT", label="Contacts (JSON)"),
        FieldDef(name="status", type="SELECT", label="Status", required=True, options=["new", "contacted", "responded", "converted", "disqualified"]),
        FieldDef(name="source", type="TEXT", label="Source"),
        FieldDef(name="discoveredAt", type="DATE_TIME", label="Discovered At"),
    ],
)

MECOS_LEAD_BRIEF = ObjectDef(
    name="mecosLeadBrief",
    label_singular="MECOS Lead Brief",
    label_plural="MECOS Lead Briefs",
    fields=[
        FieldDef(name="url", type="TEXT", label="URL", required=True),
        FieldDef(name="lead", type="RELATION", label="Lead", relation_to="mecosLead", required=True),
        FieldDef(name="painPoints", type="TEXT", label="Pain Points (JSON)"),
        FieldDef(name="persona", type="TEXT", label="Persona"),
        FieldDef(name="suggestedPitch", type="TEXT", label="Suggested Pitch"),
        FieldDef(name="valueProposition", type="TEXT", label="Value Proposition"),
        FieldDef(name="recommendedPackage", type="TEXT", label="Recommended Package (JSON)"),
        FieldDef(name="recommendedFirstTool", type="TEXT", label="Recommended First Tool"),
        FieldDef(name="originalSignals", type="TEXT", label="Original Signals (JSON)"),
        FieldDef(name="matchedTerms", type="TEXT", label="Matched Terms (JSON)"),
        FieldDef(name="status", type="SELECT", label="Status", required=True, options=["ready_for_outreach", "drafted", "contacted", "responded", "converted", "disqualified"]),
        FieldDef(name="synthesizedAt", type="DATE_TIME", label="Synthesized At"),
    ],
)

MECOS_EMAIL_DRAFT = ObjectDef(
    name="mecosEmailDraft",
    label_singular="MECOS Email Draft",
    label_plural="MECOS Email Drafts",
    fields=[
        FieldDef(name="draftType", type="SELECT", label="Draft Type", required=True, options=["email", "linkedin", "twitter"]),
        FieldDef(name="leadBrief", type="RELATION", label="Lead Brief", relation_to="mecosLeadBrief", required=True),
        FieldDef(name="subject", type="TEXT", label="Subject"),
        FieldDef(name="body", type="TEXT", label="Body", required=True),
        FieldDef(name="status", type="SELECT", label="Status", required=True, options=["pending_review", "approved_send", "rejected", "sent", "skipped_no_email", "skipped_bad_domain", "skipped_low_quality"]),
        FieldDef(name="recipientEmail", type="TEXT", label="Recipient Email"),
        FieldDef(name="paymentLink", type="TEXT", label="Payment Link"),
        FieldDef(name="invoiceId", type="TEXT", label="Invoice ID"),
        FieldDef(name="createdAt", type="DATE_TIME", label="Created At"),
        FieldDef(name="sentAt", type="DATE_TIME", label="Sent At"),
    ],
)

MECOS_PAYMENT = ObjectDef(
    name="mecosPayment",
    label_singular="MECOS Payment",
    label_plural="MECOS Payments",
    fields=[
        FieldDef(name="lead", type="RELATION", label="Lead", relation_to="mecosLead", required=True),
        FieldDef(name="amount", type="NUMBER", label="Amount", required=True),
        FieldDef(name="currencyCode", type="TEXT", label="Currency", required=True),
        FieldDef(name="source", type="TEXT", label="Source", required=True),
        FieldDef(name="status", type="SELECT", label="Status", required=True, options=["pending", "completed", "denied", "refunded", "failed"]),
        FieldDef(name="invoiceId", type="TEXT", label="Invoice ID"),
        FieldDef(name="paypalOrderId", type="TEXT", label="PayPal Order ID"),
        FieldDef(name="paypalCaptureId", type="TEXT", label="PayPal Capture ID"),
        FieldDef(name="clientEmail", type="TEXT", label="Client Email"),
        FieldDef(name="description", type="TEXT", label="Description"),
        FieldDef(name="createdAt", type="DATE_TIME", label="Created At"),
    ],
)

ALL_OBJECTS: List[ObjectDef] = [MECOS_LEAD, MECOS_LEAD_BRIEF, MECOS_EMAIL_DRAFT, MECOS_PAYMENT]
