from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class ComponentHealth:
    component: str
    last_heartbeat: float
    stale_for_seconds: float
    status: str


class HealthMonitor:
    def __init__(self, stale_threshold_seconds: float = 60.0):
        self.stale_threshold_seconds = float(stale_threshold_seconds)
        self._heartbeats: Dict[str, float] = {}

    def heartbeat(self, component: str):
        self._heartbeats[str(component)] = time.time()

    def mark_started(self, component: str):
        self.heartbeat(component)

    def snapshots(self) -> List[ComponentHealth]:
        now = time.time()
        out: List[ComponentHealth] = []
        for component, last in self._heartbeats.items():
            stale_for = max(0.0, now - last)
            status = "healthy" if stale_for <= self.stale_threshold_seconds else "stale"
            out.append(
                ComponentHealth(
                    component=component,
                    last_heartbeat=last,
                    stale_for_seconds=stale_for,
                    status=status,
                )
            )
        return out

    def unhealthy_components(self) -> List[ComponentHealth]:
        return [entry for entry in self.snapshots() if entry.status != "healthy"]

