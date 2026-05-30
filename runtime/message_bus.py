"""
runtime/message_bus.py
Async message bus for inter-agent communication.
Replaces direct function calls with message passing so a crash in one
agent cannot take down the others.

Usage:
    bus = MessageBus()
    await bus.publish("research", {"topic": "autonomous runtime"})
    msg = await bus.subscribe("research")
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from loguru import logger


@dataclass
class Message:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    channel: str = ""
    payload: Any = None
    sender: str = "unknown"
    timestamp: float = field(default_factory=time.time)
    priority: int = 5          # 1=highest, 10=lowest
    ttl_seconds: float = 60.0  # message expires after this many seconds

    def is_expired(self) -> bool:
        return (time.time() - self.timestamp) > self.ttl_seconds


class MessageBus:
    """
    Async pub/sub message bus.
    Agents publish to channels; subscribers receive from their channels.
    Dead letters (undelivered after TTL) are logged and discarded.
    """

    def __init__(self, max_queue_size: int = 500):
        self._queues: Dict[str, asyncio.Queue] = {}
        self._handlers: Dict[str, List[Callable]] = {}
        self._stats: Dict[str, int] = {
            "published": 0,
            "delivered": 0,
            "expired": 0,
            "errors": 0,
        }
        self._max_queue_size = max_queue_size
        self._running = False
        self._dispatch_task: Optional[asyncio.Task] = None

    def _ensure_channel(self, channel: str):
        if channel not in self._queues:
            self._queues[channel] = asyncio.Queue(maxsize=self._max_queue_size)
        if channel not in self._handlers:
            self._handlers[channel] = []

    async def publish(self, channel: str, payload: Any, sender: str = "system",
                      priority: int = 5, ttl: float = 60.0):
        self._ensure_channel(channel)
        msg = Message(channel=channel, payload=payload, sender=sender,
                      priority=priority, ttl_seconds=ttl)
        try:
            self._queues[channel].put_nowait(msg)
            self._stats["published"] += 1
        except asyncio.QueueFull:
            logger.warning(f"[MessageBus] Queue full for channel '{channel}' — dropping message")
            self._stats["errors"] += 1

    async def subscribe(self, channel: str, timeout: float = 5.0) -> Optional[Message]:
        """Pull next message from channel. Returns None on timeout."""
        self._ensure_channel(channel)
        try:
            msg = await asyncio.wait_for(self._queues[channel].get(), timeout=timeout)
            if msg.is_expired():
                self._stats["expired"] += 1
                logger.debug(f"[MessageBus] Expired message on '{channel}' discarded")
                return None
            self._stats["delivered"] += 1
            return msg
        except asyncio.TimeoutError:
            return None

    def register_handler(self, channel: str, handler: Callable):
        """Register an async handler that fires on every message to channel."""
        self._ensure_channel(channel)
        self._handlers[channel].append(handler)

    async def start_dispatch(self):
        """Start background dispatch loop for registered handlers."""
        self._running = True
        self._dispatch_task = asyncio.create_task(self._dispatch_loop())
        logger.info("[MessageBus] Dispatch loop started")

    async def stop_dispatch(self):
        self._running = False
        if self._dispatch_task:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass
        logger.info("[MessageBus] Dispatch loop stopped")

    async def _dispatch_loop(self):
        while self._running:
            for channel, handlers in self._handlers.items():
                if not handlers:
                    continue
                msg = await self.subscribe(channel, timeout=0.1)
                if msg is None:
                    continue
                for handler in handlers:
                    try:
                        await handler(msg)
                    except Exception as e:
                        logger.error(f"[MessageBus] Handler error on '{channel}': {e}")
                        self._stats["errors"] += 1
            await asyncio.sleep(0.05)

    def stats(self) -> Dict[str, int]:
        return dict(self._stats)

    def channel_sizes(self) -> Dict[str, int]:
        return {ch: q.qsize() for ch, q in self._queues.items()}


# Global singleton — import and use anywhere
_bus: Optional[MessageBus] = None

def get_bus() -> MessageBus:
    global _bus
    if _bus is None:
        _bus = MessageBus()
    return _bus
