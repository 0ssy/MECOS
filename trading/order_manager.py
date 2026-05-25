import inspect
from typing import Dict, Any, Callable, Awaitable, List
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
        self._status_callbacks: List[Callable[[Dict[str, Any]], Awaitable[None]]] = []
        logger.info('Order Manager initialized')

    def register_status_callback(self, callback: Callable[[Dict[str, Any]], Awaitable[None]]):
        self._status_callbacks.append(callback)

    async def _emit_status(self, order_id: int, order: Dict[str, Any], status: str, **metadata):
        payload = {
            'order_id': int(order_id),
            'symbol': order.get('symbol', ''),
            'side': order.get('side', ''),
            'size': float(order.get('size', 0.0) or 0.0),
            'price': float(order.get('price', 0.0) or 0.0),
            'status': status,
            **metadata,
        }
        for callback in self._status_callbacks:
            try:
                result = callback(payload)
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:
                logger.error(f'Order status callback failed: {exc}')

    async def create_order(self, order: Dict) -> int:
        order['status'] = OrderStatus.CREATED.value
        order_id = self.database.insert_order(order)
        self.active_orders[order_id] = order
        self.database.update_order_status(order_id, OrderStatus.CREATED.value)
        logger.info(f'Order created: {order_id}')
        await self._emit_status(order_id, order, OrderStatus.CREATED.value)
        return order_id

    async def submit_order(self, order_id: int):
        if order_id in self.active_orders:
            self.active_orders[order_id]['status'] = OrderStatus.SUBMITTED.value
            self.database.update_order_status(order_id, OrderStatus.SUBMITTED.value)
            logger.info(f'Order submitted: {order_id}')
            await self._emit_status(order_id, self.active_orders[order_id], OrderStatus.SUBMITTED.value)

    async def fill_order(self, order_id: int, fill_price: float, fill_size: float):
        if order_id not in self.active_orders:
            logger.warning(f'Fill received for unknown order_id={order_id}; creating transient record')
            self.active_orders[order_id] = {
                'symbol': '',
                'side': '',
                'size': float(fill_size),
                'price': float(fill_price),
                'status': OrderStatus.SUBMITTED.value,
            }
        order = self.active_orders[order_id]
        
        self.database.insert_fill({
            'order_id': order_id,
            'symbol': order['symbol'],
            'size': fill_size,
            'price': fill_price
        })
        
        if fill_size >= order['size']:
            order['status'] = OrderStatus.FILLED.value
            self.database.update_order_status(order_id, OrderStatus.FILLED.value)
            logger.info(f'Order filled: {order_id}')
            await self._emit_status(
                order_id,
                order,
                OrderStatus.FILLED.value,
                fill_price=float(fill_price),
                fill_size=float(fill_size),
            )
            self.active_orders.pop(order_id, None)
        else:
            order['status'] = OrderStatus.PARTIALLY_FILLED.value
            self.database.update_order_status(order_id, OrderStatus.PARTIALLY_FILLED.value)
            logger.info(f'Order partially filled: {order_id}')
            await self._emit_status(
                order_id,
                order,
                OrderStatus.PARTIALLY_FILLED.value,
                fill_price=float(fill_price),
                fill_size=float(fill_size),
            )

    async def cancel_order(self, order_id: int):
        if order_id in self.active_orders:
            self.active_orders[order_id]['status'] = OrderStatus.CANCELLED.value
            self.database.update_order_status(order_id, OrderStatus.CANCELLED.value)
            await self._emit_status(order_id, self.active_orders[order_id], OrderStatus.CANCELLED.value)
            del self.active_orders[order_id]
            logger.info(f'Order cancelled: {order_id}')
