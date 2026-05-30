from __future__ import annotations

from datetime import datetime
from typing import List, Optional
import logging

from .weekly_review_generator import SystemImprovement

logger = logging.getLogger(__name__)


class ReportingScheduler:
    def __init__(
        self,
        daily_generator,
        weekly_generator,
        dispatcher,
        daily_hour: int = 17,
        weekly_day: int = 4,
        weekly_hour: int = 18,
    ):
        self.daily_generator = daily_generator
        self.weekly_generator = weekly_generator
        self.dispatcher = dispatcher
        self.daily_hour = int(daily_hour)
        self.weekly_day = int(weekly_day)
        self.weekly_hour = int(weekly_hour)
        self.last_daily_date: Optional[str] = None
        self.last_weekly_key: Optional[str] = None

    def tick(self, discoveries: Optional[List[str]] = None, improvements: Optional[List[SystemImprovement]] = None) -> None:
        now = datetime.now()
        date_key = now.strftime("%Y-%m-%d")
        week_key = f"{now.strftime('%Y')}-W{now.strftime('%W')}"

        if now.hour >= self.daily_hour and self.last_daily_date != date_key:
            report = self.daily_generator.generate_report(date=date_key, discoveries=discoveries or [])
            self.daily_generator.save_report(report)
            self.dispatcher.send_alert(
                title=f"Daily PnL Report ({date_key})",
                message=self.daily_generator.format_markdown(report),
            )
            self.last_daily_date = date_key
            logger.info(f"Daily report dispatched for {date_key}")

        if now.weekday() == self.weekly_day and now.hour >= self.weekly_hour and self.last_weekly_key != week_key:
            review = self.weekly_generator.generate_review(
                week_end_date=date_key,
                discoveries=discoveries or [],
                improvements=improvements or [],
            )
            self.weekly_generator.save_review(review)
            self.dispatcher.send_alert(
                title=f"Weekly Review ({week_key})",
                message=self.weekly_generator.format_markdown(review),
            )
            self.last_weekly_key = week_key
            logger.info(f"Weekly review dispatched for {week_key}")
