"""
Advanced Feature Engineering for Quantitative Trading
Computes institutional-grade market features for all downstream agents.

Features computed:
  - Volatility:     realized vol, ATR, volatility clustering, percentile
  - Momentum:       ROC-5/20, acceleration
  - Oscillators:    RSI-14, MACD (12/26/9), Bollinger Bands (20/2σ)
  - Trend:          SIGNED trend strength, SMA-20/50, price vs SMAs
  - Liquidity:      volume ratio, spread pressure, liquidity score
  - Entropy:        Shannon entropy, information ratio
  - Correlation:    autocorr, mean reversion, z-score
  - Regime:         trend direction, volatility regime
  - Microstructure: order flow imbalance, volume imbalance, pressure

Key fix over previous version:
  - RSI-14 is now actually computed (was missing entirely before — every
    agent was receiving the hardcoded default of 50.0)
  - MACD histogram gives signed momentum — negative = bearish → SELL signal
  - trend_strength is now SIGNED (was abs() before, hiding direction)
  - _empty_features() provides safe neutral defaults when data is thin
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any
from loguru import logger


class FeatureEngine:
    """Computes all technical and statistical features for the trading pipeline."""

    def __init__(self, memory):
        self.memory = memory
        logger.info("Feature Engine initialized")

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    async def compute_features(self, data: List[Dict]) -> Dict[str, Any]:
        """Compute comprehensive feature set from a list of OHLCV bar dicts."""
        if not data or len(data) < 2:
            return self._empty_features()

        df = pd.DataFrame(data)

        if "close" not in df.columns:
            logger.warning("Feature engine received data without 'close' column")
            return self._empty_features()

        # Fill missing OHLCV columns with close as fallback
        for col in ("open", "high", "low", "volume"):
            if col not in df.columns:
                df[col] = df["close"]

        df = df.ffill().bfill()

        features: Dict[str, Any] = {}
        features.update(self._compute_volatility_features(df))
        features.update(self._compute_momentum_features(df))
        features.update(self._compute_oscillator_features(df))
        features.update(self._compute_trend_features(df))
        features.update(self._compute_liquidity_features(df))
        features.update(self._compute_entropy_features(df))
        features.update(self._compute_correlation_features(df))
        features.update(self._compute_regime_features(df))
        features.update(self._compute_microstructure_features(df))

        return features

    # ------------------------------------------------------------------ #
    #  Volatility                                                          #
    # ------------------------------------------------------------------ #

    def _compute_volatility_features(self, df: pd.DataFrame) -> Dict:
        close = df["close"].values
        high  = df["high"].values
        low   = df["low"].values

        returns = np.diff(np.log(np.maximum(close, 1e-10)))

        realized_vol = float(np.std(returns[-20:]) * np.sqrt(252)) \
            if len(returns) >= 20 else 0.0

        if len(close) > 1:
            hl  = high[1:] - low[1:]
            hpc = np.abs(high[1:] - close[:-1])
            lpc = np.abs(low[1:]  - close[:-1])
            tr  = np.maximum(hl, np.maximum(hpc, lpc))
            atr = float(np.mean(tr[-14:])) if len(tr) >= 14 else 0.0
        else:
            atr = 0.0

        vol_series = pd.Series(returns).rolling(5).std().dropna().values
        if len(vol_series) > 5:
            vc = float(np.corrcoef(vol_series[:-1], vol_series[1:])[0, 1])
            vol_clustering = 0.0 if np.isnan(vc) else vc
        else:
            vol_clustering = 0.0

        return {
            "realized_volatility":   realized_vol,
            "atr":                   atr,
            "volatility_clustering": vol_clustering,
            "volatility_percentile": self._percentile(vol_series, realized_vol),
        }

    # ------------------------------------------------------------------ #
    #  Momentum                                                            #
    # ------------------------------------------------------------------ #

    def _compute_momentum_features(self, df: pd.DataFrame) -> Dict:
        close = df["close"].values

        roc_5  = float(close[-1] / close[-5]  - 1) if len(close) >= 5  else 0.0
        roc_20 = float(close[-1] / close[-20] - 1) if len(close) >= 20 else 0.0

        mom_5  = float(close[-1] - close[-5])  if len(close) >= 5  else 0.0
        mom_10 = float(close[-1] - close[-10]) if len(close) >= 10 else 0.0
        accel  = float(mom_5 - (mom_10 - mom_5)) if len(close) >= 10 else 0.0

        return {
            "roc_5":                 roc_5,
            "roc_20":                roc_20,
            "momentum_acceleration": accel,
        }

    # ------------------------------------------------------------------ #
    #  Oscillators — RSI, MACD, Bollinger Bands                           #
    # ------------------------------------------------------------------ #

    def _compute_oscillator_features(self, df: pd.DataFrame) -> Dict:
        close = df["close"].values

        rsi_14 = self._rsi(close, 14)
        macd_line, macd_sig, macd_hist = self._macd(close, 12, 26, 9)
        bb_upper, bb_mid, bb_lower, bb_pct_b, bb_width = self._bollinger(close, 20, 2.0)

        return {
            # RSI — agents can now check < 30 (oversold/BUY) or > 70 (overbought/SELL)
            "rsi_14":         rsi_14,
            "rsi":            rsi_14,          # alias for legacy code reading 'rsi'
            "rsi_overbought": 1.0 if rsi_14 > 70 else 0.0,
            "rsi_oversold":   1.0 if rsi_14 < 30 else 0.0,
            # MACD — negative histogram = bearish momentum = SELL signal
            "macd":           macd_line,
            "macd_signal":    macd_sig,
            "macd_hist":      macd_hist,
            # Bollinger Bands — pct_b > 1 = extended above upper band (potential SELL)
            "bb_upper":       bb_upper,
            "bb_mid":         bb_mid,
            "bb_lower":       bb_lower,
            "bb_pct_b":       bb_pct_b,
            "bb_width":       bb_width,
        }

    # ------------------------------------------------------------------ #
    #  Trend — directional and SIGNED                                      #
    # ------------------------------------------------------------------ #

    def _compute_trend_features(self, df: pd.DataFrame) -> Dict:
        close = df["close"].values

        if len(close) < 20:
            price = float(close[-1]) if len(close) else 0.0
            return {
                "trend_strength":  0.0,
                "trend_direction": 0,
                "sma_20":          price,
                "sma_50":          price,
                "price_vs_sma20":  0.0,
                "price_vs_sma50":  0.0,
            }

        sma_20 = float(np.mean(close[-20:]))
        sma_50 = float(np.mean(close[-50:])) if len(close) >= 50 else sma_20

        # +1 = bullish (SMA20 above SMA50), -1 = bearish
        direction = 1 if sma_20 >= sma_50 else -1

        # SIGNED trend strength — critical for SELL signal generation
        # Positive = bullish, Negative = bearish
        trend_strength = direction * float(abs(sma_20 - sma_50) / max(sma_50, 1e-9))

        price_vs_sma20 = float((close[-1] - sma_20) / max(sma_20, 1e-9))
        price_vs_sma50 = float((close[-1] - sma_50) / max(sma_50, 1e-9))

        return {
            "trend_strength":  trend_strength,   # SIGNED — negative means bearish
            "trend_direction": direction,
            "sma_20":          sma_20,
            "sma_50":          sma_50,
            "price_vs_sma20":  price_vs_sma20,
            "price_vs_sma50":  price_vs_sma50,
        }

    # ------------------------------------------------------------------ #
    #  Liquidity                                                           #
    # ------------------------------------------------------------------ #

    def _compute_liquidity_features(self, df: pd.DataFrame) -> Dict:
        close  = df["close"].values
        high   = df["high"].values
        low    = df["low"].values
        volume = df["volume"].values

        avg_vol      = float(np.mean(volume[-20:])) if len(volume) >= 20 else float(np.mean(volume) + 1e-9)
        volume_ratio = float(volume[-1] / max(avg_vol, 1e-9))
        spread       = float((high[-1] - low[-1]) / max(close[-1], 1e-9))

        return {
            "volume_ratio":    volume_ratio,
            "spread_pressure": spread,
            "liquidity_score": float(volume_ratio * (1.0 - spread)),
        }

    # ------------------------------------------------------------------ #
    #  Entropy                                                             #
    # ------------------------------------------------------------------ #

    def _compute_entropy_features(self, df: pd.DataFrame) -> Dict:
        close = df["close"].values

        if len(close) < 20:
            return {"entropy": 0.0, "information_ratio": 0.0}

        returns = np.diff(np.log(np.maximum(close[-20:], 1e-10)))
        hist, _ = np.histogram(returns, bins=10, density=True)
        hist    = hist[hist > 0]
        entropy = float(-np.sum(hist * np.log(hist + 1e-10)))

        noise      = float(np.std(returns))
        signal_mag = float(abs(np.mean(returns)))
        info_ratio = signal_mag / noise if noise > 0 else 0.0

        return {
            "entropy":           entropy,
            "information_ratio": info_ratio,
        }

    # ------------------------------------------------------------------ #
    #  Correlation & mean reversion                                        #
    # ------------------------------------------------------------------ #

    def _compute_correlation_features(self, df: pd.DataFrame) -> Dict:
        close = df["close"].values

        if len(close) < 20:
            return {"autocorr_1": 0.0, "mean_reversion_score": 0.0, "z_score": 0.0}

        returns = np.diff(np.log(np.maximum(close, 1e-10)))

        if len(returns) > 1:
            ac = float(np.corrcoef(returns[:-1], returns[1:])[0, 1])
            autocorr = 0.0 if np.isnan(ac) else ac
        else:
            autocorr = 0.0

        mean_c = float(np.mean(close[-20:]))
        std_c  = float(np.std(close[-20:]))
        z_score        = float((close[-1] - mean_c) / std_c) if std_c > 0 else 0.0
        mean_reversion = float(-autocorr * abs(z_score))

        return {
            "autocorr_1":           autocorr,
            "mean_reversion_score": mean_reversion,
            "z_score":              z_score,
        }

    # ------------------------------------------------------------------ #
    #  Regime                                                              #
    # ------------------------------------------------------------------ #

    def _compute_regime_features(self, df: pd.DataFrame) -> Dict:
        close = df["close"].values

        if len(close) < 50:
            return {"regime_trend": 0, "regime_volatility": "normal"}

        sma_20 = float(np.mean(close[-20:]))
        sma_50 = float(np.mean(close[-50:]))
        trend  = 1 if sma_20 > sma_50 else -1

        rv_20 = float(np.std(np.diff(np.log(np.maximum(close[-20:], 1e-10)))))
        rv_50 = float(np.std(np.diff(np.log(np.maximum(close[-50:], 1e-10)))))
        vol_regime = "high" if rv_20 > 1.5 * rv_50 else "normal"

        return {
            "regime_trend":      trend,
            "regime_volatility": vol_regime,
        }

    # ------------------------------------------------------------------ #
    #  Microstructure                                                      #
    # ------------------------------------------------------------------ #

    def _compute_microstructure_features(self, df: pd.DataFrame) -> Dict:
        close  = df["close"].values
        open_  = df["open"].values
        high   = df["high"].values
        low    = df["low"].values
        volume = df["volume"].values

        if len(close) < 5:
            return {
                "order_flow_imbalance":    0.0,
                "volume_imbalance":        0.0,
                "microstructure_pressure": 0.0,
            }

        w           = min(20, len(close))
        price_delta = close[-w:] - open_[-w:]
        vol_slice   = volume[-w:]

        signed_vol           = np.sign(price_delta) * vol_slice
        total_vol            = float(np.sum(np.abs(vol_slice))) + 1e-9
        order_flow_imbalance = float(np.sum(signed_vol) / total_vol)

        up_vol   = float(np.sum(vol_slice[price_delta > 0])) if np.any(price_delta > 0) else 0.0
        down_vol = float(np.sum(vol_slice[price_delta < 0])) if np.any(price_delta < 0) else 0.0
        volume_imbalance = float((up_vol - down_vol) / (up_vol + down_vol + 1e-9))

        range_pct = (high[-w:] - low[-w:]) / np.maximum(close[-w:], 1e-9)
        avg_range = float(np.mean(range_pct))
        msp       = float(order_flow_imbalance * (1.0 + avg_range * 20.0))

        return {
            "order_flow_imbalance":    float(np.clip(order_flow_imbalance, -1.0, 1.0)),
            "volume_imbalance":        float(np.clip(volume_imbalance,     -1.0, 1.0)),
            "microstructure_pressure": float(np.clip(msp,                  -1.5, 1.5)),
        }

    # ------------------------------------------------------------------ #
    #  Technical indicator helpers                                         #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _rsi(close: np.ndarray, period: int = 14) -> float:
        """Wilder's RSI. Returns 50.0 if insufficient data."""
        if len(close) < period + 1:
            return 50.0
        deltas = np.diff(close)
        gains  = np.where(deltas > 0, deltas,  0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        avg_gain = float(np.mean(gains[:period]))
        avg_loss = float(np.mean(losses[:period]))

        for g, l in zip(gains[period:], losses[period:]):
            avg_gain = (avg_gain * (period - 1) + g) / period
            avg_loss = (avg_loss * (period - 1) + l) / period

        if avg_loss == 0.0:
            return 100.0
        rs = avg_gain / avg_loss
        return float(100.0 - 100.0 / (1.0 + rs))

    @staticmethod
    def _ema(values: np.ndarray, period: int) -> np.ndarray:
        """Exponential moving average."""
        if len(values) == 0:
            return np.array([])
        alpha  = 2.0 / (period + 1)
        result = np.empty(len(values))
        result[0] = values[0]
        for i in range(1, len(values)):
            result[i] = alpha * values[i] + (1.0 - alpha) * result[i - 1]
        return result

    def _macd(self, close: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9):
        """Returns (macd_line, signal_line, histogram) as floats. 0.0 if insufficient data."""
        if len(close) < slow + signal:
            return 0.0, 0.0, 0.0
        macd_line = self._ema(close, fast) - self._ema(close, slow)
        sig_line  = self._ema(macd_line, signal)
        histogram = macd_line - sig_line
        return float(macd_line[-1]), float(sig_line[-1]), float(histogram[-1])

    @staticmethod
    def _bollinger(close: np.ndarray, period: int = 20, num_std: float = 2.0):
        """Returns (upper, mid, lower, pct_b, width). Safe defaults if insufficient data."""
        if len(close) < period:
            price = float(close[-1]) if len(close) else 0.0
            return price, price, price, 0.5, 0.0
        window = close[-period:]
        mid    = float(np.mean(window))
        std    = float(np.std(window))
        upper  = mid + num_std * std
        lower  = mid - num_std * std
        width  = (upper - lower) / max(mid, 1e-9)
        denom  = upper - lower
        pct_b  = float((close[-1] - lower) / denom) if denom > 0 else 0.5
        return upper, mid, lower, float(np.clip(pct_b, 0.0, 1.0)), width

    # ------------------------------------------------------------------ #
    #  Utilities                                                           #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _percentile(series: np.ndarray, value: float) -> float:
        series = series[~np.isnan(series)]
        if len(series) == 0:
            return 0.5
        return float(np.sum(series <= value) / len(series))

    @staticmethod
    def _empty_features() -> Dict[str, Any]:
        """Safe neutral defaults when data is insufficient."""
        return {
            "realized_volatility":     0.0,
            "atr":                     0.0,
            "volatility_clustering":   0.0,
            "volatility_percentile":   0.5,
            "roc_5":                   0.0,
            "roc_20":                  0.0,
            "momentum_acceleration":   0.0,
            "rsi_14":                  50.0,
            "rsi":                     50.0,
            "rsi_overbought":          0.0,
            "rsi_oversold":            0.0,
            "macd":                    0.0,
            "macd_signal":             0.0,
            "macd_hist":               0.0,
            "bb_upper":                0.0,
            "bb_mid":                  0.0,
            "bb_lower":                0.0,
            "bb_pct_b":                0.5,
            "bb_width":                0.0,
            "trend_strength":          0.0,
            "trend_direction":         0,
            "sma_20":                  0.0,
            "sma_50":                  0.0,
            "price_vs_sma20":          0.0,
            "price_vs_sma50":          0.0,
            "volume_ratio":            1.0,
            "spread_pressure":         0.0,
            "liquidity_score":         1.0,
            "entropy":                 0.0,
            "information_ratio":       0.0,
            "autocorr_1":              0.0,
            "mean_reversion_score":    0.0,
            "z_score":                 0.0,
            "regime_trend":            0,
            "regime_volatility":       "normal",
            "order_flow_imbalance":    0.0,
            "volume_imbalance":        0.0,
            "microstructure_pressure": 0.0,
        }
