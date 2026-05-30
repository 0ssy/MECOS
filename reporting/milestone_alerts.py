"""
MilestoneAlertSystem — Real-time Milestone Achievement Alerts (MECOS v3.0 Phase 2)

Detects when trading goals are reached and sends alerts via multiple channels
(email, Slack, Discord, in-app notifications).

Location: reporting/milestone_alerts.py
"""

import json
import smtplib
from datetime import datetime
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import logging

logger = logging.getLogger(__name__)


@dataclass
class MilestoneEvent:
    """Represents a milestone achievement."""
    milestone_amount: float
    reached_at: str
    current_equity: float
    days_to_reach: int
    progress_percent: float
    best_day_pnl: float
    win_streak: int
    most_profitable_strategy: str


class AlertDispatcher:
    """Send alerts via multiple channels."""
    
    def __init__(self):
        """Initialize alert dispatcher."""
        self.channels = {}
        logger.info("AlertDispatcher initialized")
    
    def register_email(
        self,
        smtp_server: str,
        smtp_port: int,
        sender_email: str,
        sender_password: str,
    ) -> None:
        """Register email channel."""
        self.channels["email"] = {
            "type": "email",
            "smtp_server": smtp_server,
            "smtp_port": smtp_port,
            "sender_email": sender_email,
            "sender_password": sender_password,
        }
        logger.info(f"Email channel registered: {sender_email}")
    
    def register_slack(self, webhook_url: str) -> None:
        """Register Slack channel."""
        self.channels["slack"] = {
            "type": "slack",
            "webhook_url": webhook_url,
        }
        logger.info("Slack channel registered")
    
    def register_discord(self, webhook_url: str) -> None:
        """Register Discord channel."""
        self.channels["discord"] = {
            "type": "discord",
            "webhook_url": webhook_url,
        }
        logger.info("Discord channel registered")
    
    def register_callback(self, name: str, callback: Callable) -> None:
        """Register custom callback."""
        self.channels[name] = {
            "type": "callback",
            "callback": callback,
        }
        logger.info(f"Callback channel registered: {name}")
    
    def send_alert(
        self,
        title: str,
        message: str,
        channels: Optional[List[str]] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, bool]:
        """
        Send alert to specified channels.
        
        Args:
            title: Alert title
            message: Alert message
            channels: List of channels to send to (if None, sends to all)
            metadata: Additional metadata
        
        Returns:
            Dictionary of {channel: success}
        """
        if channels is None:
            channels = list(self.channels.keys())
        
        results = {}
        
        for channel_name in channels:
            if channel_name not in self.channels:
                logger.warning(f"Channel not registered: {channel_name}")
                results[channel_name] = False
                continue
            
            channel = self.channels[channel_name]
            
            try:
                if channel["type"] == "email":
                    results[channel_name] = self._send_email(channel, title, message, metadata)
                elif channel["type"] == "slack":
                    results[channel_name] = self._send_slack(channel, title, message, metadata)
                elif channel["type"] == "discord":
                    results[channel_name] = self._send_discord(channel, title, message, metadata)
                elif channel["type"] == "callback":
                    results[channel_name] = self._send_callback(channel, title, message, metadata)
                else:
                    logger.warning(f"Unknown channel type: {channel['type']}")
                    results[channel_name] = False
            
            except Exception as e:
                logger.error(f"Failed to send alert to {channel_name}: {e}")
                results[channel_name] = False
        
        return results
    
    def _send_email(
        self,
        channel: Dict,
        title: str,
        message: str,
        metadata: Optional[Dict],
    ) -> bool:
        """Send email alert."""
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"🎉 {title}"
            msg["From"] = channel["sender_email"]
            msg["To"] = channel["sender_email"]  # Send to self
            
            # Plain text version
            text = f"{title}\n\n{message}"
            
            # HTML version
            html = f"""
            <html>
                <body>
                    <h2>{title}</h2>
                    <p>{message}</p>
                    {self._format_metadata_html(metadata) if metadata else ""}
                    <p style="color: #999; font-size: 12px;">
                        Sent at {datetime.now().isoformat()}
                    </p>
                </body>
            </html>
            """
            
            part1 = MIMEText(text, "plain")
            part2 = MIMEText(html, "html")
            
            msg.attach(part1)
            msg.attach(part2)
            
            # Send
            with smtplib.SMTP_SSL(channel["smtp_server"], channel["smtp_port"]) as server:
                server.login(channel["sender_email"], channel["sender_password"])
                server.sendmail(
                    channel["sender_email"],
                    channel["sender_email"],
                    msg.as_string(),
                )
            
            logger.info(f"Email alert sent: {title}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    def _send_slack(
        self,
        channel: Dict,
        title: str,
        message: str,
        metadata: Optional[Dict],
    ) -> bool:
        """Send Slack alert."""
        try:
            payload = {
                "text": f"🎉 {title}",
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"🎉 {title}",
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": message,
                        },
                    },
                ]
            }
            
            if metadata:
                fields = []
                for key, value in metadata.items():
                    fields.append({
                        "type": "mrkdwn",
                        "text": f"*{key}*\n{value}",
                    })
                
                if fields:
                    payload["blocks"].append({
                        "type": "section",
                        "fields": fields,
                    })
            
            response = requests.post(channel["webhook_url"], json=payload)
            response.raise_for_status()
            
            logger.info(f"Slack alert sent: {title}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False
    
    def _send_discord(
        self,
        channel: Dict,
        title: str,
        message: str,
        metadata: Optional[Dict],
    ) -> bool:
        """Send Discord alert."""
        try:
            embed = {
                "title": f"🎉 {title}",
                "description": message,
                "color": 3066993,  # Green
                "timestamp": datetime.now().isoformat(),
            }
            
            if metadata:
                fields = []
                for key, value in metadata.items():
                    fields.append({
                        "name": key,
                        "value": str(value),
                        "inline": True,
                    })
                
                embed["fields"] = fields
            
            payload = {
                "embeds": [embed],
            }
            
            response = requests.post(channel["webhook_url"], json=payload)
            response.raise_for_status()
            
            logger.info(f"Discord alert sent: {title}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send Discord alert: {e}")
            return False
    
    def _send_callback(
        self,
        channel: Dict,
        title: str,
        message: str,
        metadata: Optional[Dict],
    ) -> bool:
        """Send via custom callback."""
        try:
            callback = channel["callback"]
            callback(title, message, metadata)
            logger.info(f"Callback alert sent: {title}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send callback alert: {e}")
            return False
    
    def _format_metadata_html(self, metadata: Dict) -> str:
        """Format metadata as HTML table."""
        if not metadata:
            return ""
        
        rows = "".join(
            f"<tr><td><strong>{k}</strong></td><td>{v}</td></tr>"
            for k, v in metadata.items()
        )
        
        return f"""
        <table style="border-collapse: collapse; margin-top: 20px;">
            {rows}
        </table>
        """


class MilestoneAlertSystem:
    """
    Detect and alert on milestone achievements.
    
    Responsibilities:
    - Monitor equity against milestones
    - Trigger alerts when milestones reached
    - Format milestone notifications
    - Dispatch via multiple channels
    """
    
    def __init__(
        self,
        performance_tracker,
        alert_dispatcher: AlertDispatcher,
        milestones: Optional[List[float]] = None,
    ):
        """
        Initialize MilestoneAlertSystem.
        
        Args:
            performance_tracker: PerformanceTracker instance
            alert_dispatcher: AlertDispatcher instance
            milestones: List of milestone amounts (if None, uses tracker's milestones)
        """
        self.tracker = performance_tracker
        self.dispatcher = alert_dispatcher
        self.milestones = milestones or performance_tracker.milestones
        self.reached_milestones = set()
        
        logger.info(f"MilestoneAlertSystem initialized")
        logger.info(f"  Milestones: {self.milestones}")
    
    def check_milestones(self) -> Optional[MilestoneEvent]:
        """
        Check if any milestone has been reached.
        
        Returns:
            MilestoneEvent if milestone reached, None otherwise
        """
        current_equity = self.tracker.current_equity
        
        for milestone in self.milestones:
            if current_equity >= milestone and milestone not in self.reached_milestones:
                self.reached_milestones.add(milestone)
                
                # Create event
                event = self._create_milestone_event(milestone)
                
                # Send alerts
                self._send_milestone_alerts(event)
                
                return event
        
        return None
    
    def _create_milestone_event(self, milestone_amount: float) -> MilestoneEvent:
        """Create milestone event with metadata."""
        progress = self.tracker.get_progress_to_goal()
        metrics = self.tracker.get_performance_metrics()
        
        # Get best day and win streak
        all_trades = self.tracker.get_all_trades()
        best_day_pnl = max(
            (sum(t.pnl for t in all_trades if t.timestamp.startswith(d))
             for d in set(t.timestamp[:10] for t in all_trades)),
            default=0,
        )
        
        # Calculate win streak
        win_streak = 0
        for trade in reversed(all_trades):
            if trade.pnl > 0:
                win_streak += 1
            else:
                break
        
        # Most profitable strategy
        strategy_pnl = {}
        for trade in all_trades:
            if trade.strategy not in strategy_pnl:
                strategy_pnl[trade.strategy] = 0
            strategy_pnl[trade.strategy] += trade.pnl
        
        most_profitable_strategy = max(strategy_pnl, key=strategy_pnl.get) if strategy_pnl else "unknown"
        
        event = MilestoneEvent(
            milestone_amount=milestone_amount,
            reached_at=datetime.now().isoformat(),
            current_equity=self.tracker.current_equity,
            days_to_reach=progress.get("days_to_goal", 0),
            progress_percent=progress.get("progress_percent", 0),
            best_day_pnl=best_day_pnl,
            win_streak=win_streak,
            most_profitable_strategy=most_profitable_strategy,
        )
        
        return event
    
    def _send_milestone_alerts(self, event: MilestoneEvent) -> None:
        """Send milestone alerts via all channels."""
        title = f"MILESTONE REACHED: ${event.milestone_amount:,.0f}! 🎉"
        
        message = f"""
MECOS has reached ${event.milestone_amount:,.0f} in paper trading!

**Progress**: {event.progress_percent:.1f}% of goal achieved
**Time to milestone**: {event.days_to_reach} days
**Best trading day**: ${event.best_day_pnl:+,.2f}
**Current win streak**: {event.win_streak} trades
**Most profitable strategy**: {event.most_profitable_strategy}
"""
        
        metadata = {
            "Milestone": f"${event.milestone_amount:,.0f}",
            "Current Equity": f"${event.current_equity:,.0f}",
            "Progress": f"{event.progress_percent:.1f}%",
            "Days to Reach": event.days_to_reach,
            "Best Day": f"${event.best_day_pnl:+,.2f}",
            "Win Streak": f"{event.win_streak} trades",
            "Top Strategy": event.most_profitable_strategy,
        }
        
        self.dispatcher.send_alert(title, message, metadata=metadata)
        
        logger.info(f"Milestone alerts sent for ${event.milestone_amount:,.0f}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    # Example usage
    dispatcher = AlertDispatcher()
    
    # Register channels
    dispatcher.register_callback(
        "console",
        lambda title, msg, meta: print(f"\n{title}\n{msg}\n{json.dumps(meta, indent=2)}")
    )
    
    # Mock tracker
    class MockTracker:
        current_equity = 30000
        milestones = [10000, 20000, 30000, 40000, 50000, 60000]
        
        def get_progress_to_goal(self):
            return {
                "current_equity": 30000,
                "goal_equity": 60000,
                "progress_percent": 50,
                "days_to_goal": 7,
            }
        
        def get_performance_metrics(self):
            from performance_tracker import PerformanceMetrics
            return PerformanceMetrics(
                sharpe_ratio=1.45,
                max_drawdown=0.032,
                win_rate=0.625,
                profit_factor=2.14,
                total_return=0.5,
                total_trades=100,
                avg_trade_pnl=150,
            )
        
        def get_all_trades(self):
            from performance_tracker import Trade
            from datetime import datetime, timedelta
            
            trades = []
            for i in range(100):
                trades.append(Trade(
                    symbol="BTC/USD",
                    entry_price=65000,
                    exit_price=65100,
                    quantity=1,
                    pnl=100 if i % 3 != 0 else -50,
                    timestamp=(datetime.now() - timedelta(days=i)).isoformat(),
                    trade_type="BUY",
                    strategy="momentum",
                    confidence=0.85,
                ))
            
            return trades
    
    tracker = MockTracker()
    system = MilestoneAlertSystem(tracker, dispatcher)
    
    event = system.check_milestones()
    if event:
        print(f"\n✓ Milestone event created: {event}")
