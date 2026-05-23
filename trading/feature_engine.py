"""
Advanced Feature Engineering for Quantitative Trading
Computes institutional-grade market features
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Any
from loguru import logger

class FeatureEngine:
    """Computes all technical and statistical features"""
    
    def __init__(self, memory):
        self.memory = memory
        logger.info("Feature Engine initialized")
    
    async def compute_features(self, data: List[Dict]) -> Dict[str, Any]:
        """Compute comprehensive feature set"""
        df = pd.DataFrame(data)
        
        features = {}
        
        # 1. VOLATILITY FEATURES
        features.update(self._compute_volatility_features(df))
        
        # 2. MOMENTUM FEATURES
        features.update(self._compute_momentum_features(df))
        
        # 3. LIQUIDITY FEATURES
        features.update(self._compute_liquidity_features(df))
        
        # 4. ENTROPY & INFORMATION
        features.update(self._compute_entropy_features(df))
        
        # 5. CORRELATION & DEPENDENCY
        features.update(self._compute_correlation_features(df))
        
        # 6. REGIME FEATURES
        features.update(self._compute_regime_features(df))
        
        return features
    
    def _compute_volatility_features(self, df: pd.DataFrame) -> Dict:
        """Realized volatility, ATR, volatility clustering"""
        close = df['close'].values
        high = df['high'].values if 'high' in df.columns else close
        low = df['low'].values if 'low' in df.columns else close
        
        # Realized volatility (20-period)
        returns = np.diff(np.log(close + 1e-10))
        realized_vol = np.std(returns[-20:]) * np.sqrt(252) if len(returns) >= 20 else 0
        
        # ATR (Average True Range)
        if len(close) > 1:
            tr = np.maximum(high[1:] - low[1:], 
                           np.abs(high[1:] - close[:-1]))
            tr = np.maximum(tr, np.abs(low[1:] - close[:-1]))
            atr = np.mean(tr[-14:]) if len(tr) >= 14 else 0
        else:
            atr = 0
        
        # Volatility clustering (GARCH-like)
        vol_series = pd.Series(returns).rolling(5).std()
        vol_clustering = vol_series.autocorr(1) if len(vol_series) > 5 else 0
        
        return {
            "realized_volatility": float(realized_vol),
            "atr": float(atr),
            "volatility_clustering": float(vol_clustering) if not np.isnan(vol_clustering) else 0,
            "volatility_percentile": self._percentile(vol_series.values, realized_vol)
        }
    
    def _compute_momentum_features(self, df: pd.DataFrame) -> Dict:
        """Momentum, acceleration, trend strength"""
        close = df['close'].values
        
        # Rate of change
        roc_5 = (close[-1] / close[-5] - 1) if len(close) >= 5 else 0
        roc_20 = (close[-1] / close[-20] - 1) if len(close) >= 20 else 0
        
        # Momentum acceleration
        mom_5 = close[-1] - close[-5] if len(close) >= 5 else 0
        mom_10 = close[-1] - close[-10] if len(close) >= 10 else 0
        acceleration = mom_5 - (mom_10 - mom_5) if len(close) >= 10 else 0
        
        # Trend strength (ADX-like)
        trend_strength = abs(roc_20) if len(close) >= 20 else 0
        
        return {
            "roc_5": float(roc_5),
            "roc_20": float(roc_20),
            "momentum_acceleration": float(acceleration),
            "trend_strength": float(trend_strength)
        }
    
    def _compute_liquidity_features(self, df: pd.DataFrame) -> Dict:
        """Volume, spread, liquidity pressure"""
        if 'volume' not in df.columns:
            return {"volume_ratio": 1.0, "spread_pressure": 0, "liquidity_score": 1.0}
        
        volume = df['volume'].values
        close = df['close'].values
        high = df['high'].values if 'high' in df.columns else close
        low = df['low'].values if 'low' in df.columns else close
        
        # Volume ratio
        avg_vol = np.mean(volume[-20:]) if len(volume) >= 20 else 1
        current_vol = volume[-1]
        volume_ratio = current_vol / avg_vol if avg_vol > 0 else 1
        
        # Spread pressure
        spread = (high[-1] - low[-1]) / close[-1] if close[-1] > 0 else 0
        
        return {
            "volume_ratio": float(volume_ratio),
            "spread_pressure": float(spread),
            "liquidity_score": float(volume_ratio * (1 - spread))
        }
    
    def _compute_entropy_features(self, df: pd.DataFrame) -> Dict:
        """Market entropy, information content"""
        close = df['close'].values
        
        if len(close) < 20:
            return {"entropy": 0, "information_ratio": 0}
        
        # Shannon entropy of returns
        returns = np.diff(np.log(close[-20:] + 1e-10))
        hist, _ = np.histogram(returns, bins=10, density=True)
        hist = hist[hist > 0]
        entropy = -np.sum(hist * np.log(hist + 1e-10))
        
        # Information ratio (signal/noise)
        signal = abs(np.mean(returns))
        noise = np.std(returns)
        info_ratio = signal / noise if noise > 0 else 0
        
        return {
            "entropy": float(entropy),
            "information_ratio": float(info_ratio)
        }
    
    def _compute_correlation_features(self, df: pd.DataFrame) -> Dict:
        """Auto-correlation, mean reversion"""
        close = df['close'].values
        
        if len(close) < 20:
            return {"autocorr_1": 0, "mean_reversion_score": 0, "z_score": 0}
        
        returns = np.diff(np.log(close + 1e-10))
        
        # Lag-1 autocorrelation
        if len(returns) > 1:
            autocorr = np.corrcoef(returns[:-1], returns[1:])[0, 1]
        else:
            autocorr = 0
        
        # Mean reversion (Hurst exponent approximation)
        mean_close = np.mean(close[-20:])
        std_close = np.std(close[-20:])
        z_score = (close[-1] - mean_close) / std_close if std_close > 0 else 0
        mean_reversion = -autocorr * abs(z_score)
        
        return {
            "autocorr_1": float(autocorr) if not np.isnan(autocorr) else 0,
            "mean_reversion_score": float(mean_reversion) if not np.isnan(mean_reversion) else 0,
            "z_score": float(z_score)
        }
    
    def _compute_regime_features(self, df: pd.DataFrame) -> Dict:
        """Regime indicators"""
        close = df['close'].values
        
        if len(close) < 50:
            return {"regime_trend": 0, "regime_volatility": "normal", "trend_strength": 0}
        
        # Trend regime
        sma_20 = np.mean(close[-20:])
        sma_50 = np.mean(close[-50:])
        trend = 1 if sma_20 > sma_50 else -1
        
        # Volatility regime
        recent_vol = np.std(np.diff(np.log(close[-20:] + 1e-10)))
        long_vol = np.std(np.diff(np.log(close[-50:] + 1e-10)))
        vol_regime = "high" if recent_vol > 1.5 * long_vol else "normal"
        
        return {
            "regime_trend": int(trend),
            "regime_volatility": vol_regime,
            "trend_strength": float(abs(sma_20 - sma_50) / sma_50) if sma_50 > 0 else 0
        }
    
    @staticmethod
    def _percentile(series: np.ndarray, value: float) -> float:
        """Calculate percentile of value in series"""
        series = series[~np.isnan(series)]
        if len(series) == 0:
            return 0.5
        return float(np.sum(series <= value) / len(series))
