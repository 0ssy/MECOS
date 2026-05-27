from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional

from loguru import logger

from .health_monitor import HealthMonitor


class RuntimeWatchdog:
    def __init__(
        self,
        monitor: HealthMonitor,
        on_stale_component: Optional[Callable[[str, float], Awaitable[None]]] = None,
        interval_seconds: float = 10.0,
    ):
        self.monitor = monitor
        self.on_stale_component = on_stale_component
        self.interval_seconds = float(interval_seconds)
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self):
        while self._running:
            stale = self.monitor.unhealthy_components()
            for entry in stale:
                logger.warning(
                    f"Watchdog detected stale component={entry.component} "
                    f"stale_for={entry.stale_for_seconds:.1f}s"
                )
                if self.on_stale_component:
                    await self.on_stale_component(entry.component, entry.stale_for_seconds)
            await asyncio.sleep(self.interval_seconds)

