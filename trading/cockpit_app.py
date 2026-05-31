from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


def build_cockpit_snapshot(trading_system: Any) -> Dict[str, Any]:
    performance_monitor = getattr(trading_system, "performance_monitor", None)
    metrics = performance_monitor.get_metrics() if performance_monitor else {}
    status = trading_system.get_status() if hasattr(trading_system, "get_status") else {}
    signal_stats = {}
    signal_generator = getattr(trading_system, "signal_generator", None)
    if signal_generator and hasattr(signal_generator, "get_stats"):
        signal_stats = signal_generator.get_stats()
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "performance_metrics": metrics,
        "signal_stats": signal_stats,
    }
