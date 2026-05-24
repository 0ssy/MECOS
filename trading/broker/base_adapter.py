from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Dict, List


class BrokerAdapter(ABC):
    @abstractmethod
    async def get_live_bars(self, symbol: str, timeframe: str = '1Min', limit: int = 200) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def submit_order(self, symbol: str, qty: float, side: str, order_type: str = 'market') -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_positions(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def get_account(self) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def stream_quotes(self, symbols: List[str], callback: Callable[[str, Dict[str, Any]], Awaitable[None]]) -> None:
        raise NotImplementedError
