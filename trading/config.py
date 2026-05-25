class TradingConfig:
    # --- Regime Detection ---
    REGIME_LOOKBACK = 50       # Number of candles to analyze for regime
    VOLATILITY_THRESHOLD = 2.0  # Ratio above which market is "volatile"
    TREND_THRESHOLD = 0.02      # Percentage move to consider "trending"

    # --- Meta-Orchestrator ---
    MIN_CONFIDENCE = 0.25       # Burn-in consensus threshold (lower to allow signal flow)
    SIGNAL_WEIGHTS = {
        "trend": 1.2,           # Give trend signals more weight
        "mean_reversion": 1.0,
        "volatility": 0.9,
        "options_pricing": 0.8,
        "order_flow": 1.1,
        "liquidity_hunter": 1.0,
        "statistical_arbitrage": 0.9,
        "sentiment": 1.0,
        "reinforcement_learning": 0.8,
        "market_making": 1.0,
    }

    # --- Risk Engine ---
    MAX_DRAWDOWN = 0.10         # Stop trading if 10% loss
    MAX_LEVERAGE = 3.0          # Max 3x leverage
    MAX_POSITION_SIZE = 0.10    # No single asset > 10% of portfolio
    MAX_TOTAL_EXPOSURE = 0.80   # Gross exposure cap
    MAX_CRYPTO_EXPOSURE = 0.25  # Crypto concentration cap
    MAX_DAILY_LOSS = 0.03       # Daily loss kill switch
    MAX_OPEN_TRADES = 10        # Concurrent positions cap
    # --- Options Pricing ---
    RISK_FREE_RATE = 0.05       # 5% annual interest rate for Black-Scholes
