import os
import re

def patch(path, old, new):
    if not os.path.exists(path): return False
    with open(path, 'r', encoding='utf-8') as f:
        c = f.read()
    if old in c:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(c.replace(old, new))
        print(f"✅ Alpha Tuned: {path}")
        return True
    return False

# 1. Tune: Increase the 'Edge' requirement for better entries
# We set spread multiplier to 1.5 - This is the 'Sweet Spot' for profit vs frequency.
patch("trading/autonomous_trading_loop.py", "self.trade_quality_spread_multiplier = 1.1", "self.trade_quality_spread_multiplier = 1.5")
patch("trading/autonomous_trading_loop.py", "self.min_acceptable_volatility = 0.0001", "self.min_acceptable_volatility = 0.0015")

# 2. Tune: Confidence Calibration
# We set it to 0.62. This is high enough to filter noise but low enough to catch moves.
patch("trading/config.py", "MIN_CONFIDENCE = 0.50", "MIN_CONFIDENCE = 0.62")

# 3. Tune: Risk-Adjusted Sizing
# We cap at 15% to ensure the system can survive 6-7 consecutive losses (statistical norm).
patch("trading/risk_engine.py", "self.max_position_size = 0.25", "self.max_position_size = 0.15")
