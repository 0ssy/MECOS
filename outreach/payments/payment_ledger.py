"""
MECOS Outreach - Payment Ledger
Extends RevenueLedger with PayPal-specific payment tracking,
idempotent webhook updates, and payout/withdrawal records.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from config import settings
from outreach.revenue_ledger import RevenueLedger


class PaymentLedger:
    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"
    STATUS_REFUNDED = "refunded"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"

    def __init__(self):
        self.save_path = settings.DATA_DIR / "outreach" / "payments" / "payment_ledger.json"
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        self.revenue_ledger = RevenueLedger()
        self.payments: List[Dict[str, Any]] = []
        self.withdrawals: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        if self.save_path.exists():
            try:
                data = json.loads(self.save_path.read_text())
                self.payments = data.get("payments", [])
                self.withdrawals = data.get("withdrawals", [])
            except Exception as e:
                logger.warning(f"Failed to load payment ledger: {e}")
                self.payments = []
                self.withdrawals = []

    def _save(self):
        data = {
            "payments": self.payments[-500:],
            "withdrawals": self.withdrawals[-200:],
            "last_updated": datetime.now().isoformat(),
        }
        try:
            self.save_path.write_text(json.dumps(data, default=str, indent=2))
        except Exception as e:
            logger.error(f"Failed to save payment ledger: {e}")

    def create_invoice(self, lead_id: str, amount: float, currency: str = "USD",
                       description: str = "", client_email: str = "") -> Dict[str, Any]:
        invoice_id = f"inv_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{lead_id[:8]}"
        invoice = {
            "invoice_id": invoice_id,
            "lead_id": lead_id,
            "amount": round(amount, 2),
            "currency": currency,
            "description": description,
            "client_email": client_email,
            "status": self.STATUS_PENDING,
            "paypal_order_id": "",
            "paypal_capture_id": "",
            "checkout_url": "",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        self.payments.append(invoice)
        self._save()
        logger.info(f"Invoice created: {invoice_id} ${amount:.2f} {currency} for {client_email or lead_id}")
        return invoice

    def link_paypal_order(self, invoice_id: str, paypal_order_id: str, checkout_url: str) -> bool:
        for p in self.payments:
            if p.get("invoice_id") == invoice_id:
                p["paypal_order_id"] = paypal_order_id
                p["checkout_url"] = checkout_url
                p["updated_at"] = datetime.now().isoformat()
                self._save()
                logger.info(f"Invoice {invoice_id} linked to PayPal order {paypal_order_id}")
                return True
        logger.warning(f"Invoice {invoice_id} not found for PayPal order link")
        return False

    def mark_completed(self, paypal_capture_id: str, amount: float, currency: str = "USD",
                       payer_email: str = "", captured_at: str = "") -> Optional[Dict[str, Any]]:
        for p in self.payments:
            if p.get("paypal_order_id") and not p.get("paypal_capture_id"):
                pass
            if p.get("paypal_capture_id") == paypal_capture_id:
                logger.info(f"Duplicate capture {paypal_capture_id} — idempotent skip")
                return p

        for p in self.payments:
            if p.get("status") == self.STATUS_PENDING and p.get("paypal_order_id"):
                p["status"] = self.STATUS_COMPLETED
                p["paypal_capture_id"] = paypal_capture_id
                p["captured_at"] = captured_at or datetime.now().isoformat()
                p["payer_email"] = payer_email
                p["updated_at"] = datetime.now().isoformat()
                self._save()

                self.revenue_ledger.record_payment(
                    deal_id=p["invoice_id"],
                    amount=p["amount"],
                    source="paypal",
                    description=f"PayPal payment for {p.get('description', 'automation service')}",
                )
                logger.info(f"Payment completed: {p['invoice_id']} ${p['amount']:.2f} via PayPal capture {paypal_capture_id}")
                return p

        logger.warning(f"No pending invoice found for PayPal capture {paypal_capture_id}")
        return None

    def mark_failed(self, invoice_id: str, reason: str = "") -> bool:
        for p in self.payments:
            if p.get("invoice_id") == invoice_id:
                p["status"] = self.STATUS_FAILED
                p["failure_reason"] = reason
                p["updated_at"] = datetime.now().isoformat()
                self._save()
                logger.info(f"Invoice {invoice_id} marked failed: {reason}")
                return True
        return False

    def mark_cancelled(self, invoice_id: str) -> bool:
        for p in self.payments:
            if p.get("invoice_id") == invoice_id:
                p["status"] = self.STATUS_CANCELLED
                p["updated_at"] = datetime.now().isoformat()
                self._save()
                logger.info(f"Invoice {invoice_id} cancelled")
                return True
        return False

    def record_withdrawal(self, amount: float, destination: str, method: str = "paypal_to_bank",
                          fee: float = 0.0, notes: str = "") -> Dict[str, Any]:
        net = round(amount - fee, 2)
        withdrawal = {
            "withdrawal_id": f"wd_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "amount": round(amount, 2),
            "fee": round(fee, 2),
            "net": net,
            "destination": destination,
            "method": method,
            "notes": notes,
            "created_at": datetime.now().isoformat(),
        }
        self.withdrawals.append(withdrawal)
        self._save()
        logger.info(f"Withdrawal recorded: ${net:.2f} net to {destination} via {method}")
        return withdrawal

    def get_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        for p in self.payments:
            if p.get("invoice_id") == invoice_id:
                return p
        return None

    def get_pending_invoices(self) -> List[Dict[str, Any]]:
        return [p for p in self.payments if p.get("status") == self.STATUS_PENDING]

    def get_completed_payments(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [p for p in self.payments if p.get("status") == self.STATUS_COMPLETED][-limit:]

    def get_recent_payments(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.payments[-limit:]

    def get_revenue_summary(self) -> Dict[str, Any]:
        completed = [p for p in self.payments if p.get("status") == self.STATUS_COMPLETED]
        total_collected = sum(p.get("amount", 0) for p in completed)
        pending = [p for p in self.payments if p.get("status") == self.STATUS_PENDING]
        pending_total = sum(p.get("amount", 0) for p in pending)
        return {
            "total_collected": total_collected,
            "pending_total": pending_total,
            "completed_count": len(completed),
            "pending_count": len(pending),
            "total_count": len(self.payments),
            "last_updated": datetime.now().isoformat(),
        }

    def get_withdrawals(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.withdrawals[-limit:]
