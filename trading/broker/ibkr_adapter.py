import asyncio
import math
import os
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional

from loguru import logger

# Python 3.14 compatibility for eventkit/ib_insync import-time loop access.
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from ib_insync import IB, Stock, Forex, Crypto, MarketOrder

from .base_adapter import BrokerAdapter


class IbkrAdapter(BrokerAdapter):
    def __init__(self, host: Optional[str] = None, port: Optional[int] = None, client_id: Optional[int] = None):
        self.host = host or os.getenv('IBKR_HOST', '127.0.0.1')
        self.port = int(port or os.getenv('IBKR_PORT', '7497'))
        self.client_id = int(client_id or os.getenv('IBKR_CLIENT_ID', '1'))
        self.ib = IB()
        self._subscribed_tickers = []
        self._trade_by_order_id: Dict[int, Any] = {}

    async def _connect_async(self):
        if self.ib.isConnected():
            return
        ports = [self.port, 7497, 7496, 4001, 4002]
        seen = set()
        ordered_ports = []
        for p in ports:
            if p not in seen:
                ordered_ports.append(p)
                seen.add(p)

        last_error = None
        for p in ordered_ports:
            try:
                logger.info(f'Connecting to IBKR at {self.host}:{p} clientId={self.client_id}')
                await self.ib.connectAsync(self.host, p, clientId=self.client_id, timeout=6)
                if self.ib.isConnected():
                    self.port = p
                    # Delayed market data type fallback when live entitlements are unavailable.
                    self.ib.reqMarketDataType(3)
                    logger.info(f'IBKR connected on port {p}')
                    return
            except Exception as exc:
                last_error = exc
                continue

        raise RuntimeError(f'IBKR connection failed on all candidate ports: {last_error}')

    async def _resolve_contract(self, symbol: str):
        symbol = str(symbol).upper().strip()
        if not symbol:
            raise ValueError('Empty symbol')

        candidates = [Stock(symbol, 'SMART', 'USD')]

        if len(symbol) == 6 and symbol.isalpha():
            candidates.insert(0, Forex(symbol))

        if '/' in symbol:
            parts = symbol.split('/')
            if len(parts) == 2 and parts[1] == 'USD':
                candidates.insert(0, Crypto(parts[0], 'PAXOS', 'USD'))

        if symbol.endswith('USDT') and len(symbol) >= 7:
            base = symbol[:-4]
            candidates.insert(0, Crypto(base, 'PAXOS', 'USD'))

        last_error = None
        for contract in candidates:
            try:
                qualified = await self.ib.qualifyContractsAsync(contract)
                if qualified:
                    return qualified[0]
            except Exception as exc:
                last_error = exc
        raise RuntimeError(f'Unable to resolve IBKR contract for {symbol}: {last_error}')

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            val = float(value)
            if math.isnan(val) or math.isinf(val):
                return float(default)
            return val
        except Exception:
            return float(default)

    async def get_live_bars(self, symbol: str, timeframe: str = '1Min', limit: int = 200) -> List[Dict[str, Any]]:
        await self._connect_async()
        contract = await self._resolve_contract(symbol)
        bar_size_map = {
            '1Min': '1 min',
            '5Min': '5 mins',
            '15Min': '15 mins',
            '1Hour': '1 hour',
            '1Day': '1 day',
        }
        bar_size = bar_size_map.get(timeframe, '1 min')
        bars = await self.ib.reqHistoricalDataAsync(
            contract,
            endDateTime='',
            durationStr=f'{max(limit, 10)} D',
            barSizeSetting=bar_size,
            whatToShow='TRADES',
            useRTH=True,
            formatDate=1,
            keepUpToDate=False,
            chartOptions=[],
        )
        output = []
        for bar in list(bars)[-limit:]:
            output.append(
                {
                    'symbol': symbol,
                    'timestamp': str(bar.date),
                    'open': self._safe_float(bar.open),
                    'high': self._safe_float(bar.high),
                    'low': self._safe_float(bar.low),
                    'close': self._safe_float(bar.close),
                    'volume': max(1.0, self._safe_float(bar.volume, default=1.0)),
                }
            )
        return output

    async def submit_order(self, symbol: str, qty: float, side: str, order_type: str = 'market') -> Dict[str, Any]:
        await self._connect_async()
        contract = await self._resolve_contract(symbol)
        action = 'BUY' if str(side).upper() == 'BUY' else 'SELL'
        order = MarketOrder(action, float(qty))
        trade = self.ib.placeOrder(contract, order)
        order_id = int(trade.order.orderId)
        self._trade_by_order_id[order_id] = trade
        return {
            'id': order_id,
            'symbol': symbol,
            'qty': float(qty),
            'side': action,
            'status': str(trade.orderStatus.status),
        }

    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        await self._connect_async()
        oid = int(order_id)
        trade = self._trade_by_order_id.get(oid)
        if trade is None:
            return {'status': 'UNKNOWN_ORDER_ID', 'order_id': oid}
        self.ib.cancelOrder(trade.order)
        return {'status': 'CANCELLED', 'order_id': oid}

    async def get_positions(self) -> List[Dict[str, Any]]:
        await self._connect_async()
        positions = self.ib.positions()
        return [
            {
                'symbol': p.contract.symbol,
                'qty': self._safe_float(p.position),
                'avg_cost': self._safe_float(p.avgCost),
                'market_value': 0.0,
                'unrealized_pl': 0.0,
            }
            for p in positions
        ]

    async def get_account(self) -> Dict[str, Any]:
        await self._connect_async()
        summary = self.ib.accountSummary()
        fields = {item.tag: self._safe_float(item.value) for item in summary if item.tag in {'CashBalance', 'NetLiquidation', 'BuyingPower'}}
        return {
            'cash': fields.get('CashBalance', 0.0),
            'portfolio_value': fields.get('NetLiquidation', 0.0),
            'buying_power': fields.get('BuyingPower', 0.0),
            'equity': fields.get('NetLiquidation', 0.0),
            'status': 'CONNECTED' if self.ib.isConnected() else 'DISCONNECTED',
        }

    async def stream_quotes(self, symbols: List[str], callback: Callable[[str, Dict[str, Any]], Awaitable[None]]) -> None:
        await self._connect_async()

        self._subscribed_tickers = []
        for symbol in symbols:
            try:
                contract = await self._resolve_contract(symbol)
            except Exception as exc:
                logger.warning(f'Skipping unsupported IBKR symbol {symbol}: {exc}')
                continue
            ticker = self.ib.reqMktData(contract, '', False, False)
            self._subscribed_tickers.append((symbol, ticker))

        if not self._subscribed_tickers:
            raise RuntimeError('No valid IBKR contracts were resolved for streaming.')

        logger.info(f'Starting IBKR quote stream for: {symbols}')
        try:
            while self.ib.isConnected():
                await asyncio.sleep(0.25)
                ts = datetime.utcnow().isoformat()
                for symbol, ticker in self._subscribed_tickers:
                    bid = self._safe_float(ticker.bid)
                    ask = self._safe_float(ticker.ask)
                    last = self._safe_float(ticker.last)
                    close = last if last > 0 else ((bid + ask) / 2.0 if bid > 0 and ask > 0 else max(bid, ask))
                    if close <= 0:
                        continue

                    low_candidates = [x for x in (bid, ask, close) if x > 0]
                    tick = {
                        'symbol': symbol,
                        'open': close,
                        'high': max([close, bid, ask]),
                        'low': min(low_candidates) if low_candidates else close,
                        'close': close,
                        'volume': max(1.0, self._safe_float(ticker.lastSize, default=1.0)),
                        'timestamp': ts,
                        'bid': bid,
                        'ask': ask,
                        'source': 'ibkr_quote',
                    }
                    await callback(symbol, tick)
        finally:
            for _, ticker in self._subscribed_tickers:
                try:
                    self.ib.cancelMktData(ticker.contract)
                except Exception:
                    pass
            self._subscribed_tickers = []
