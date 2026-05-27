import asyncio
from typing import Dict, Any, Callable
from loguru import logger
from enum import Enum
from datetime import datetime
import inspect

class EventType(Enum):
    MARKET_TICK = 'market_tick'
    SIGNAL_CREATED = 'signal_created'
    RISK_APPROVED = 'risk_approved'
    ORDER_SUBMITTED = 'order_submitted'
    ORDER_FILLED = 'order_filled'
    PNL_UPDATED = 'pnl_updated'
    MARKET_DATA = 'market_data'
    SIGNAL = 'signal'
    ORDER = 'order'
    FILL = 'fill'
    RISK = 'risk'
    PORTFOLIO = 'portfolio'

class Event:
    def __init__(self, event_type: EventType, data: Dict[str, Any]):
        self.type = event_type
        self.data = data
        self.timestamp = datetime.now()

class EventBus:
    def __init__(self):
        self.subscribers = {event_type: [] for event_type in EventType}
        self.queue = asyncio.Queue()
        self._consumer_task = None
        logger.info('Event Bus initialized')

    def subscribe(self, event_type: EventType, callback: Callable):
        self.subscribers[event_type].append(callback)

    async def publish(self, event: Event):
        await self.queue.put(event)

    async def start(self):
        if self._consumer_task and not self._consumer_task.done():
            return
        self._consumer_task = asyncio.create_task(self.process_events())

    async def stop(self):
        if not self._consumer_task:
            return
        self._consumer_task.cancel()
        try:
            await self._consumer_task
        except asyncio.CancelledError:
            pass
        self._consumer_task = None

    async def process_events(self):
        while True:
            event = await self.queue.get()
            
            for callback in self.subscribers[event.type]:
                try:
                    result = callback(event)
                    if inspect.isawaitable(result):
                        await result
                except Exception as e:
                    logger.error(f'Event handler error: {e}')
            self.queue.task_done()
