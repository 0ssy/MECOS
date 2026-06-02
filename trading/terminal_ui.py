from __future__ import annotations

from typing import Any, Dict


def render_signal_dashboard(decisions: Dict[str, Dict[str, Any]]) -> str:
    """Render a compact terminal dashboard string for signal snapshots."""
    headers = ["SYMBOL", "DECISION", "CONF", "EDGE", "REGIME", "RISK_GATE"]
    widths = [12, 10, 8, 8, 12, 22]
    line = " ".join(h.ljust(w) for h, w in zip(headers, widths))
    sep = "-" * len(line)
    rows = [line, sep]

    for symbol, payload in sorted((decisions or {}).items()):
        decision = str(payload.get("final_decision", payload.get("decision", "HOLD"))).upper()
        conf = f"{float(payload.get('confidence', 0.0) or 0.0):.2f}"
        edge = f"{float(payload.get('edge', 0.0) or 0.0):.2f}"
        regime = str(payload.get("regime", "unknown"))
        risk_gate = str(payload.get("risk_gate_reason", "")) or "-"
        row = [
            str(symbol)[:widths[0] - 1].ljust(widths[0]),
            decision[:widths[1] - 1].ljust(widths[1]),
            conf.rjust(widths[2] - 1).ljust(widths[2]),
            edge.rjust(widths[3] - 1).ljust(widths[3]),
            regime[:widths[4] - 1].ljust(widths[4]),
            risk_gate[:widths[5] - 1].ljust(widths[5]),
        ]
        rows.append(" ".join(row))
    return "\n".join(rows)
