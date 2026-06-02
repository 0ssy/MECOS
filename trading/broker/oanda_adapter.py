import asyncio
import json
import os
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List

import aiohttp
from dotenv import load_dotenv
from loguru import logger

from .base_adapter import BrokerAdapter


class OandaAdapter(BrokerAdapter):
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv('OANDA_API_KEY', '').strip()
        self.account_id = os.getenv('OANDA_ACCOUNT_ID', '').strip()
        self.environment = os.getenv('OANDA_ENV', 'practice').strip().lower()
        self.base_url = os.getenv(
            'OANDA_BASE_URL',
            'https://api-fxpractice.oanda.com/v3' if self.environment == 'practice' else 'https://api-fxtrade.oanda.com/v3',
        ).rstrip('/')
        self.stream_url = os.getenv(
            'OANDA_STREAM_URL',
            'https://stream-fxpractice.oanda.com/v3'
            if self.environment == 'practice'
            else 'https://stream-fxtrade.oanda.com/v3',
        ).rstrip('/')

        if not self.api_key or not self.account_id:
            raise RuntimeError('Missing OANDA credentials (OANDA_API_KEY/OANDA_ACCOUNT_ID).')

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)

    @staticmethod
    def _to_oanda_instrument(symbol: str) -> str:
        token = str(symbol).upper().strip()
        if '/' in token:
            left, right = token.split('/', 1)
            return f'{left}_{right}'
        if len(token) == 6 and token.isalpha():
            return f'{token[:3]}_{token[3:]}'
        return token

    @staticmethod
    def _to_internal_symbol(instrument: str) -> str:
        token = str(instrument).upper().strip()
        if '_' in token:
            left, right = token.split('_', 1)
            return f'{left}/{right}'
        return token

    @staticmethod
    def _to_oanda_granularity(timeframe: str) -> str:
        mapping = {
            '1Min': 'M1',
            '5Min': 'M5',
            '15Min': 'M15',
            '1Hour': 'H1',
            '1Day': 'D',
        }
        return mapping.get(str(timeframe), 'M1')

    def _headers(self) -> Dict[str, str]:
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

    async def _request(
        self,
        method: str,
        path: str,
        params: Dict[str, Any] | None = None,
        payload: Dict[str, Any] | None = None,
    ) -> Any:
        url = f'{self.base_url}{path}'
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method.upper(),
                url,
                params=params or {},
                json=payload,
                headers=self._headers(),
                timeout=25,
            ) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    raise RuntimeError(f'OANDA API error {resp.status}: {text}')
                if not text:
                    return {}
                return json.loads(text)

    async def get_live_bars(self, symbol: str, timeframe: str = '1Min', limit: int = 200) -> List[Dict[str, Any]]:
        instrument = self._to_oanda_instrument(symbol)
        granularity = self._to_oanda_granularity(timeframe)
        response = await self._request(
            'GET',
            f'/instruments/{instrument}/candles',
            params={
                'granularity': granularity,
                'count': max(5, int(limit)),
                'price': 'M',
            },
        )
        candles = response.get('candles', [])
        output: List[Dict[str, Any]] = []
        normalized_symbol = self._to_internal_symbol(instrument)
        for candle in candles[-limit:]:
            if not candle.get('mid'):
                continue
            mid = candle['mid']
            output.append(
                {
                    'symbol': normalized_symbol,
                    'timestamp': str(candle.get('time')),
                    'open': self._safe_float(mid.get('o')),
                    'high': self._safe_float(mid.get('h')),
                    'low': self._safe_float(mid.get('l')),
                    'close': self._safe_float(mid.get('c')),
                    'volume': max(1.0, self._safe_float(candle.get('volume'), default=1.0)),
                }
            )
        return output

    async def submit_order(self, symbol: str, qty: float, side: str, order_type: str = 'market') -> Dict[str, Any]:
        instrument = self._to_oanda_instrument(symbol)
        units = max(1, int(abs(float(qty))))
        if str(side).upper() == 'SELL':
            units = -units
        order_payload = {
            'order': {
                'instrument': instrument,
                'units': str(units),
                'type': 'MARKET',
                'positionFill': 'DEFAULT',
            }
        }
        response = await self._request(
            'POST',
            f'/accounts/{self.account_id}/orders',
            payload=order_payload,
        )
        tx = response.get('orderFillTransaction') or response.get('orderCreateTransaction') or {}
        return {
            'id': tx.get('id') or response.get('lastTransactionID'),
            'symbol': self._to_internal_symbol(instrument),
            'qty': float(abs(units)),
            'side': 'BUY' if units > 0 else 'SELL',
            'status': 'FILLED' if response.get('orderFillTransaction') else 'SUBMITTED',
        }

    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        response = await self._request(
            'PUT',
            f'/accounts/{self.account_id}/orders/{order_id}/cancel',
        )
        tx = response.get('orderCancelTransaction') or {}
        return {
            'status': 'CANCELLED',
            'order_id': str(tx.get('orderID') or order_id),
        }

    async def get_positions(self) -> List[Dict[str, Any]]:
        response = await self._request('GET', f'/accounts/{self.account_id}/openPositions')
        positions = response.get('positions', [])
        output: List[Dict[str, Any]] = []
        for pos in positions:
            instrument = self._to_internal_symbol(str(pos.get('instrument', '')))
            long_units = self._safe_float(pos.get('long', {}).get('units'))
            short_units = self._safe_float(pos.get('short', {}).get('units'))
            net_units = long_units + short_units
            if net_units == 0:
                continue
            output.append(
                {
                    'symbol': instrument,
                    'qty': net_units,
                    'market_value': 0.0,
                    'unrealized_pl': self._safe_float(pos.get('unrealizedPL')),
                }
            )
        return output

    async def get_account(self) -> Dict[str, Any]:
        response = await self._request('GET', f'/accounts/{self.account_id}/summary')
        account = response.get('account', {})
        nav = self._safe_float(account.get('NAV'))
        balance = self._safe_float(account.get('balance'))
        margin = self._safe_float(account.get('marginAvailable'))
        return {
            'cash': balance,
            'portfolio_value': nav,
            'buying_power': margin,
            'equity': nav,
            'status': str(account.get('state', 'CONNECTED')),
        }

    async def stream_quotes(self, symbols: List[str], callback: Callable[[str, Dict[str, Any]], Awaitable[None]]) -> None:
        instruments = [self._to_oanda_instrument(symbol) for symbol in symbols]
        if not instruments:
            raise RuntimeError('No OANDA symbols provided for streaming.')

        params = {'instruments': ','.join(instruments)}
        endpoint = f'{self.stream_url}/accounts/{self.account_id}/pricing/stream'
        reconnect_attempt = 0

        while True:
            try:
                async with aiohttp.ClientSession(headers=self._headers()) as session:
                    logger.info(f'Starting OANDA quote stream for: {symbols}')
                    async with session.get(endpoint, params=params, timeout=None) as resp:
                        if resp.status >= 400:
                            text = await resp.text()
                            raise RuntimeError(f'OANDA stream error {resp.status}: {text}')

                        reconnect_attempt = 0
                        while not resp.content.at_eof():
                            raw_line = await resp.content.readline()
                            if not raw_line:
                                break
                            line = raw_line.decode('utf-8', errors='ignore').strip()
                            if not line:
                                continue
                            try:
                                event = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            if event.get('type') != 'PRICE':
                                continue
                            instrument = str(event.get('instrument', ''))
                            symbol = self._to_internal_symbol(instrument)
                            bids = event.get('bids', [])
                            asks = event.get('asks', [])
                            bid = self._safe_float(bids[0]['price']) if bids else 0.0
                            ask = self._safe_float(asks[0]['price']) if asks else 0.0
                            close = (bid + ask) / 2.0 if bid > 0.0 and ask > 0.0 else max(bid, ask)
                            if close <= 0.0:
                                continue
                            low_candidates = [x for x in (bid, ask, close) if x > 0.0]
                            tick = {
                                'symbol': symbol,
                                'open': close,
                                'high': max(close, bid, ask),
                                'low': min(low_candidates) if low_candidates else close,
                                'close': close,
                                'volume': 1.0,
                                'timestamp': str(event.get('time') or datetime.utcnow().isoformat()),
                                'bid': bid,
                                'ask': ask,
                                'source': 'oanda_price',
                            }
                            await callback(symbol, tick)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                reconnect_attempt += 1
                backoff = min(2 ** reconnect_attempt, 60)
                logger.error(f'OANDA quote stream disconnected (attempt {reconnect_attempt}): {exc}')
                await asyncio.sleep(backoff)
