#!/usr/bin/env python3
"""
MECOS Terminal Dashboard
Lightweight HTTP server that serves a terminal-style dashboard
for monitoring outreach, revenue, and system status.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger
from config import settings

BASE_DIR = settings.BASE_DIR
OUTREACH_DIR = settings.DATA_DIR / "outreach"
DASHBOARD_PORT = settings.DASHBOARD_PORT


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, data: Dict[str, Any], status: int = 200):
        payload = json.dumps(data, default=str, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_html(self, html: str):
        payload = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._send_html(DASHBOARD_HTML)
        elif self.path == "/api/stats":
            self._send_json(self._collect_stats())
        elif self.path == "/api/leads":
            self._send_json(self._read_json(OUTREACH_DIR / "leads.json", []))
        elif self.path == "/api/revenue":
            self._send_json(self._read_json(OUTREACH_DIR / "revenue_ledger.json", {}))
        elif self.path == "/api/case_studies":
            self._send_json(self._read_json(OUTREACH_DIR / "funnel" / "case_studies.json", []))
        elif self.path == "/api/outbox":
            outbox = []
            outbox_dir = OUTREACH_DIR / "outbox"
            sent_dir = OUTREACH_DIR / "sent"
            if outbox_dir.exists():
                for f in sorted(outbox_dir.glob("*.json")):
                    try:
                        outbox.append(json.loads(f.read_text()))
                    except Exception:
                        pass
            if sent_dir.exists():
                for f in sorted(sent_dir.glob("*.json")):
                    try:
                        data = json.loads(f.read_text())
                        data["_file"] = f.name
                        outbox.append(data)
                    except Exception:
                        pass
            self._send_json(outbox[-50:])
        elif self.path == "/api/payments":
            self._send_json(self._read_json(OUTREACH_DIR / "payments" / "payment_ledger.json", {}).get("payments", []))
        elif self.path.startswith("/api/invoices/"):
            invoice_id = self.path.split("/")[-1]
            ledger_data = self._read_json(OUTREACH_DIR / "payments" / "payment_ledger.json", {})
            payment = next((p for p in ledger_data.get("payments", []) if p.get("invoice_id") == invoice_id), None)
            if payment:
                self._send_json(payment)
            else:
                self._send_json({"error": "not_found"}, 404)
        elif self.path == "/api/payments/summary":
            self._send_json(self._read_json(OUTREACH_DIR / "payments" / "payment_ledger.json", {}).get("payments", []))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length)

        if self.path == "/webhooks/paypal":
            try:
                from outreach.payments.webhooks import PayPalWebhookHandler
                handler = PayPalWebhookHandler()
                event_body = json.loads(body_bytes.decode())

                verified = handler.verify_signature(dict(self.headers), body_bytes)
                if not verified:
                    self.send_response(403)
                    self.end_headers()
                    self.wfile.write(b'{"error": "invalid_signature"}')
                    return

                result = handler.process_event(event_body)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            except Exception as e:
                logger.error(f"PayPal webhook processing error: {e}")
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b'{"error": "processing_failed"}')
        else:
            self.send_response(404)
            self.end_headers()

    def _read_json(self, path: Path, default):
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                return default
        return default

    def _collect_stats(self) -> Dict[str, Any]:
        leads = self._read_json(OUTREACH_DIR / "leads.json", [])
        synthesized = self._read_json(OUTREACH_DIR / "synthesized_leads.json", [])
        revenue = self._read_json(OUTREACH_DIR / "revenue_ledger.json", {})

        outbox_count = 0
        sent_count = 0
        outbox_dir = OUTREACH_DIR / "outbox"
        sent_dir = OUTREACH_DIR / "sent"
        if outbox_dir.exists():
            outbox_count = len(list(outbox_dir.glob("*.json")))
        if sent_dir.exists():
            sent_count = len(list(sent_dir.glob("*.json")))

        bucket_balances = revenue.get("bucket_balances", {})
        entries = revenue.get("entries", [])

        status = {
            "timestamp": datetime.now().isoformat(),
            "system": {
                "version": settings.VERSION,
                "trading_enabled": os.getenv("TRADING_ENABLED", "false").lower() == "true",
                "outreach_enabled": settings.MECOS_ENABLE_OUTREACH,
                "email_enabled": bool(settings.MECOS_EMAIL),
            },
            "leads": {
                "total": len(leads),
                "new": len([l for l in leads if l.get("status") == "new"]),
                "contacted": len([l for l in leads if l.get("status") == "contacted"]),
            },
            "outreach": {
                "synthesized": len(synthesized),
                "pending_outbox": outbox_count,
                "sent": sent_count,
            },
            "revenue": {
                "total": sum(bucket_balances.values()),
                "ops_hardware": bucket_balances.get("ops_hardware", 0),
                "trading_reserve": bucket_balances.get("trading_reserve", 0),
                "growth_profit": bucket_balances.get("growth_profit", 0),
                "transactions": len(entries),
            },
            "recent_transactions": entries[-10:],
        }
        return status


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def run_dashboard(port: int = DASHBOARD_PORT):
    server = ThreadedHTTPServer(("0.0.0.0", port), DashboardHandler)
    logger.info(f"Dashboard running at http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MECOS Terminal</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: #0d1117;
    color: #c9d1d9;
    font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'SF Mono', Consolas, monospace;
    font-size: 13px;
    line-height: 1.5;
    padding: 20px;
    min-height: 100vh;
  }
  .window {
    background: #010409;
    border: 1px solid #30363d;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 8px 24px rgba(0,0,0,0.5);
    max-width: 1100px;
    margin: 0 auto;
  }
  .titlebar {
    background: #161b22;
    padding: 10px 16px;
    display: flex;
    align-items: center;
    border-bottom: 1px solid #30363d;
  }
  .dots { display: flex; gap: 8px; margin-right: 16px; }
  .dot { width: 12px; height: 12px; border-radius: 50%; }
  .dot.red { background: #ff5f56; }
  .dot.yellow { background: #ffbd2e; }
  .dot.green { background: #27c93f; }
  .titlebar-text { color: #8b949e; font-size: 12px; }
  .content { padding: 20px; }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
    margin-bottom: 20px;
  }
  .card {
    background: #0d1117;
    border: 1px solid #21262d;
    border-radius: 6px;
    padding: 14px;
  }
  .card-header {
    color: #58a6ff;
    font-weight: 700;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 8px;
    border-bottom: 1px dashed #21262d;
    padding-bottom: 6px;
  }
  .metric { font-size: 24px; font-weight: 700; color: #f0f6fc; }
  .metric.small { font-size: 16px; }
  .label { color: #8b949e; font-size: 11px; margin-top: 2px; }
  .bar-bg {
    background: #21262d;
    border-radius: 4px;
    height: 8px;
    margin-top: 8px;
    overflow: hidden;
  }
  .bar-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.4s ease;
  }
  .bar-ops { background: #58a6ff; }
  .bar-trading { background: #3fb950; }
  .bar-growth { background: #d29922; }
  .log {
    background: #010409;
    border: 1px solid #21262d;
    border-radius: 6px;
    padding: 12px;
    height: 220px;
    overflow-y: auto;
    font-size: 12px;
    color: #8b949e;
  }
  .log-line { margin-bottom: 4px; }
  .log-line .time { color: #6e7681; margin-right: 8px; }
  .log-line.info { color: #c9d1d9; }
  .log-line.success { color: #3fb950; }
  .log-line.warn { color: #d29922; }
  .log-line.error { color: #f85149; }
  .section-title {
    color: #f0f6fc;
    font-weight: 700;
    margin: 20px 0 10px;
    font-size: 14px;
  }
  .tag {
    display: inline-block;
    background: #21262d;
    color: #c9d1d9;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    margin-right: 6px;
    margin-bottom: 4px;
  }
  .tag.active { background: #238636; color: #fff; }
  .tag.warn { background: #9e6a03; color: #fff; }
  a { color: #58a6ff; text-decoration: none; }
</style>
</head>
<body>
<div class="window">
  <div class="titlebar">
    <div class="dots"><div class="dot red"></div><div class="dot yellow"></div><div class="dot green"></div></div>
    <div class="titlebar-text">mecos@agency:~/outreach — zsh — 80x24</div>
  </div>
  <div class="content" id="app">
    <div style="color:#3fb950;">mecos@agency:~$ ./run_outreach.sh</div>
    <div style="color:#8b949e; margin-bottom:16px;">Loading metrics...</div>
    <div class="grid" id="metrics"></div>
    <div class="section-title">Revenue Buckets</div>
    <div class="grid" id="revenue"></div>
    <div class="section-title">System</div>
    <div class="grid" id="system"></div>
    <div class="section-title">Live Log</div>
    <div class="log" id="log"></div>
  </div>
</div>

<script>
function fmt(n) { return '$' + Number(n).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}); }
function timeAgo(iso) {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff/60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return mins + 'm ago';
  const hrs = Math.floor(mins/60);
  if (hrs < 24) return hrs + 'h ago';
  return Math.floor(hrs/24) + 'd ago';
}

function addLog(html) {
  const log = document.getElementById('log');
  const line = document.createElement('div');
  line.className = 'log-line info';
  const ts = new Date().toLocaleTimeString('en-US', {hour12: false});
  line.innerHTML = '<span class="time">' + ts + '</span>' + html;
  log.prepend(line);
  while (log.children.length > 80) log.removeChild(log.lastChild);
}

async function update() {
  try {
    const res = await fetch('/api/stats');
    const d = await res.json();
    const m = document.getElementById('metrics');
    m.innerHTML = `
      <div class="card">
        <div class="card-header">Leads Discovered</div>
        <div class="metric">${d.leads.total}</div>
        <div class="label">${d.leads.new} new · ${d.leads.contacted} contacted</div>
      </div>
      <div class="card">
        <div class="card-header">Outreach Pipeline</div>
        <div class="metric">${d.outreach.synthesized}</div>
        <div class="label">${d.outreach.pending_outbox} pending · ${d.outreach.sent} sent</div>
      </div>
      <div class="card">
        <div class="card-header">Revenue Total</div>
        <div class="metric">${fmt(d.revenue.total)}</div>
        <div class="label">${d.revenue.transactions} transactions</div>
      </div>
    `;

    const r = document.getElementById('revenue');
    const ops = d.revenue.total || 1;
    r.innerHTML = `
      <div class="card">
        <div class="card-header">Ops & Hardware (40%)</div>
        <div class="metric small">${fmt(d.revenue.ops_hardware)}</div>
        <div class="bar-bg"><div class="bar-fill bar-ops" style="width:${(d.revenue.ops_hardware/ops)*100}%"></div></div>
      </div>
      <div class="card">
        <div class="card-header">Trading Reserve (30%)</div>
        <div class="metric small">${fmt(d.revenue.trading_reserve)}</div>
        <div class="bar-bg"><div class="bar-fill bar-trading" style="width:${(d.revenue.trading_reserve/ops)*100}%"></div></div>
      </div>
      <div class="card">
        <div class="card-header">Growth & Profit (30%)</div>
        <div class="metric small">${fmt(d.revenue.growth_profit)}</div>
        <div class="bar-bg"><div class="bar-fill bar-growth" style="width:${(d.revenue.growth_profit/ops)*100}%"></div></div>
      </div>
    `;

    const s = document.getElementById('system');
    s.innerHTML = `
      <div class="card">
        <div class="card-header">Trading</div>
        <div style="margin-top:6px;"><span class="tag ${d.system.trading_enabled ? 'active' : 'warn'}">${d.system.trading_enabled ? 'LIVE' : 'PAPER'}</span></div>
      </div>
      <div class="card">
        <div class="card-header">Outreach</div>
        <div style="margin-top:6px;"><span class="tag ${d.system.outreach_enabled ? 'active' : 'warn'}">${d.system.outreach_enabled ? 'ENABLED' : 'DISABLED'}</span></div>
      </div>
      <div class="card">
        <div class="card-header">Email</div>
        <div style="margin-top:6px;"><span class="tag ${d.system.email_enabled ? 'active' : 'warn'}">${d.system.email_enabled ? 'CONNECTED' : 'MISSING'}</span></div>
      </div>
      <div class="card">
        <div class="card-header">Last Update</div>
        <div class="label" style="margin-top:6px;">${timeAgo(d.timestamp)}</div>
      </div>
    `;

    if (d.recent_transactions && d.recent_transactions.length) {
      const last = d.recent_transactions[d.recent_transactions.length - 1];
      addLog(`Payment <b>${fmt(last.amount)}</b> from <b>${last.source || last.deal_id}</b>`);
      for (const [k,v] of Object.entries(last.allocation || {})) {
        addLog(`  → ${k}: ${fmt(v)}`);
      }
    }
  } catch (e) {
    console.error('dashboard fetch failed', e);
  }
}

setInterval(update, 2000);
update();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=int(os.getenv("DASHBOARD_PORT", "8080")))
    args = parser.parse_args()
    run_dashboard(args.port)
