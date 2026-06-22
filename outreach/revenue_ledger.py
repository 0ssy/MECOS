"""
MECOS Outreach - Revenue Ledger
Tracks deals, invoices, payments, and automatically allocates revenue
to the three profit buckets: 40% ops/hardware, 30% trading reserve, 30% growth/profit.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from config import settings


class RevenueLedger:
    BUCKETS = {
        "ops_hardware": {"pct": 0.40, "purpose": "API costs, cloud infra, hardware fund"},
        "trading_reserve": {"pct": 0.30, "purpose": "Trading capital (paper sim now, live later)"},
        "growth_profit": {"pct": 0.30, "purpose": "Marketing, sales tools, founder take-home"},
    }

    def __init__(self):
        self.save_path = settings.DATA_DIR / "outreach" / "revenue_ledger.json"
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        self.entries: List[Dict[str, Any]] = []
        self.bucket_balances: Dict[str, float] = {k: 0.0 for k in self.BUCKETS}
        self._load()

    def _load(self):
        if self.save_path.exists():
            try:
                data = json.loads(self.save_path.read_text())
                self.entries = data.get("entries", [])
                self.bucket_balances = data.get("bucket_balances", {k: 0.0 for k in self.BUCKETS})
            except Exception as e:
                logger.warning(f"Failed to load revenue ledger: {e}")
                self.entries = []
                self.bucket_balances = {k: 0.0 for k in self.BUCKETS}

    def _save(self):
        data = {
            "entries": self.entries[-200:],
            "bucket_balances": self.bucket_balances,
            "last_updated": datetime.now().isoformat(),
        }
        try:
            self.save_path.write_text(json.dumps(data, default=str, indent=2))
        except Exception as e:
            logger.error(f"Failed to save revenue ledger: {e}")

    def record_payment(self, deal_id: str, amount: float, source: str = "client_payment",
                       description: str = "") -> Dict[str, Any]:
        if amount <= 0:
            raise ValueError("Amount must be positive")

        allocation = {}
        for bucket, info in self.BUCKETS.items():
            alloc_amount = round(amount * info["pct"], 2)
            allocation[bucket] = alloc_amount
            self.bucket_balances[bucket] += alloc_amount

        entry = {
            "deal_id": deal_id,
            "amount": amount,
            "source": source,
            "description": description,
            "allocated_at": datetime.now().isoformat(),
            "allocation": allocation,
            "cumulative_balances": dict(self.bucket_balances),
        }
        self.entries.append(entry)
        self._save()
        logger.info(
            f"Revenue recorded: ${amount:.2f} from {source} | "
            f"Ops=${allocation['ops_hardware']:.2f} | "
            f"Trading=${allocation['trading_reserve']:.2f} | "
            f"Growth=${allocation['growth_profit']:.2f}"
        )
        return entry

    def get_bucket_balances(self) -> Dict[str, Dict[str, Any]]:
        result = {}
        for bucket, info in self.BUCKETS.items():
            result[bucket] = {
                "balance": self.bucket_balances[bucket],
                "percentage": info["pct"],
                "purpose": info["purpose"],
            }
        return result

    def get_total_revenue(self) -> float:
        return sum(self.bucket_balances.values())

    def get_summary(self) -> Dict[str, Any]:
        total = self.get_total_revenue()
        return {
            "total_revenue": total,
            "bucket_balances": self.get_bucket_balances(),
            "transaction_count": len(self.entries),
            "last_transaction": self.entries[-1]["allocated_at"] if self.entries else None,
        }

    def get_recent_transactions(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.entries[-limit:]

    def transfer_between_buckets(self, from_bucket: str, to_bucket: str, amount: float,
                                  reason: str = "") -> bool:
        if from_bucket not in self.bucket_balances or to_bucket not in self.bucket_balances:
            logger.error(f"Invalid bucket names: {from_bucket} -> {to_bucket}")
            return False

        if self.bucket_balances[from_bucket] < amount:
            logger.error(f"Insufficient funds in {from_bucket}: have ${self.bucket_balances[from_bucket]:.2f}")
            return False

        self.bucket_balances[from_bucket] -= amount
        self.bucket_balances[to_bucket] += amount

        entry = {
            "deal_id": f"transfer_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "amount": amount,
            "source": "internal_transfer",
            "description": f"Transfer from {from_bucket} to {to_bucket}. Reason: {reason}",
            "allocated_at": datetime.now().isoformat(),
            "allocation": {from_bucket: -amount, to_bucket: amount},
            "cumulative_balances": dict(self.bucket_balances),
        }
        self.entries.append(entry)
        self._save()
        logger.info(f"Transferred ${amount:.2f} from {from_bucket} to {to_bucket}")
        return True
