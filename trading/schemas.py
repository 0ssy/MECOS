from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Signal:
    symbol: str
    decision: str
    confidence: float
    buy_score: float
    sell_score: float
    edge: float
    regime: str
    session: str
    reasons: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class Decision:
    symbol: str
    action: str
    confidence: float
    threshold: float
    approved: bool
    reasons: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class Order:
    symbol: str
    side: str
    size: float
    price: float
    status: str
    order_id: Optional[int] = None


@dataclass(frozen=True)
class Position:
    symbol: str
    size: float
    avg_price: float
    mark_price: float
    sector: str = "unknown"


@dataclass(frozen=True)
class RiskState:
    portfolio_value: float
    sector_exposure: Dict[str, float] = field(default_factory=dict)
    correlated_positions: int = 0
    drawdown: float = 0.0


@dataclass(frozen=True)
class MarketEvent:
    event_type: str
    symbol: str
    timestamp: str
    payload: Dict[str, Any] = field(default_factory=dict)
