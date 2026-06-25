"""
MECOS Terminal Monitor
Shows business metrics, outreach pipeline, revenue, and system health in a live-updating terminal dashboard.

Run: python terminal_monitor.py

Press Ctrl+C to stop.

Windows: set PYTHONIOENCODING=utf-8 first, or use --once for a single snapshot.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich.live import Live
from rich.align import Align
from rich.text import Text
from rich import box

console = Console()

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTREACH_DIR = DATA_DIR / "outreach"
LEADS_FILE = OUTREACH_DIR / "leads.json"
REVENUE_FILE = OUTREACH_DIR / "revenue_ledger.json"
SYNTHESIZED_FILE = OUTREACH_DIR / "synthesized_leads.json"
PAYMENTS_FILE = OUTREACH_DIR / "payments" / "payment_ledger.json"
REPLIES_FILE = OUTREACH_DIR / "replies.json"
OUTBOX_DIR = OUTREACH_DIR / "outbox"
SENT_DIR = OUTREACH_DIR / "sent"
CEO_FILE = OUTREACH_DIR / "ceo_instincts.json"
HEALTH_FILE = DATA_DIR / "health_status.json"

REFRESH_INTERVAL = 5


def load_json(path: Path) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception as e:
        console.log(f"[red]Error loading {path}: {e}[/red]")
    return None


def count_files(directory: Path) -> int:
    try:
        return len([f for f in directory.iterdir() if f.is_file()])
    except Exception:
        return 0


def get_revenue_data() -> Dict[str, Any]:
    data = load_json(REVENUE_FILE) or {}
    entries = data.get("entries", [])
    buckets = data.get("bucket_balances", {})
    last_updated = data.get("last_updated", "N/A")
    real_entries = [
        e for e in entries
        if "test" not in e.get("deal_id", "").lower()
        and "test" not in e.get("description", "").lower()
    ]
    real_total = sum(float(e.get("amount", 0)) for e in real_entries)
    recent = real_entries[-5:] if real_entries else []
    return {
        "total": real_total,
        "buckets": buckets,
        "entries_count": len(real_entries),
        "last_updated": last_updated,
        "recent": recent,
    }


def get_outreach_data() -> Dict[str, Any]:
    leads = load_json(LEADS_FILE) or []
    synthesized = load_json(SYNTHESIZED_FILE) or []
    outbox_count = count_files(OUTBOX_DIR)
    sent_count = count_files(SENT_DIR)
    replies = load_json(REPLIES_FILE) or []

    real_leads = [l for l in leads if l.get("domain") not in (
        "hn.algolia.com", "news.ycombinator.com", "reddit.com",
        "www.reddit.com", "indiehackers.com", "www.indiehackers.com"
    )]
    real_briefs = [b for b in synthesized if b.get("domain") not in (
        "hn.algolia.com", "news.ycombinator.com", "reddit.com",
        "www.reddit.com", "indiehackers.com", "www.indiehackers.com"
    )]

    new_leads = sum(1 for l in real_leads if l.get("status") == "new")
    ready_briefs = sum(1 for b in real_briefs if b.get("status") == "ready_for_outreach")
    drafted_briefs = sum(1 for b in real_briefs if b.get("status") == "drafted")
    contacted = sum(1 for l in real_leads if l.get("status") == "contacted")

    platform_sources: Dict[str, int] = {}
    for l in real_leads:
        src = l.get("source", "unknown").split("/")[0]
        platform_sources[src] = platform_sources.get(src, 0) + 1

    return {
        "total_leads": len(real_leads),
        "new_leads": new_leads,
        "contacted": contacted,
        "ready_briefs": ready_briefs,
        "drafted_briefs": drafted_briefs,
        "outbox_drafts": outbox_count,
        "sent_emails": sent_count,
        "replies": len(replies),
        "platform_sources": platform_sources,
        "avg_score": round(
            sum(l.get("total_score", 0) for l in real_leads) / max(len(real_leads), 1), 2
        ),
    }


def get_payment_data() -> Dict[str, Any]:
    data = load_json(PAYMENTS_FILE) or {}
    invoices = data.get("invoices", [])
    payments = data.get("payments", [])
    real_payments = [
        p for p in payments
        if "test" not in p.get("lead_id", "").lower()
        and "example.com" not in p.get("client_email", "").lower()
    ]
    real_invoices = [
        i for i in invoices
        if "test" not in i.get("lead_id", "").lower()
        and "example.com" not in i.get("client_email", "").lower()
    ]
    pending = [i for i in real_invoices if i.get("status") == "pending"]
    completed = [p for p in real_payments if p.get("status") == "completed"]
    recent_payments = real_payments[-5:] if real_payments else []
    recent_invoices = real_invoices[-5:] if real_invoices else []
    return {
        "total_invoices": len(real_invoices),
        "pending": len(pending),
        "completed": len(completed),
        "recent_payments": recent_payments,
        "recent_invoices": recent_invoices,
    }


def get_health_data() -> Dict[str, Any]:
    if HEALTH_FILE.exists():
        return load_json(HEALTH_FILE) or {}
    return {"status": "unknown", "checks": {}}


def get_system_data() -> Dict[str, Any]:
    return {
        "mecos_pid": os.getpid(),
        "uptime": time.time(),
    }


def build_dashboard() -> Layout:
    layout = Layout()

    layout.split(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="footer", size=3),
    )
    layout["main"].split_row(
        Layout(name="left", ratio=1),
        Layout(name="right", ratio=1),
    )
    layout["left"].split_column(
        Layout(name="revenue", ratio=1),
        Layout(name="payments", ratio=1),
    )
    layout["right"].split_column(
        Layout(name="outreach", ratio=1),
        Layout(name="health", ratio=1),
    )

    # Header
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header_text = Text.from_markup(
        f"[bold cyan]MECOS Terminal Monitor[/bold cyan]  |  "
        f"[yellow]{now}[/yellow]  |  "
        f"[dim]Refresh every {REFRESH_INTERVAL}s | Ctrl+C to stop[/dim]"
    )
    layout["header"].update(Panel(Align.center(header_text), box=box.SIMPLE, style="cyan"))

    # Revenue
    rev = get_revenue_data()
    rev_table = Table(show_header=True, header_style="bold green", box=box.SIMPLE, expand=True)
    rev_table.add_column("Bucket", style="cyan")
    rev_table.add_column("Balance", justify="right", style="bold green")
    rev_table.add_column("", justify="center")

    bucket_labels = {
        "ops_hardware": "Ops & Hardware (40%)",
        "trading_reserve": "Trading Reserve (30%)",
        "growth_profit": "Growth Profit (30%)",
    }
    for key in ["ops_hardware", "trading_reserve", "growth_profit"]:
        val = rev["buckets"].get(key, 0)
        pct = round((val / rev["total"] * 100), 1) if rev["total"] > 0 else 0
        bar = "[green]" + ("█" * int(pct / 5)) + "[/green]" + ("░" * (20 - int(pct / 5)))
        rev_table.add_row(bucket_labels.get(key, key), f"${val:,.2f}", bar)

    rev_table.add_row(
        "[bold]TOTAL[/bold]", f"[bold]${rev['total']:,.2f}[/bold]", "",
        style="bold"
    )
    if rev["recent"]:
        rev_table.add_section()
        rev_table.add_row("[bold]Last Transaction[/bold]", "", "")
        last = rev["recent"][-1]
        rev_table.add_row(
            last.get("deal_id", "")[:20],
            f"${last.get('amount', 0):,.2f}",
            last.get("source", "")[:15],
        )

    rev_panel = Panel(
        rev_table,
        title="[bold green]REVENUE[/bold green]",
        subtitle=f"Last updated: {rev['last_updated'][:19].replace('T', ' ')}",
        box=box.SIMPLE,
    )
    layout["revenue"].update(rev_panel)

    # Payments
    pay = get_payment_data()
    pay_table = Table(show_header=True, header_style="bold yellow", box=box.SIMPLE, expand=True)
    pay_table.add_column("Stat", style="cyan")
    pay_table.add_column("Value", justify="right")

    pay_table.add_row("Total Invoices", str(pay["total_invoices"]))
    pay_table.add_row("Pending", f"[yellow]{pay['pending']}[/yellow]")
    pay_table.add_row("Completed", f"[green]{pay['completed']}[/green]")
    pay_table.add_row("Collected", "")
    total_collected = sum(
        p.get("amount", 0) for p in pay["recent_payments"] if p.get("status") == "completed"
    )
    pay_table.add_row("Recent Collected", f"${total_collected:,.2f}")

    if pay["recent_invoices"]:
        pay_table.add_section()
        for inv in pay["recent_invoices"][-3:]:
            status_color = "green" if inv.get("status") == "completed" else "yellow"
            pay_table.add_row(
                inv.get("invoice_id", "")[:18],
                f"[{status_color}]${inv.get('amount', 0):,.2f} {inv.get('status', '')}[/{status_color}]",
            )

    pay_panel = Panel(
        pay_table,
        title="[bold yellow]PAYMENTS & INVOICES[/bold yellow]",
        box=box.SIMPLE,
    )
    layout["payments"].update(pay_panel)

    # Outreach
    out = get_outreach_data()
    out_table = Table(show_header=True, header_style="bold magenta", box=box.SIMPLE, expand=True)
    out_table.add_column("Metric", style="cyan")
    out_table.add_column("Count", justify="right")
    out_table.add_column("Note")

    out_table.add_row("Total Leads", str(out["total_leads"]), f"avg score: {out['avg_score']}")
    out_table.add_row("New Leads", f"[green]{out['new_leads']}[/green]", "awaiting contact")
    out_table.add_row("Contacted", str(out["contacted"]), "")
    out_table.add_row("Ready Briefs", f"[yellow]{out['ready_briefs']}[/yellow]", "ready for outreach")
    out_table.add_row("Drafted", str(out["drafted_briefs"]), "")
    out_table.add_row(
        "Pending Drafts", f"[yellow]{out['outbox_drafts']}[/yellow]", "awaiting review/send"
    )
    out_table.add_row("Sent Emails", f"[green]{out['sent_emails']}[/green]", "")
    out_table.add_row("Email Replies", str(out["replies"]), "")

    out_table.add_section()
    out_table.add_row("[bold]Sources[/bold]", "", "")
    for src, cnt in sorted(out["platform_sources"].items(), key=lambda x: -x[1])[:5]:
        out_table.add_row(src, str(cnt), "")

    out_panel = Panel(
        out_table,
        title="[bold magenta]OUTREACH PIPELINE[/bold magenta]",
        box=box.SIMPLE,
    )
    layout["outreach"].update(out_panel)

    # Health / System tasks
    health = get_health_data()
    health_table = Table(show_header=True, header_style="bold blue", box=box.SIMPLE, expand=True)
    health_table.add_column("Check", style="cyan")
    health_table.add_column("Status", justify="center")
    health_table.add_column("Latency", justify="right")

    status_color_map = {"ok": "green", "warn": "yellow", "error": "red", "unknown": "dim"}

    checks = health.get("checks", {})
    for name, check in checks.items():
        status = check.get("status", "unknown")
        color = status_color_map.get(status, "white")
        latency = check.get("latency", "N/A")
        latency_str = f"{latency:.0f}ms" if isinstance(latency, (int, float)) else str(latency)
        health_table.add_row(
            name,
            f"[{color}]{status.upper()}[/{color}]",
            latency_str,
        )

    if not checks:
        health_table.add_row("No health data", "[dim]check dashboard[/dim]", "")

    sys_data = get_system_data()
    health_table.add_section()
    health_table.add_row("MECOS PID", str(sys_data["mecos_pid"]), "running")
    health_table.add_row("Uptime", "", "")

    health_panel = Panel(
        health_table,
        title="[bold blue]SYSTEM HEALTH[/bold blue]",
        box=box.SIMPLE,
    )
    layout["health"].update(health_panel)

    # Footer
    footer_text = Text.from_markup(
        "[dim]MECOS Terminal Monitor | "
        f"Leads: {out['total_leads']} | "
        f"Revenue: ${rev['total']:,.2f} | "
        f"Sent: {out['sent_emails']} | "
        f"Pending: {out['outbox_drafts']}[/dim]"
    )
    layout["footer"].update(Panel(Align.center(footer_text), box=box.SIMPLE, style="dim"))

    return layout


def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    import sys as _sys
    once = "--once" in _sys.argv
    if not once:
        console.clear()
    console.print("[bold cyan]Starting MECOS Terminal Monitor...[/bold cyan]")
    if once:
        console.print(build_dashboard())
        return
    try:
        with Live(
            build_dashboard(),
            console=console,
            refresh_per_second=1,
            screen=False,
        ) as live:
            while True:
                time.sleep(REFRESH_INTERVAL)
                live.update(build_dashboard())
    except KeyboardInterrupt:
        console.print("\n[yellow]Monitor stopped.[/yellow]")


if __name__ == "__main__":
    main()
