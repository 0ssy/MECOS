import asyncio
from typing import Dict, Any, Callable
from loguru import logger
from enum import Enum
from datetime import datetime

class EventType(Enum):
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
        logger.info('Event Bus initialized')

    def subscribe(self, event_type: EventType, callback: Callable):
        self.subscribers[event_type].append(callback)

    async def publish(self, event: Event):
        await self.queue.put(event)

    async def process_events(self):
        while True:
            event = await self.queue.get()
            
            for callback in self.subscribers[event.type]:
                try:
                    await callback(event)
                except Exception as e:
                    logger.error(f'Event handler error: {e}')
