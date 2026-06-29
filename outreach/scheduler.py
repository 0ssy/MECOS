"""
MECOS Outreach - Scheduler
Decoupled daily batch trigger that orchestrates outreach cycles
and respects CEO circuit breakers.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from ceo_agent import CeoAgent
from outreach.delivery_agent import DeliveryAgent
from outreach.outreach_agent import OutreachAgent


class OutreachScheduler:
    def __init__(
        self,
        outreach_agent: OutreachAgent,
        ceo_agent: CeoAgent,
        delivery_agent: Optional[DeliveryAgent] = None,
        batch_time: str = "08:00",
        daily_limit: Optional[int] = None,
        hourly_limit: Optional[int] = None,
    ):
        self.outreach_agent = outreach_agent
        self.ceo_agent = ceo_agent
        self.delivery_agent = delivery_agent or DeliveryAgent()
        self.batch_hour, self.batch_minute = [int(x) for x in batch_time.split(":")]
        self.daily_limit = daily_limit or 50
        self.hourly_limit = hourly_limit or 20
        self.metrics_path = Path("data/outreach/daily_metrics.jsonl")
        self.metrics_path.parent.mkdir(parents=True, exist_ok=True)
        self._task: Optional[asyncio.Task] = None
        self._sent_timestamps: List[datetime] = []
        self._last_batch_date: Optional[str] = None

    def start(self) -> None:
        if not self.outreach_agent.enabled:
            logger.info("Scheduler: outreach disabled, not starting")
            return
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "Outreach scheduler started (batch at {:02d}:{:02d}, {}/day target)",
            self.batch_hour,
            self.batch_minute,
            self.daily_limit,
        )

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_loop(self) -> None:
        while True:
            now = datetime.now()
            target = now.replace(
                hour=self.batch_hour, minute=self.batch_minute, second=0, microsecond=0
            )
            if now >= target:
                target += timedelta(days=1)

            seconds_until_batch = (target - now).total_seconds()
            if seconds_until_batch > 0:
                logger.info("Scheduler: next batch in {:.1f} hours", seconds_until_batch / 3600)
                try:
                    await asyncio.sleep(seconds_until_batch)
                except asyncio.CancelledError:
                    return

            await self._run_batch()

    async def _run_batch(self) -> Dict[str, Any]:
        today = datetime.now().date().isoformat()
        if self._last_batch_date == today:
            logger.info("Scheduler: batch already ran today ({})", today)
            return {"status": "skipped", "reason": "already_ran_today"}

        if self.ceo_agent.outreach_paused or self.ceo_agent.send_paused:
            logger.warning("Scheduler: CEO circuit breaker active, skipping batch")
            return {"status": "skipped", "reason": "circuit_breaker_active"}

        # Time gate: no sends before 8 AM
        now = datetime.now()
        if now.hour < 8:
            logger.info("Scheduler: waiting for 8 AM (current time: {:02d}:{:02d})", now.hour, now.minute)
            return {"status": "waiting", "reason": "before_8am"}

        logger.info("Scheduler: starting daily batch for {}", today)

        metrics: Dict[str, Any] = {
            "date": today,
            "started_at": datetime.now().isoformat(),
            "drafts_created": 0,
            "auto_sent": 0,
            "flagged_review": 0,
            "rejected": 0,
            "skipped_icp": 0,
        }

        try:
            cycles_run = 0
            max_cycles = 20
            while cycles_run < max_cycles:
                if self._count_last_hour_sends() >= self.hourly_limit:
                    logger.warning("Scheduler: hourly send limit reached, pausing sends")
                    break

                result = await self.outreach_agent.run_cycle()
                cycles_run += 1

                drafts = result.get("drafts", {})
                metrics["drafts_created"] += drafts.get("drafts_created", 0)
                metrics["skipped_icp"] += drafts.get("skipped_icp", 0)

                approval = await self.ceo_agent.approve_drafts()
                auto_send = approval.get("auto_send", [])
                flag_review = approval.get("flag_review", [])
                reject = approval.get("reject", [])

                metrics["flagged_review"] += len(flag_review)
                metrics["rejected"] += len(reject)

                # Send all manually approved drafts (status=approved_send)
                approved_drafts = self.delivery_agent.list_approved_for_send()
                for draft in approved_drafts:
                    if self._can_send():
                        if self.delivery_agent.send_draft(draft):
                            metrics["auto_sent"] += 1
                            self._record_send()
                    else:
                        break

                total_processed = (
                    metrics["auto_sent"] + metrics["flagged_review"] + metrics["rejected"]
                )
                if total_processed >= self.daily_limit:
                    break

            self._save_metrics(metrics)
            self._last_batch_date = today

            logger.info(
                "Scheduler batch: {} drafts, {} sent, {} flagged, {} rejected, {} skipped_icp",
                metrics["drafts_created"],
                metrics["auto_sent"],
                metrics["flagged_review"],
                metrics["rejected"],
                metrics["skipped_icp"],
            )

            return {"status": "ok", **metrics}

        except Exception as exc:
            logger.error("Scheduler batch failed: {}", exc)
            metrics["error"] = str(exc)
            self._save_metrics(metrics)
            self.ceo_agent.consecutive_failures += 1
            return {"status": "error", "error": str(exc)}

    def _can_send(self) -> bool:
        self._sent_timestamps = [
            ts for ts in self._sent_timestamps
            if datetime.now() - ts < timedelta(hours=1)
        ]
        return len(self._sent_timestamps) < self.hourly_limit

    def _count_last_hour_sends(self) -> int:
        one_hour_ago = datetime.now() - timedelta(hours=1)
        return sum(1 for ts in self._sent_timestamps if ts > one_hour_ago)

    def _record_send(self) -> None:
        self._sent_timestamps.append(datetime.now())

    def _save_metrics(self, metrics: Dict[str, Any]) -> None:
        try:
            with open(self.metrics_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(metrics, default=str) + "\n")
        except Exception as exc:
            logger.error("Scheduler: failed to save metrics: {}", exc)

    def get_today_progress(self) -> Dict[str, Any]:
        today = datetime.now().date().isoformat()
        progress = {"date": today, "sent": self._count_last_hour_sends(), "limit": self.daily_limit}
        if self.metrics_path.exists():
            try:
                with open(self.metrics_path, "r", encoding="utf-8") as f:
                    for line in reversed(list(f)):
                        entry = json.loads(line)
                        if entry.get("date") == today:
                            progress.update({
                                "drafts_created": entry.get("drafts_created", 0),
                                "auto_sent": entry.get("auto_sent", 0),
                                "flagged_review": entry.get("flagged_review", 0),
                                "rejected": entry.get("rejected", 0),
                            })
                            break
            except Exception:
                pass
        return progress