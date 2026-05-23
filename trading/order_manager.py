from typing import Dict, Any
from loguru import logger
from enum import Enum

class OrderStatus(Enum):
    CREATED = 'CREATED'
    SUBMITTED = 'SUBMITTED'
    PARTIALLY_FILLED = 'PARTIALLY_FILLED'
    FILLED = 'FILLED'
    CANCELLED = 'CANCELLED'
    REJECTED = 'REJECTED'

class OrderManager:
    def __init__(self, database):
        self.database = database
        self.active_orders = {}
        logger.info('Order Manager initialized')

    async def create_order(self, order: Dict) -> int:
        order['status'] = OrderStatus.CREATED.value
        order_id = self.database.insert_order(order)
        self.active_orders[order_id] = order
        logger.info(f'Order created: {order_id}')
        return order_id

    async def submit_order(self, order_id: int):
        if order_id in self.active_orders:
            self.active_orders[order_id]['status'] = OrderStatus.SUBMITTED.value
            logger.info(f'Order submitted: {order_id}')

    async def fill_order(self, order_id: int, fill_price: float, fill_size: float):
        if order_id not in self.active_orders:
            return
        
        order = self.active_orders[order_id]
        
        self.database.insert_fill({
            'order_id': order_id,
            'symbol': order['symbol'],
            'size': fill_size,
            'price': fill_price
        })
        
        if fill_size >= order['size']:
            order['status'] = OrderStatus.FILLED.value
            logger.info(f'Order filled: {order_id}')
        else:
            order['status'] = OrderStatus.PARTIALLY_FILLED.value
            logger.info(f'Order partially filled: {order_id}')

    async def cancel_order(self, order_id: int):
        if order_id in self.active_orders:
            self.active_orders[order_id]['status'] = OrderStatus.CANCELLED.value
            del self.active_orders[order_id]
            logger.info(f'Order cancelled: {order_id}')
