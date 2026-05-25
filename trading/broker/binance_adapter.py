import hashlib
import hmac
import os
import time
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List
from urllib.parse import urlencode

import aiohttp
from dotenv import load_dotenv
from loguru import logger

from .base_adapter import BrokerAdapter


class BinanceAdapter(BrokerAdapter):
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv('BINANCE_API_KEY', '').strip()
        self.secret_key = os.getenv('BINANCE_SECRET_KEY', '').strip()
        self.base_url = os.getenv('BINANCE_BASE_URL', 'https://api.binance.com').rstrip('/')
        self.ws_url = os.getenv('BINANCE_WS_URL', 'wss://stream.binance.com:9443').rstrip('/')
        if 'testnet.binance.vision' in self.base_url and 'testnet.binance.vision' not in self.ws_url:
            self.ws_url = 'wss://stream.testnet.binance.vision:9443'

        if not self.api_key or not self.secret_key:
            raise RuntimeError('Missing Binance API credentials (BINANCE_API_KEY/BINANCE_SECRET_KEY).')

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)

    @staticmethod
    def _to_binance_symbol(symbol: str) -> str:
        symbol = str(symbol).upper().strip()
        if symbol.endswith('USDT'):
            return symbol
        if '/' in symbol:
            base, quote = symbol.split('/', 1)
            quote = quote.upper()
            if quote == 'USD':
                quote = 'USDT'
            return f'{base.upper()}{quote}'
        return symbol

    @staticmethod
    def _to_internal_symbol(binance_symbol: str) -> str:
        symbol = binance_symbol.upper()
        if symbol.endswith('USDT') and len(symbol) > 4:
            return f"{symbol[:-4]}/USD"
        return symbol

    def _signed_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        enriched = {**params, 'timestamp': int(time.time() * 1000), 'recvWindow': 5000}
        query = urlencode(enriched, doseq=True)
        signature = hmac.new(self.secret_key.encode('utf-8'), query.encode('utf-8'), hashlib.sha256).hexdigest()
        enriched['signature'] = signature
        return enriched

    async def _request(
        self,
        method: str,
        path: str,
        params: Dict[str, Any] | None = None,
        signed: bool = False,
    ) -> Any:
        params = params or {}
        headers = {'X-MBX-APIKEY': self.api_key}
        final_params = self._signed_params(params) if signed else params
        url = f'{self.base_url}{path}'

        async with aiohttp.ClientSession() as session:
            async with session.request(method.upper(), url, params=final_params, headers=headers, timeout=20) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    raise RuntimeError(f'Binance API error {resp.status}: {text}')
                if not text:
                    return {}
                return await resp.json()

    async def get_live_bars(self, symbol: str, timeframe: str = '1Min', limit: int = 200) -> List[Dict[str, Any]]:
        interval_map = {
            '1Min': '1m',
            '5Min': '5m',
            '15Min': '15m',
            '1Hour': '1h',
            '1Day': '1d',
        }
        interval = interval_map.get(timeframe, '1m')
        binance_symbol = self._to_binance_symbol(symbol)
        data = await self._request('GET', '/api/v3/klines', params={'symbol': binance_symbol, 'interval': interval, 'limit': max(5, int(limit))})
        output = []
        for row in data:
            output.append(
                {
                    'symbol': self._to_internal_symbol(binance_symbol),
                    'timestamp': datetime.utcfromtimestamp(int(row[0]) / 1000).isoformat(),
                    'open': self._safe_float(row[1]),
                    'high': self._safe_float(row[2]),
                    'low': self._safe_float(row[3]),
                    'close': self._safe_float(row[4]),
                    'volume': max(1.0, self._safe_float(row[5], 1.0)),
                }
            )
        return output[-limit:]

    async def submit_order(self, symbol: str, qty: float, side: str, order_type: str = 'market') -> Dict[str, Any]:
        payload = {
            'symbol': self._to_binance_symbol(symbol),
            'side': str(side).upper(),
            'type': str(order_type).upper(),
            'quantity': float(qty),
        }
        result = await self._request('POST', '/api/v3/order', params=payload, signed=True)
        return {
            'id': result.get('orderId'),
            'symbol': self._to_internal_symbol(str(result.get('symbol', payload['symbol']))),
            'qty': self._safe_float(result.get('origQty', qty)),
            'side': payload['side'],
            'status': str(result.get('status', 'UNKNOWN')),
        }

    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        payload = {'orderId': int(order_id)}
        result = await self._request('DELETE', '/api/v3/order', params=payload, signed=True)
        return {'status': str(result.get('status', 'CANCELED')), 'order_id': int(order_id)}

    async def get_positions(self) -> List[Dict[str, Any]]:
        account = await self._request('GET', '/api/v3/account', signed=True)
        balances = account.get('balances', [])
        positions: List[Dict[str, Any]] = []
        for bal in balances:
            free = self._safe_float(bal.get('free'))
            locked = self._safe_float(bal.get('locked'))
            qty = free + locked
            if qty <= 0:
                continue
            asset = str(bal.get('asset', '')).upper()
            positions.append(
                {
                    'symbol': f'{asset}/USD',
                    'qty': qty,
                    'market_value': 0.0,
                    'unrealized_pl': 0.0,
                }
            )
        return positions

    async def get_account(self) -> Dict[str, Any]:
        account = await self._request('GET', '/api/v3/account', signed=True)
        return {
            'cash': 0.0,
            'portfolio_value': 0.0,
            'buying_power': 0.0,
            'equity': 0.0,
            'status': str(account.get('accountType', 'CONNECTED')),
        }

    async def stream_quotes(self, symbols: List[str], callback: Callable[[str, Dict[str, Any]], Awaitable[None]]) -> None:
        stream_symbols = [self._to_binance_symbol(sym).lower() for sym in symbols]
        if not stream_symbols:
            raise RuntimeError('No Binance symbols provided for streaming.')

        stream_path = '/'.join([f'{sym}@bookTicker' for sym in stream_symbols])
        ws_endpoint = f'{self.ws_url}/stream?streams={stream_path}'
        logger.info(f'Starting Binance quote stream for: {symbols}')

        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(ws_endpoint, heartbeat=20) as ws:
                async for msg in ws:
                    if msg.type != aiohttp.WSMsgType.TEXT:
                        continue
                    payload = msg.json()
                    data = payload.get('data', {})
                    if not data:
                        continue
                    binance_symbol = str(data.get('s', '')).upper()
                    if not binance_symbol:
                        continue
                    bid = self._safe_float(data.get('b'))
                    ask = self._safe_float(data.get('a'))
                    bid_size = self._safe_float(data.get('B'))
                    ask_size = self._safe_float(data.get('A'))
                    close = (bid + ask) / 2.0 if bid > 0.0 and ask > 0.0 else max(bid, ask)
                    if close <= 0.0:
                        continue
                    low_candidates = [x for x in (bid, ask, close) if x > 0.0]
                    symbol = self._to_internal_symbol(binance_symbol)
                    tick = {
                        'symbol': symbol,
                        'open': close,
                        'high': max(close, bid, ask),
                        'low': min(low_candidates) if low_candidates else close,
                        'close': close,
                        'volume': max(1.0, bid_size + ask_size),
                        'timestamp': datetime.utcnow().isoformat(),
                        'bid': bid,
                        'ask': ask,
                        'source': 'binance_bookticker',
                    }
                    await callback(symbol, tick)
