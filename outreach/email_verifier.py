"""
MECOS Outreach - Email Verifier
Validates email deliverability before sending.
Checks MX records and blocks disposable/placeholder domains.
"""
from __future__ import annotations

import dns.resolver
import dns.exception
from loguru import logger

DISPOSABLE_DOMAINS = {
    "mailinator.com", "tempmail.com", "guerrillamail.com", "throwaway.email",
    "fakeinbox.com", "temp-mail.org", "dispostable.com", "mailnesia.com",
    "tempail.com", "mohmal.com", "yopmail.com", "sharklasers.com",
    "10minutemail.com", "minuteinbox.com", "tempr.email", "discard.email",
    "fake-email.net", "trashmail.com", "tempinbox.com", "mintemail.com",
}

PLACEHOLDER_DOMAINS = {
    "example.com", "test.com", "placeholder.com", "domain.com",
    "example.org", "example.net",
}

AGGREGATOR_DOMAINS = {
    "upwork.com", "linkedin.com", "reddit.com", "hn.algolia.com",
    "news.ycombinator.com", "indiehackers.com", "gravityflow.io",
    "docparsemagic.com", "timedoctor.com", "techweez.com",
}


def verify_email_deliverable(email: str) -> bool:
    if "@" not in email:
        return False
    domain = email.split("@")[-1].lower()
    if domain in PLACEHOLDER_DOMAINS:
        return False
    if domain in DISPOSABLE_DOMAINS:
        return False
    if domain in AGGREGATOR_DOMAINS:
        return False
    try:
        mx_records = dns.resolver.resolve(domain, 'MX')
        return len(mx_records) > 0
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.Timeout):
        return False


def get_email_confidence(email: str) -> str:
    if not verify_email_deliverable(email):
        return "undeliverable"
    domain = email.split("@")[-1].lower()
    if domain in AGGREGATOR_DOMAINS:
        return "aggregator"
    if domain in PLACEHOLDER_DOMAINS:
        return "placeholder"
    if domain in DISPOSABLE_DOMAINS:
        return "disposable"
    return "deliverable"


def is_business_domain(domain: str) -> bool:
    domain = domain.lower()
    if domain in AGGREGATOR_DOMAINS:
        return False
    if domain in ("localhost", "127.0.0.1"):
        return False
    if domain.endswith(".example.com") or domain == "example.com":
        return False
    return True
