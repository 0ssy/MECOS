class TradingConfig:
    # Dynamic agent weight adjustment
    USE_DYNAMIC_WEIGHTS = True   # Adjust agent weights based on rolling PnL
    # --- Regime Detection ---
    REGIME_LOOKBACK = 50
    VOLATILITY_THRESHOLD = 2.0
    TREND_THRESHOLD = 0.02

    # --- Meta-Orchestrator ---
    # Minimum calibrated confidence to act on a signal.
    # 0.30 = allow valid sideways-regime signals to pass.
    MIN_CONFIDENCE = 0.30

    # Minimum directional edge from QuantSignalFusion to execute a trade.
    # Edge = (buy_score - sell_score) / total_score. Must exceed costs.
    MIN_EDGE = 0.15

    # Agent weights in MetaOrchestrator ensemble
    # RL is reduced because Q-table is untrained at startup
    # Sentiment is reduced because it uses price-action proxy, not real data
    SIGNAL_WEIGHTS = {
        "trend":                   1.30,  # Strong directional signals
        "mean_reversion":          1.10,  # Good for ranging regimes
        "volatility":              1.00,
        "options_pricing":         0.85,
        "order_flow":              1.15,  # Microstructure is valuable
        "liquidity_hunter":        1.00,
        "statistical_arbitrage":   0.90,
        "sentiment":               0.60,  # Price-action proxy only — reduced
        "reinforcement_learning":  0.50,  # Untrained Q-table — reduced until warmed up
        "market_making":           0.90,
    }

    # --- Risk Engine ---
    MAX_DRAWDOWN        = 0.08   # Kill switch at 8% drawdown (tighter than 10%)
    MAX_LEVERAGE        = 1.5    # No more than 1.5x — paper mode, be conservative
    MAX_POSITION_SIZE   = 0.15   # Max 15% of portfolio per position
    MAX_TOTAL_EXPOSURE  = 3.0
    MAX_CRYPTO_EXPOSURE = 0.20   # Crypto max 20% of portfolio
    MAX_DAILY_LOSS      = 0.02   # 2% daily loss limit (tighter)
    MAX_OPEN_TRADES     = 6      # Max 6 concurrent positions

    # --- Execution Cost Model ---
    # Assumed round-trip slippage in basis points (1 bps = 0.01%)
    # SPY/QQQ: ~1-2 bps, small caps: ~5-10 bps, crypto: ~10-20 bps
    SLIPPAGE_BPS = {
        "index":          2,   # SPY, QQQ, IWM, DIA
        "technology":     3,
        "semiconductors": 4,
        "small_cap":      8,
        "crypto":        15,
        "forex":          2,
        "equity":         5,   # default for unmapped equities
        "unknown":        5,
    }
    DEFAULT_SLIPPAGE_BPS = 5

    # --- Options Pricing ---
    RISK_FREE_RATE = 0.05

    FOREX_SYMBOLS = ['EURUSD', 'GBPUSD', 'USDJPY']
    MAX_SECTOR_EXPOSURE = 0.40  # Max 40% in any one sector

