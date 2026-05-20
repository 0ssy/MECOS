import pandas as pd
import numpy as np
from loguru import logger
from typing import Dict, Any, List
from trading.config import TradingConfig

class RegimeDetectionAgent:
    def __init__(self, memory_system):
        self.memory = memory_system
        logger.info("RegimeDetectionAgent initialized.")

    def calculate_regime(self, df: pd.DataFrame) -> str:
        if df.empty or len(df) < TradingConfig.REGIME_LOOKBACK: return "unknown"
        close = df['close']
        tr = pd.concat([df['high'] - df['low'], (df['high'] - close.shift()).abs(), (df['low'] - close.shift()).abs()], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        vol_ratio = atr.iloc[-1] / atr.rolling(TradingConfig.REGIME_LOOKBACK).mean().iloc[-1]
        
        if vol_ratio > TradingConfig.VOLATILITY_THRESHOLD: return "panic" if close.iloc[-1] < close.iloc[-5] else "volatile"
        
        ema_f, ema_s = close.ewm(span=12).mean(), close.ewm(span=26).mean()
        trend_s = (ema_f - ema_s).abs().iloc[-1] / close.iloc[-1]
        if trend_s > TradingConfig.TREND_THRESHOLD: return "trending"
        
        return "ranging"

    async def detect_regime(self, market_data: List[Dict]) -> str:
        df = pd.DataFrame(market_data)
        regime = self.calculate_regime(df)
        logger.info(f"Market regime detected: {regime}")
        return regime
