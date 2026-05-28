import os
import re

def patch(path, old, new):
    if not os.path.exists(path): return
    with open(path, 'r', encoding='utf-8') as f:
        c = f.read()
    if old in c:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(c.replace(old, new))
        print(f"✅ Balanced: {path}")

# 1. Set Spread Multiplier to 1.1 (Profit must be > Spread)
patch("trading/autonomous_trading_loop.py", "self.trade_quality_spread_multiplier = 2.5", "self.trade_quality_spread_multiplier = 1.1")
patch("trading/autonomous_trading_loop.py", "self.trade_quality_spread_multiplier = 0.0", "self.trade_quality_spread_multiplier = 1.1")

# 2. Set Confidence Floor to 0.50 (To match your 0.52 signals)
patch("trading/config.py", "MIN_CONFIDENCE = 0.70", "MIN_CONFIDENCE = 0.50")
patch("trading/config.py", "MIN_CONFIDENCE = 0.40", "MIN_CONFIDENCE = 0.50")

# 3. Increase Position Limit to 25% (To allow BTC trades)
patch("trading/risk_engine.py", "self.max_position_size = 0.10", "self.max_position_size = 0.25")
patch("trading/risk_engine.py", "self.max_position_size = 1.0", "self.max_position_size = 0.25")
