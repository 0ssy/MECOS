"""
MECOS Outreach - PayPal Orders API Client
Wraps PayPal REST API v2 for creating and capturing payment orders.
"""
from __future__ import annotations

import base64
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from loguru import logger
from config import settings


class PayPalClient:
    BASE_URLS = {
        "sandbox": "https://api-m.sandbox.paypal.com",
        "live": "https://api-m.paypal.com",
    }

    def __init__(self):
        self.mode = getattr(settings, "PAYPAL_MODE", "sandbox")
        self.client_id = getattr(settings, "PAYPAL_CLIENT_ID", "")
        self.client_secret = getattr(settings, "PAYPAL_CLIENT_SECRET", "")
        self.webhook_id = getattr(settings, "PAYPAL_WEBHOOK_ID", "")
        self.return_url = getattr(settings, "PAYPAL_RETURN_URL", "http://localhost:8080/payment/success")
        self.cancel_url = getattr(settings, "PAYPAL_CANCEL_URL", "http://localhost:8080/payment/cancel")

        self.base_url = self.BASE_URLS.get(self.mode, self.BASE_URLS["sandbox"])
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

        if not self.client_id or not self.client_secret:
            logger.warning("PayPalClient: missing PAYPAL_CLIENT_ID or PAYPAL_CLIENT_SECRET")

    def _get_access_token(self) -> Optional[str]:
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        auth_str = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        url = f"{self.base_url}/v1/oauth2/token"
        data = "grant_type=client_credentials".encode()

        req = urllib_request.Request(url, data=data, method="POST")
        req.add_header("Authorization", f"Basic {auth_str}")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        try:
            with urllib_request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode())
                self._access_token = body.get("access_token")
                expires_in = int(body.get("expires_in", 3600))
                self._token_expires_at = time.time() + expires_in - 300
                return self._access_token
        except Exception as e:
            logger.error(f"PayPal auth failed: {e}")
            return None

    def _api_call(self, method: str, path: str, body: Optional[Dict] = None) -> Dict[str, Any]:
        token = self._get_access_token()
        if not token:
            return {"error": "auth_failed"}

        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode() if body else None
        req = urllib_request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/json")
        req.add_header("PayPal-Request-Id", body.get("invoice_id", f"inv_{int(time.time())}") if body else "")

        try:
            with urllib_request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except HTTPError as e:
            err_body = e.read().decode()
            logger.error(f"PayPal API {method} {path} failed: {e.code} {err_body}")
            return {"error": str(e.code), "details": err_body}
        except Exception as e:
            logger.error(f"PayPal API {method} {path} error: {e}")
            return {"error": str(e)}

    def create_order(self, invoice_id: str, amount: float, currency: str = "USD",
                     description: str = "", client_email: str = "") -> Dict[str, Any]:
        if not self.client_id:
            return {"error": "paypal_not_configured"}

        unit_amount = f"{amount:.2f}"
        order_body = {
            "intent": "CAPTURE",
            "invoice_id": invoice_id,
            "purchase_units": [
                {
                    "reference_id": invoice_id,
                    "description": description or f"MECOS Automation Invoice {invoice_id}",
                    "custom_id": client_email or "",
                    "amount": {
                        "currency_code": currency,
                        "value": unit_amount,
                    },
                }
            ],
            "application_context": {
                "brand_name": "MECOS Automation Agency",
                "locale": "en-US",
                "landing_page": "BILLING",
                "user_action": "PAY_NOW",
                "return_url": self.return_url,
                "cancel_url": self.cancel_url,
            },
        }

        result = self._api_call("POST", "/v2/checkout/orders", order_body)
        if "id" in result:
            links = {link["rel"]: link["href"] for link in result.get("links", [])}
            return {
                "order_id": result["id"],
                "status": result.get("status", "CREATED"),
                "checkout_url": links.get("approve", ""),
                "amount": amount,
                "currency": currency,
                "invoice_id": invoice_id,
                "created_at": datetime.now().isoformat(),
            }
        return result

    def capture_order(self, paypal_order_id: str) -> Dict[str, Any]:
        result = self._api_call("POST", f"/v2/checkout/orders/{paypal_order_id}/capture")
        if "purchase_units" in result:
            pu = result["purchase_units"][0]
            capture = pu.get("payments", {}).get("captures", [{}])[0]
            return {
                "order_id": result["id"],
                "status": result.get("status"),
                "capture_id": capture.get("id", ""),
                "amount": capture.get("amount", {}).get("value", "0"),
                "currency": capture.get("amount", {}).get("currency_code", "USD"),
                "captured_at": capture.get("create_time", ""),
                "payer_email": result.get("payer", {}).get("email_address", ""),
            }
        return result

    def get_order(self, paypal_order_id: str) -> Dict[str, Any]:
        result = self._api_call("GET", f"/v2/checkout/orders/{paypal_order_id}")
        if "id" in result:
            status = result.get("status")
            pu = result.get("purchase_units", [{}])[0]
            return {
                "order_id": result["id"],
                "status": status,
                "amount": pu.get("amount", {}).get("value", "0"),
                "currency": pu.get("amount", {}).get("currency_code", "USD"),
                "invoice_id": pu.get("invoice_id", ""),
                "payer_email": result.get("payer", {}).get("email_address", ""),
            }
        return result
