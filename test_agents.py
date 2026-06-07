import asyncio
from unittest.mock import MagicMock
from trading.feature_engine import FeatureEngine
from trading.trend_agent import TrendAgent
from trading.mean_reversion_agent import MeanReversionAgent
from trading.volatility_arbitrage_agent import VolatilityArbitrageAgent
from trading.liquidity_hunter_agent import LiquidityHunterAgent
from trading.sentiment_agent import SentimentAgent
from trading.market_making_agent import MarketMakingAgent
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
    
    agents = {
        "trend":         TrendAgent(mem),
        "mean_reversion": MeanReversionAgent(mem),
        "volatility":    VolatilityArbitrageAgent(mem),
        "liquidity":     LiquidityHunterAgent(mem),
        "sentiment":     SentimentAgent(mem),
        "market_making": MarketMakingAgent(mem),
    }
    
    for name, agent in agents.items():
        try:
            result = await agent.analyze(bars, features, {})
        except TypeError:
            result = await agent.analyze(bars, features)
        print(f"{name:20s} signal={result.get('signal','?'):10s} conf={result.get('confidence',0):.3f}")

asyncio.run(test())
