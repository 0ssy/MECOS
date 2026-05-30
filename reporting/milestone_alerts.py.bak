from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Callable, Dict, List, Optional
import logging
import requests
import smtplib

logger = logging.getLogger(__name__)


@dataclass
class MilestoneEvent:
    milestone_amount: float
    reached_at: str
    current_equity: float
    days_to_reach: int
    progress_percent: float
    best_day_pnl: float
    win_streak: int
    most_profitable_strategy: str


class AlertDispatcher:
    def __init__(self):
        self.channels: Dict[str, Dict] = {}

    def register_email(self, smtp_server: str, smtp_port: int, sender_email: str, sender_password: str) -> None:
        self.channels["email"] = {
            "type": "email",
            "smtp_server": smtp_server,
            "smtp_port": int(smtp_port),
            "sender_email": sender_email,
            "sender_password": sender_password,
        }

    def register_slack(self, webhook_url: str) -> None:
        self.channels["slack"] = {"type": "slack", "webhook_url": webhook_url}

    def register_discord(self, webhook_url: str) -> None:
        self.channels["discord"] = {"type": "discord", "webhook_url": webhook_url}

    def register_callback(self, name: str, callback: Callable) -> None:
        self.channels[name] = {"type": "callback", "callback": callback}

    def send_alert(
        self,
        title: str,
        message: str,
        channels: Optional[List[str]] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, bool]:
        targets = channels or list(self.channels.keys())
        results: Dict[str, bool] = {}
        for channel_name in targets:
            channel = self.channels.get(channel_name)
            if not channel:
                results[channel_name] = False
                continue
            try:
                if channel["type"] == "email":
                    results[channel_name] = self._send_email(channel, title, message)
                elif channel["type"] == "slack":
                    results[channel_name] = self._send_slack(channel, title, message, metadata)
                elif channel["type"] == "discord":
                    results[channel_name] = self._send_discord(channel, title, message, metadata)
                elif channel["type"] == "callback":
                    results[channel_name] = self._send_callback(channel, title, message, metadata)
                else:
                    results[channel_name] = False
            except Exception as exc:
                logger.error(f"Failed to send alert to {channel_name}: {exc}")
                results[channel_name] = False
        return results

    def _send_email(self, channel: Dict, title: str, message: str) -> bool:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = title
        msg["From"] = channel["sender_email"]
        msg["To"] = channel["sender_email"]
        msg.attach(MIMEText(message, "plain"))
        with smtplib.SMTP_SSL(channel["smtp_server"], channel["smtp_port"]) as server:
            server.login(channel["sender_email"], channel["sender_password"])
            server.sendmail(channel["sender_email"], channel["sender_email"], msg.as_string())
        return True

    def _send_slack(self, channel: Dict, title: str, message: str, metadata: Optional[Dict]) -> bool:
        payload = {"text": f"{title}\n{message}"}
        if metadata:
            payload["text"] = payload["text"] + "\n" + "\n".join(f"{k}: {v}" for k, v in metadata.items())
        response = requests.post(channel["webhook_url"], json=payload, timeout=10)
        response.raise_for_status()
        return True

    def _send_discord(self, channel: Dict, title: str, message: str, metadata: Optional[Dict]) -> bool:
        payload = {"content": f"**{title}**\n{message}"}
        if metadata:
            payload["content"] += "\n" + "\n".join(f"{k}: {v}" for k, v in metadata.items())
        response = requests.post(channel["webhook_url"], json=payload, timeout=10)
        response.raise_for_status()
        return True

    def _send_callback(self, channel: Dict, title: str, message: str, metadata: Optional[Dict]) -> bool:
        callback = channel["callback"]
        callback(title, message, metadata)
        return True


class MilestoneAlertSystem:
    def __init__(self, performance_tracker, alert_dispatcher: AlertDispatcher, milestones: Optional[List[float]] = None):
        self.tracker = performance_tracker
        self.dispatcher = alert_dispatcher
        self.milestones = list(milestones or performance_tracker.milestones)
        self.reached_milestones = set()

    def check_milestones(self) -> Optional[MilestoneEvent]:
        current_equity = float(self.tracker.current_equity)
        for milestone in self.milestones:
            if current_equity < milestone or milestone in self.reached_milestones:
                continue
            self.reached_milestones.add(milestone)
            event = self._create_milestone_event(float(milestone))
            self._send_milestone_alerts(event)
            return event
        return None

    def _create_milestone_event(self, milestone_amount: float) -> MilestoneEvent:
        progress = self.tracker.get_progress_to_goal()
        all_trades = self.tracker.get_all_trades()

        best_day_map: Dict[str, float] = {}
        strategy_pnl: Dict[str, float] = {}
        for trade in all_trades:
            day = str(trade.timestamp)[:10]
            best_day_map[day] = best_day_map.get(day, 0.0) + float(trade.pnl)
            strategy_pnl[trade.strategy] = strategy_pnl.get(trade.strategy, 0.0) + float(trade.pnl)
        best_day_pnl = max(best_day_map.values()) if best_day_map else 0.0
        most_profitable_strategy = max(strategy_pnl, key=strategy_pnl.get) if strategy_pnl else "unknown"

        win_streak = 0
        for trade in reversed(all_trades):
            if float(trade.pnl) > 0:
                win_streak += 1
            else:
                break

        return MilestoneEvent(
            milestone_amount=milestone_amount,
            reached_at=datetime.now().isoformat(),
            current_equity=float(self.tracker.current_equity),
            days_to_reach=int(progress.get("days_to_goal", 0) or 0),
            progress_percent=float(progress.get("progress_percent", 0.0)),
            best_day_pnl=float(best_day_pnl),
            win_streak=win_streak,
            most_profitable_strategy=most_profitable_strategy,
        )

    def _send_milestone_alerts(self, event: MilestoneEvent) -> None:
        title = f"Milestone reached: ${event.milestone_amount:,.0f}"
        message = (
            f"Current equity: ${event.current_equity:,.2f}\n"
            f"Progress: {event.progress_percent:.1f}%\n"
            f"Best day: ${event.best_day_pnl:+,.2f}\n"
            f"Win streak: {event.win_streak}\n"
            f"Top strategy: {event.most_profitable_strategy}"
        )
        metadata = {
            "milestone": f"${event.milestone_amount:,.0f}",
            "current_equity": f"${event.current_equity:,.2f}",
            "progress": f"{event.progress_percent:.1f}%",
            "days_to_reach": event.days_to_reach,
        }
        self.dispatcher.send_alert(title, message, metadata=metadata)
