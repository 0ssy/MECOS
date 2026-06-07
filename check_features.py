import asyncio
from unittest.mock import MagicMock
from trading.feature_engine import FeatureEngine
from trading.market_data_stream import MarketDataStream
import yfinance as yf

async def test():
    mem = MagicMock()
    fe = FeatureEngine(mem)
    ticker = yf.Ticker("BTC-USD")
    df = ticker.history(period="5d", interval="5m", auto_adjust=True)
    bars = [{"close": float(r.Close), "high": float(r.High), "low": float(r.Low),
             "volume": float(r.Volume), "open": float(r.Open)}
            for _, r in df.tail(100).iterrows()]
    features = await fe.compute_features(bars)
    important = {k: v for k, v in features.items()
                 if k in ["roc_20","trend_strength","realized_volatility","rsi_14","atr","macd"]}
    print(important)

asyncio.run(test())
