import asyncio
from unittest.mock import MagicMock
from trading.feature_engine import FeatureEngine
import yfinance as yf

async def test():
    mem = MagicMock()
    fe = FeatureEngine(mem)
    ticker = yf.Ticker("BTC-USD")
    df = ticker.history(period="30d", interval="1h", auto_adjust=True)
    bars = [{"close": float(r.Close), "high": float(r.High), "low": float(r.Low),
             "volume": float(r.Volume), "open": float(r.Open)}
            for _, r in df.tail(100).iterrows()]
    features = await fe.compute_features(bars)
    for k, v in sorted(features.items()):
        print(f"{k}: {v}")

asyncio.run(test())
