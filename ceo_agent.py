"""
MECOS CEO Agent
Permanent coordinator that monitors system health, manages outreach,
tracks revenue, and coordinates worker agents for stable operation.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from memory_system import MemorySystem
from outreach.ceo_instincts import CeoInstincts
from outreach.outreach_agent import OutreachAgent
from outreach.revenue_ledger import RevenueLedger
from outreach.scanner import OutreachScanner
from tool_orchestrator import ToolOrchestrator


class CeoAgent:
    """
    Permanent CEO-level coordinator for MECOS.
    
    Responsibilities:
    - System health monitoring (memory, trading, outreach)
    - Outreach pipeline management (scan/synth/draft/send throttling)
    - Revenue tracking and ledger oversight
    - Worker coordination and recovery
    - Stability enforcement (rate limits, circuit breakers)
    """
    
    def __init__(self, memory: MemorySystem, tool_orchestrator: Optional[ToolOrchestrator] = None, revenue_ledger: Optional[RevenueLedger] = None):
        self.memory = memory
        self.tool_orchestrator = tool_orchestrator
        self.outreach: Optional[OutreachAgent] = None
        self.revenue_ledger = revenue_ledger or RevenueLedger()
        self.instincts = CeoInstincts()
        
        # CEO state
        self.cycle = 0
        self.last_health_check: Optional[datetime] = None
        self.last_outreach_cycle: Optional[datetime] = datetime.now()
        self.last_revenue_check: Optional[datetime] = None
        self.last_report_date: Optional[str] = None
        self.alert_thresholds = {
            "max_leads_per_hour": int(os.getenv("CEO_MAX_LEADS_HOUR", "50")),
            "max_sends_per_hour": int(os.getenv("CEO_MAX_SENDS_HOUR", "20")),
            "max_revenue_drop_pct": float(os.getenv("CEO_MAX_REVENUE_DROP", "30")),
            "min_memory_experiences": int(os.getenv("CEO_MIN_MEMORIES", "10")),
        }
        
        # Circuit breakers
        self.outreach_paused = False
        self.send_paused = False
        self.consecutive_failures = 0
        
        logger.info("CeoAgent initialized — system overseer active")
    
    def attach_outreach(self, outreach_agent: OutreachAgent):
        """Connect outreach agent for coordination."""
        self.outreach = outreach_agent
        self.instincts.bootstrap_defaults()
        logger.info("CeoAgent attached to OutreachAgent, instincts bootstrapped")
    
    async def run_cycle(self) -> Dict[str, Any]:
        """Run one CEO supervision cycle."""
        self.cycle += 1
        result = {
            "ceo_cycle": self.cycle,
            "timestamp": datetime.now().isoformat(),
            "health": await self._check_health(),
            "outreach": await self._supervise_outreach(),
            "revenue": await self._check_revenue(),
            "actions": [],
        }
        
        weekly = await self._run_weekly_report()
        if weekly:
            result["weekly_report"] = weekly
        
        # Persist CEO state
        await self._store_cycle_state(result)
        
        # Log summary every 10 cycles
        if self.cycle % 10 == 0:
            logger.info(
                "CEO cycle #{} | Health={} | Outreach={} | Revenue=${:.2f}",
                self.cycle,
                result["health"]["status"],
                result["outreach"]["status"],
                result["revenue"]["total"],
            )
        
        return result
    
    async def _check_health(self) -> Dict[str, Any]:
        """Check overall system health."""
        health = {
            "status": "healthy",
            "memory": await self._check_memory_health(),
            "outreach": await self._check_outreach_health(),
            "tools": await self._check_tool_health(),
            "issues": [],
        }
        
        # Aggregate issues
        for component, status in health.items():
            if isinstance(status, dict) and status.get("issues"):
                health["issues"].extend(status["issues"])
        
        if health["issues"]:
            health["status"] = "degraded" if len(health["issues"]) <= 2 else "unhealthy"
        
        self.last_health_check = datetime.now()
        return health
    
    async def _check_memory_health(self) -> Dict[str, Any]:
        """Check memory system health."""
        try:
            stats = await self.memory.get_stats()
            exp_count = stats.get("experience_count", 0)
            issues = []
            if exp_count < self.alert_thresholds["min_memory_experiences"]:
                issues.append(f"Low memory count: {exp_count}")
            return {
                "status": "ok" if not issues else "warn",
                "experience_count": exp_count,
                "short_term_buffer": stats.get("short_term_buffer_size", 0),
                "quality": stats.get("quality", {}),
                "issues": issues,
            }
        except Exception as exc:
            logger.error("Memory health check failed: {}", exc)
            return {"status": "error", "issues": [str(exc)]}
    
    async def _check_outreach_health(self) -> Dict[str, Any]:
        """Check outreach pipeline health."""
        if not self.outreach:
            return {"status": "disabled", "issues": ["Outreach not attached"]}
        
        try:
            summary = self.outreach.get_summary()
            pending = summary.get("pending_drafts", 0)
            leads_queued = summary.get("leads_queued", 0)
            issues = []
            
            if pending > 100:
                issues.append(f"Outbox backlog: {pending} drafts pending")
            if leads_queued > 200:
                issues.append(f"Lead queue too large: {leads_queued}")
            if self.outreach_paused:
                issues.append("Outreach paused by CEO")
            
            return {
                "status": "ok" if not issues else "warn",
                "enabled": summary.get("outreach_enabled", False),
                "pending_drafts": pending,
                "leads_queued": leads_queued,
                "revenue": summary.get("revenue", {}).get("total_revenue", 0),
                "issues": issues,
            }
        except Exception as exc:
            logger.error("Outreach health check failed: {}", exc)
            return {"status": "error", "issues": [str(exc)]}
    
    async def _check_tool_health(self) -> Dict[str, Any]:
        """Check tool orchestrator health."""
        if not self.tool_orchestrator:
            return {"status": "no_orchestrator", "issues": ["ToolOrchestrator not attached"]}
        
        try:
            tools = self.tool_orchestrator.registry.list_tools()
            health = self.tool_orchestrator.mcp_health_check()
            issues = []
            
            disabled_tools = [t.name for t in tools if not getattr(t, 'enabled', True)]
            if disabled_tools:
                issues.append(f"Disabled tools: {len(disabled_tools)}")
            
            return {
                "status": "ok" if not issues else "warn",
                "total_tools": len(tools),
                "mcp_servers": len(health),
                "mcp_running": sum(1 for s in health.values() if s.get("running")),
                "issues": issues,
            }
        except Exception as exc:
            logger.error("Tool health check failed: {}", exc)
            return {"status": "error", "issues": [str(exc)]}
    
    def _check_spam_risk(self) -> Dict[str, Any]:
        """Check outreach engagement metrics and pause if spam risk is high."""
        if not self.outreach or not self.outreach.enabled:
            return {"paused": False}
        
        try:
            from outreach.delivery_agent import DeliveryAgent
            from outreach.reply_monitor import ReplyMonitor
            delivery = DeliveryAgent()
            reply_monitor = ReplyMonitor()
            
            sent_files = list(delivery.sent_dir.glob("*.json"))
            total_sent = len(sent_files)
            send_failed = sum(1 for f in sent_files if json.loads(f.read_text()).get("status") == "send_failed")
            replies = reply_monitor._replies if hasattr(reply_monitor, '_replies') else []
            total_replies = len(replies)
            
            bounce_rate = send_failed / total_sent if total_sent > 0 else 0
            reply_rate = total_replies / total_sent if total_sent > 0 else 0
            
            if total_sent >= 10 and (bounce_rate > 0.05 or reply_rate < 0.01):
                reason = f"bounce_rate={bounce_rate:.1%}, reply_rate={reply_rate:.1%}"
                logger.warning("CEO: Spam risk detected — {}", reason)
                return {"paused": True, "reason": reason, "bounce_rate": bounce_rate, "reply_rate": reply_rate}
            
            return {"paused": False, "bounce_rate": bounce_rate, "reply_rate": reply_rate}
        except Exception as exc:
            logger.debug("Spam risk check failed: {}", exc)
            return {"paused": False}

    async def _supervise_outreach(self) -> Dict[str, Any]:
        """Supervise outreach agent cycles and enforce limits."""
        if not self.outreach or not self.outreach.enabled:
            return {"status": "disabled"}
        
        status = {"status": "ok", "actions": []}
        
        # Check circuit breakers
        if self.outreach_paused:
            status["status"] = "paused"
            status["reason"] = "CEO circuit breaker active"
            return status
        
        # Run outreach cycle if it's time
        now = datetime.now()
        should_run = (
            self.last_outreach_cycle is None
            or (now - self.last_outreach_cycle) >= timedelta(minutes=5)
        )
        
        if should_run:
            try:
                cycle_result = await self.outreach.run_cycle()
                self.last_outreach_cycle = now
                status["last_cycle"] = cycle_result
                
                # Check for failures
                if cycle_result.get("outreach_status") == "error":
                    self.consecutive_failures += 1
                    status["actions"].append("recorded_failure")
                else:
                    self.consecutive_failures = 0
                
                # Circuit breaker: pause after 3 consecutive failures
                if self.consecutive_failures >= 3:
                    self.outreach_paused = True
                    status["actions"].append("circuit_breaker_triggered")
                    logger.warning("CEO: Outreach paused after {} consecutive failures", self.consecutive_failures)
                
                # Spam-risk scoring
                spam_risk = self._check_spam_risk()
                if spam_risk.get("paused"):
                    self.outreach_paused = True
                    status["actions"].append("spam_risk_paused")
                    logger.warning("CEO: Outreach paused due to spam risk: {}", spam_risk.get("reason"))
                
            except Exception as exc:
                logger.error("CEO: Outreach cycle failed: {}", exc)
                self.consecutive_failures += 1
                status["actions"].append("cycle_failed")
        
        return status
    
    async def _run_weekly_report(self) -> Optional[Dict[str, Any]]:
        now = datetime.now()
        today = now.date().isoformat()
        week_label = now.strftime("%Y-W%V")
        if self.last_report_date == week_label:
            return None
        
        if now.weekday() != 0 and self.last_report_date:
            return None
        
        try:
            from outreach.analytics.weekly_report import WeeklyReport
            report = WeeklyReport()
            path = report.generate()
            push = await self._push_report_to_github(path)
            self.last_report_date = week_label
            return {"path": str(path), "pushed": push}
        except Exception as exc:
            logger.error(f"Weekly report failed: {exc}")
            return None
    
    async def _push_report_to_github(self, path: Path) -> bool:
        from config import settings
        repo = settings.GITHUB_PAGES_REPO
        token = settings.GITHUB_TOKEN
        if not repo or not token:
            logger.debug("GitHub Pages push skipped: GITHUB_PAGES_REPO or GITHUB_TOKEN not set")
            return False
        try:
            import subprocess, base64
            if not path.exists():
                return False
            content = base64.b64encode(path.read_bytes()).decode()
            name = path.name
            url = f"https://api.github.com/repos/{repo}/contents/reports/{name}"
            payload = {
                "message": f"Add weekly report {name}",
                "content": content,
                "branch": "gh-pages",
            }
            result = subprocess.run(
                ["python", "-c", f"""
