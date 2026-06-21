"""
MECOS Event Bus System
Provides loose-coupled communication between cognitive layers via pub/sub pattern.
Events are persisted for replay and debugging.
"""

import asyncio
import json
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from loguru import logger


@dataclass
class Event:
    """Represents an event in the system."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: int = 100
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    source: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "payload": self.payload,
            "priority": self.priority,
            "timestamp": self.timestamp,
            "source": self.source,
            "metadata": self.metadata,
        }


class EventBus:
    """
    Central event bus for MECOS. Handles pub/sub with priority ordering,
    persistence, and async event processing.
    """

    def __init__(self, persistence_path: Optional[Path] = None):
        self.handlers: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.persistence_path = persistence_path or Path("memory_db/events")
        self.persistence_path.mkdir(parents=True, exist_ok=True)
        self._event_log: List[Dict[str, Any]] = []
        self._running = False
        self._queue: asyncio.Queue = asyncio.Queue()
        self._subscriber_lock = asyncio.Lock()

    async def publish(
        self,
        event_type: str,
        payload: Dict[str, Any],
        priority: int = 100,
        source: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Publish an event to all subscribers."""
        event = Event(
            type=event_type,
            payload=payload,
            priority=priority,
            source=source,
            metadata=metadata or {},
        )
        await self._persist_event(event)
        await self._dispatch_async(event)
        return event.id

    async def _persist_event(self, event: Event) -> None:
        """Persist event to disk for replay."""
        self._event_log.append(event.to_dict())
        if len(self._event_log) % 50 == 0:
            self._save_log()

    def _save_log(self) -> None:
        """Save event log to jsonl file."""
        log_file = self.persistence_path / "events.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            for event in self._event_log[-50:]:
                f.write(json.dumps(event) + "\n")

    async def _dispatch_async(self, event: Event) -> None:
        """Queue event for async dispatch."""
        await self._queue.put(event)

    async def _dispatch_loop(self) -> None:
        """Process events from queue."""
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._dispatch_event(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Event dispatch error: {e}")

    async def _dispatch_event(self, event: Event) -> None:
        """Dispatch event to all registered handlers."""
        handlers = self.handlers.get(event.type, [])
        if not handlers:
            logger.debug(f"No handlers for event type: {event.type}")
            return

        sorted_handlers = sorted(handlers, key=lambda h: h["priority"], reverse=True)
        for handler in sorted_handlers:
            try:
                result = handler["func"](event.to_dict())
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Handler failed for {event.type}: {e}")

    def subscribe(
        self,
        event_type: str,
        func: Callable,
        priority: int = 100,
        once: bool = False,
    ) -> str:
        """Register a handler for an event type."""
        handler_id = str(uuid.uuid4())
        self.handlers[event_type].append(
            {"id": handler_id, "func": func, "priority": priority, "once": once}
        )
        logger.debug(f"Subscribed to {event_type} with priority {priority}")
        return handler_id

    def unsubscribe(self, event_type: str, handler_id: str) -> bool:
        """Remove a handler."""
        handlers = self.handlers.get(event_type, [])
        for i, h in enumerate(handlers):
            if h["id"] == handler_id:
                del handlers[i]
                return True
        return False

    async def start_dispatcher(self) -> None:
        """Start async event dispatcher."""
        self._running = True
        asyncio.create_task(self._dispatch_loop())
        logger.info("EventBus dispatcher started")

    async def stop_dispatcher(self) -> None:
        """Stop async event dispatcher."""
        self._running = False
        self._save_log()
        logger.info("EventBus dispatcher stopped")

    async def replay(
        self,
        event_types: Optional[List[str]] = None,
        from_timestamp: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Replay historical events."""
        log_file = self.persistence_path / "events.jsonl"
        if not log_file.exists():
            return []

        results = []
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                event = json.loads(line.strip())
                if event_types and event["type"] not in event_types:
                    continue
                if from_timestamp and event["timestamp"] < from_timestamp:
                    continue
                results.append(event)
        return results

    def register_layer_handlers(self, layer_name: str, handler_map: Dict[str, Callable]) -> None:
        """Register all handlers for a layer at once."""
        for event_type, func in handler_map.items():
            self.subscribe(event_type, func, priority=100)
        logger.info(f"Registered {len(handler_map)} handlers for layer: {layer_name}")