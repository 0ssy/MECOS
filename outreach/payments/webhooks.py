"""
MECOS Outreach - PayPal Webhook Handler
Verifies and processes PayPal webhook events (IPN-style).
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime
from typing import Any, Dict, Optional

from loguru import logger
from config import settings
from outreach.payments.paypal_client import PayPalClient


class PayPalWebhookHandler:
    def __init__(self, payment_ledger=None):
        from outreach.payments.payment_ledger import PaymentLedger
        self.payment_ledger = payment_ledger or PaymentLedger()
        self.webhook_id = getattr(settings, "PAYPAL_WEBHOOK_ID", "")
        self.client_secret = getattr(settings, "PAYPAL_CLIENT_SECRET", "")

    def verify_signature(self, headers: Dict[str, str], body_bytes: bytes) -> bool:
        if not self.webhook_id:
            logger.warning("PayPal webhook ID not set — skipping signature verification")
            return True

        transmission_id = headers.get("PayPal-Transmission-Id", "")
        transmission_time = headers.get("PayPal-Transmission-Time", "")
        cert_url = headers.get("PayPal-Cert-Url", "")
        auth_algo = headers.get("PayPal-Auth-Algo", "")
        transmission_sig = headers.get("PayPal-Transmission-Sig", "")

        if not all([transmission_id, transmission_time, cert_url, auth_algo, transmission_sig]):
            logger.error("Missing PayPal webhook headers")
            return False

        access_token = self._get_access_token()
        if not access_token:
            logger.error("Failed to get PayPal access token for webhook verification")
            return False

        base = PayPalClient.BASE_URLS.get(getattr(settings, "PAYPAL_MODE", "sandbox"), PayPalClient.BASE_URLS["sandbox"])
        verify_url = f"{base}/v1/notifications/verify-webhook-signature"
        payload = {
            "auth_algo": auth_algo,
            "cert_url": cert_url,
            "transmission_id": transmission_id,
            "transmission_sig": transmission_sig,
            "transmission_time": transmission_time,
            "webhook_id": self.webhook_id,
            "webhook_event": json.loads(body_bytes.decode()),
        }

        try:
            import urllib.request
            req = urllib.request.Request(
                verify_url,
                data=json.dumps(payload).encode(),
                method="POST",
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())
                verified = result.get("verification_status") == "SUCCESS"
                if not verified:
                    logger.error(f"PayPal webhook verification failed: {result}")
                return verified
        except Exception as e:
            logger.error(f"PayPal webhook verification error: {e}")
            return False

    def _get_access_token(self) -> Optional[str]:
        client_id = getattr(settings, "PAYPAL_CLIENT_ID", "")
        client_secret = getattr(settings, "PAYPAL_CLIENT_SECRET", "")
        if not client_id:
            return None

        import base64
        import urllib.request
        auth_str = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        url = f"{PayPalClient.BASE_URLS.get(getattr(settings, 'PAYPAL_MODE', 'sandbox'), PayPalClient.BASE_URLS['sandbox'])}/v1/oauth2/token"
        data = "grant_type=client_credentials".encode()
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Authorization", f"Basic {auth_str}")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode())
                return body.get("access_token")
        except Exception as e:
            logger.error(f"Failed to get PayPal access token: {e}")
            return None

    def process_event(self, event_body: Dict[str, Any]) -> Dict[str, Any]:
        event_type = event_body.get("event_type", "")
        event_id = event_body.get("id", "")
        resource = event_body.get("resource", {})

        logger.info(f"Processing PayPal webhook: {event_type} ({event_id})")

        if event_type == "PAYMENT.CAPTURE.COMPLETED":
            capture_id = resource.get("id", "")
            amount = float(resource.get("amount", {}).get("value", 0))
            currency = resource.get("amount", {}).get("currency_code", "USD")
            payer_email = resource.get("payer", {}).get("email_address", "")
            captured_at = resource.get("create_time", "")
            invoice_id = resource.get("invoice_id", "") or resource.get("custom_id", "")

            result = self.payment_ledger.mark_completed(
                paypal_capture_id=capture_id,
                amount=amount,
                currency=currency,
                payer_email=payer_email,
                captured_at=captured_at,
            )
            if result:
                return {"status": "ok", "action": "payment_completed", "invoice_id": invoice_id}
            return {"status": "error", "message": "no pending invoice matched"}

        elif event_type == "PAYMENT.CAPTURE.DENIED":
            return self._handle_failure(resource, "denied")

        elif event_type == "PAYMENT.CAPTURE.REFUNDED":
            return self._handle_refund(resource)

        elif event_type == "CHECKOUT.ORDER.APPROVED":
            order_id = resource.get("id", "")
            payer_email = resource.get("payer", {}).get("email_address", "")
            logger.info(f"PayPal order approved: {order_id} by {payer_email}")
            return {"status": "ok", "action": "order_approved", "order_id": order_id}

        else:
            logger.info(f"Unhandled PayPal event type: {event_type}")
            return {"status": "ignored", "event_type": event_type}

    def _handle_failure(self, resource: Dict, reason: str) -> Dict[str, Any]:
        invoice_id = resource.get("invoice_id", "") or resource.get("custom_id", "")
        if invoice_id:
            self.payment_ledger.mark_failed(invoice_id, reason)
        return {"status": "ok", "action": "payment_failed", "invoice_id": invoice_id}

    def _handle_refund(self, resource: Dict) -> Dict[str, Any]:
        capture_id = resource.get("id", "")
        for p in self.payment_ledger.payments:
            if p.get("paypal_capture_id") == capture_id:
                p["status"] = PaymentLedger.STATUS_REFUNDED
                p["updated_at"] = datetime.now().isoformat()
                self.payment_ledger._save()
                logger.info(f"Payment refunded: {p.get('invoice_id')} capture {capture_id}")
                return {"status": "ok", "action": "payment_refunded", "invoice_id": p.get("invoice_id")}
        return {"status": "error", "message": "capture not found for refund"}
