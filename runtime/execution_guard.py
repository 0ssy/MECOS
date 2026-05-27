from __future__ import annotations

import asyncio
from typing import Awaitable, TypeVar

from loguru import logger

T = TypeVar("T")


class ExecutionGuard:
    def __init__(self, default_timeout_seconds: float = 90.0, retries: int = 1):
        self.default_timeout_seconds = float(default_timeout_seconds)
        self.retries = int(retries)

    async def run(
        self,
        name: str,
        awaitable: Awaitable[T],
        timeout_seconds: float | None = None,
    ) -> T:
        timeout = float(timeout_seconds or self.default_timeout_seconds)
        attempts = max(1, self.retries + 1)

        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                return await asyncio.wait_for(awaitable, timeout=timeout)
            except asyncio.TimeoutError as exc:
                last_error = exc
                logger.error(f"Execution timeout: {name} attempt={attempt}/{attempts} timeout={timeout}s")
            except Exception as exc:
                last_error = exc
                logger.error(f"Execution failure: {name} attempt={attempt}/{attempts} error={exc}")

        raise RuntimeError(f"Execution guard exhausted retries for {name}: {last_error}")