import json, urllib.request
req = urllib.request.Request('{url}', data=json.dumps({payload}).encode(), headers={{"Authorization":"token {token}","Content-Type":"application/json","Accept":"application/vnd.github.v3+json"}})
try:
    with urllib.request.urlopen(req) as r:
        print(r.status)
except urllib.error.HTTPError as e:
    if e.code == 422:
        print('exists')
    else:
        raise
"""],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0 and result.stdout.strip() in ("200", "201", "exists"):
                logger.info(f"Report pushed to GitHub Pages: {name}")
                return True
            logger.warning(f"GitHub push failed: {result.stderr}")
            return False
        except Exception as exc:
            logger.error(f"GitHub Pages push failed: {exc}")
            return False
    
    async def _check_revenue(self) -> Dict[str, Any]:
        """Check revenue ledger and flag anomalies."""
        try:
            summary = self.revenue_ledger.get_summary()
            total = summary.get("total_revenue", 0)
            now = datetime.now()
            
            # Store revenue checkpoint
            checkpoint = {
                "timestamp": now.isoformat(),
                "total": total,
                "buckets": summary.get("bucket_balances", {}),
            }
            await self.memory.add_experience(
                content=f"REVENUE CHECKPOINT: ${total:.2f}",
                source="ceo_agent",
                metadata=checkpoint,
            )
            
            self.last_revenue_check = now
            return {
                "total": total,
                "buckets": summary.get("bucket_balances", {}),
                "status": "ok",
            }
        except Exception as exc:
            logger.error("Revenue check failed: {}", exc)
            return {"total": 0, "status": "error", "error": str(exc)}
    
    async def _store_cycle_state(self, result: Dict[str, Any]):
        """Persist CEO cycle state to memory."""
        try:
            await self.memory.add_experience(
                content=f"CEO CYCLE #{self.cycle}: health={result['health']['status']}",
                source="ceo_agent",
                metadata={
                    "ceo_cycle": self.cycle,
                    "health_status": result["health"]["status"],
                    "outreach_status": result["outreach"].get("status", "unknown"),
                    "revenue_total": result["revenue"].get("total", 0),
                },
            )
        except Exception as exc:
            logger.debug("Failed to store CEO state: {}", exc)
    
    async def get_dashboard(self) -> Dict[str, Any]:
        """Get full CEO dashboard for monitoring."""
        health = await self._check_health()
        outreach = await self._check_outreach_health()
        revenue = await self.revenue_ledger.get_summary()
        
        return {
            "ceo": {
                "cycle": self.cycle,
                "outreach_paused": self.outreach_paused,
                "send_paused": self.send_paused,
                "consecutive_failures": self.consecutive_failures,
                "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
                "last_outreach_cycle": self.last_outreach_cycle.isoformat() if self.last_outreach_cycle else None,
            },
            "health": health,
            "outreach": outreach,
            "revenue": {
                "total": revenue.get("total_revenue", 0),
                "breakdown": revenue.get("bucket_balances", {}),
            },
            "limits": self.alert_thresholds,
        }
    
    async def pause_outreach(self, reason: str = "manual"):
        """Pause outreach operations."""
        self.outreach_paused = True
        logger.warning("CEO: Outreach paused — {}", reason)
        await self.memory.add_experience(
            content=f"OUTREACH PAUSED: {reason}",
            source="ceo_agent",
        )
    
    async def resume_outreach(self):
        """Resume outreach operations."""
        self.outreach_paused = False
        self.consecutive_failures = 0
        logger.info("CEO: Outreach resumed")
        await self.memory.add_experience(
            content="OUTREACH RESUMED by CEO",
            source="ceo_agent",
        )

    async def approve_drafts(self) -> Dict[str, Any]:
        """Apply tiered CEO approval rules to pending drafts."""
        if not self.outreach or not self.outreach.enabled:
            return {"auto_send": [], "flag_review": [], "reject": []}

        if self.outreach_paused or self.send_paused:
            return {"auto_send": [], "flag_review": [], "reject": []}

        pending = self.outreach.delivery_agent.list_pending()
        if not pending:
            return {"auto_send": [], "flag_review": [], "reject": []}

        auto_send: List[Dict[str, Any]] = []
        flag_review: List[Dict[str, Any]] = []
        reject: List[Dict[str, Any]] = []

        min_local_score = int(os.getenv("CEO_MIN_LOCAL_SCORE", "3"))
        max_enterprise_penalty = int(os.getenv("CEO_MAX_ENTERPRISE_PENALTY", "2"))
        min_body_length = int(os.getenv("CEO_MIN_BODY_LENGTH", "200"))

        for draft in pending:
            decision = self._evaluate_draft(
                draft,
                min_local_score=min_local_score,
                max_enterprise_penalty=max_enterprise_penalty,
                min_body_length=min_body_length,
            )
            if decision == "auto_send":
                auto_send.append(draft)
            elif decision == "flag_review":
                flag_review.append(draft)
            else:
                reject.append(draft)

        for draft in auto_send:
            draft["status"] = "pending_review"
            draft["ceo_reviewed_at"] = datetime.now().isoformat()
            draft["ceo_reviewed_by"] = "ceo_auto_pass"
            self.outreach.delivery_agent.update_draft(draft)

        for draft in flag_review:
            self.outreach.delivery_agent.update_draft(draft)

        for draft in reject:
            draft["status"] = "skipped_bad_lead"
            draft["rejected_at"] = datetime.now().isoformat()
            draft["rejected_by"] = "ceo_auto"
            self.outreach.delivery_agent.update_draft(draft)

            archive_dir = Path("data/outreach/archive_stale")
            archive_dir.mkdir(parents=True, exist_ok=True)
            filename = draft.get("_filename", f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_rejected.json")
            archive_path = archive_dir / filename
            try:
                with open(archive_path, "w", encoding="utf-8") as f:
                    json.dump(draft, f, default=str, indent=2)
                src = self.outreach.delivery_agent.outbox_dir / filename
                if src.exists():
                    src.unlink()
            except Exception as exc:
                logger.debug("Failed to archive rejected draft: {}", exc)

        self._log_approvals(auto_send, flag_review, reject)

        return {
            "auto_send": auto_send,
            "flag_review": flag_review,
            "reject": reject,
        }

    def _evaluate_draft(
        self,
        draft: Dict[str, Any],
        min_local_score: int = 3,
        max_enterprise_penalty: int = 2,
        min_body_length: int = 200,
    ) -> str:
        """Evaluate a draft against CEO tiered rules. Returns: auto_send, flag_review, or reject."""
        brief = draft.get("lead_brief", {})
        contacts = brief.get("contacts", {})
        emails = contacts.get("emails", [])
        email = emails[0] if emails else ""
        recipient_domain = email.split("@")[-1].lower() if "@" in email else ""

        confidence = contacts.get("email_confidence", "unknown")
        source = contacts.get("email_source", "unknown")
        local_score = brief.get("local_business_score", 0)
        enterprise_penalty = brief.get("enterprise_penalty", 0)
        body = draft.get("body", "")

        if confidence in ("placeholder", "example") or confidence == "unknown":
            return "reject"

        if recipient_domain in OutreachScanner.AGGREGATOR_DOMAINS:
            return "reject"

        if ".example.com" in recipient_domain:
            return "reject"

        if enterprise_penalty > max_enterprise_penalty:
            return "reject"

        if local_score < min_local_score:
            return "reject"

        if len(body) < min_body_length:
            return "reject"

        if confidence == "low":
            return "flag_review"

        if source == "pattern_guess":
            return "flag_review"

        if min_local_score <= local_score <= 4:
            return "flag_review"

        if enterprise_penalty == 2:
            return "flag_review"

        return "auto_send"

    def _log_approvals(
        self,
        auto_send: List[Dict[str, Any]],
        flag_review: List[Dict[str, Any]],
        reject: List[Dict[str, Any]],
    ) -> None:
        """Log approval decisions to ceo_approvals.jsonl."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "auto_send_count": len(auto_send),
            "flag_review_count": len(flag_review),
            "reject_count": len(reject),
            "auto_send": [
                {"to": d.get("to"), "subject": d.get("subject"), "domain": d.get("lead_brief", {}).get("domain", "")}
                for d in auto_send
            ],
        }
        approvals_path = Path("data/outreach/ceo_approvals.jsonl")
        approvals_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(approvals_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(report, default=str) + "\n")
        except Exception as exc:
            logger.error("CEO: Failed to log approvals: {}", exc)

    async def emergency_stop(self):
        """Emergency stop — pause all outreach and sends."""
        self.outreach_paused = True
        self.send_paused = True
        logger.critical("CEO: EMERGENCY STOP activated")
        await self.memory.add_experience(
            content="EMERGENCY STOP activated by CEO",
            source="ceo_agent",
            metadata={"emergency": True, "timestamp": datetime.now().isoformat()},
        )
