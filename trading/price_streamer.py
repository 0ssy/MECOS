from __future__ import annotations

from typing import Awaitable, Callable, Dict, List

import asyncio
import json

import websockets
from loguru import logger


async def stream_binance_prices(
    symbols: List[str],
    callback: Callable[[Dict[str, float | str]], Awaitable[None] | None],
) -> None:
    """Streams ticker updates from Binance public websocket."""
    if not symbols:
        return
    normalized = [str(s).strip().lower() for s in symbols if s]
    streams = "/".join(f"{s}@ticker" for s in normalized)
    url = f"wss://stream.binance.com:9443/stream?streams={streams}"

    while True:
        try:
            async with websockets.connect(url) as ws:
                while True:
                    payload = json.loads(await ws.recv())
                    ticker = payload.get("data", {})
                    payload_out = {
                        "symbol": str(ticker.get("s", "")),
                        "price": float(ticker.get("c", 0.0) or 0.0),
                        "change_pct": float(ticker.get("P", 0.0) or 0.0),
                        "volume": float(ticker.get("v", 0.0) or 0.0),
                    }
                    maybe = callback(payload_out)
                    if asyncio.iscoroutine(maybe):
                        await maybe
        except Exception as exc:
            logger.warning(f"Binance public stream error: {exc}")
            await asyncio.sleep(2)
