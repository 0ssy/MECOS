import os
import re

def patch(path, old, new):
    if not os.path.exists(path): return False
    with open(path, 'r', encoding='utf-8') as f:
        c = f.read()
    if old in c:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(c.replace(old, new))
        print(f"✅ Safe Alpha Tuned: {path}")
        return True
    return False

# 1. Tune: Volume-Validated Momentum (Adding the 'Fuel' Check)
agent_path = "trading/trading_agent.py"
if os.path.exists(agent_path):
    with open(agent_path, 'r', encoding='utf-8') as f:
        c = f.read()
    # Only boost if momentum is backed by Relative Volume > 1.2
    safe_momentum = '''        expected_move = float(max(abs(features.get("roc_5", 0.0)), abs(features.get("trend_strength", 0.0))))
        # Alpha v2.3: Confirmed Anticipation (Price + Volume)
        rel_vol = float(features.get("relative_volume", 1.0) or 1.0)
        if abs(float(features.get("roc_1", 0.0))) > 0.0001 and rel_vol > 1.2:
            expected_move *= 2.5 
'''
    c = re.sub(r'expected_move = float\(max\(abs\(features\.get\("roc_5", 0\.0"\)\), abs\(features\.get\("trend_strength", 0\.0"\)\)\)\)', safe_momentum, c)
    # Also update Synergy Bonus to be more strict
    synergy_logic = '''        confidence = float(fused.get("confidence", orchestrated.get("confidence", 0.0)))
        # Alpha v2.3: Triple-Lock Synergy (Trend + OrderFlow + MeanRev)
        sigs = orchestrated.get("agent_signals", {})
        if sigs.get("trend") == sigs.get("order_flow") == sigs.get("mean_reversion"):
            confidence += 0.20
'''
    c = re.sub(r'confidence = float\(fused\.get\("confidence", orchestrated\.get\("confidence", 0\.0"\)\)\)', synergy_logic, c)
    with open(agent_path, 'w', encoding='utf-8') as f:
        f.write(c)
    print("✅ Safe Alpha Tuned: trading/trading_agent.py")

# 2. Tune: Restore Spread Safety Buffer
patch("trading/autonomous_trading_loop.py", "self.trade_quality_spread_multiplier = 0.8", "self.trade_quality_spread_multiplier = 1.1")

# 3. Tune: Professional Confidence Floor
patch("trading/config.py", "MIN_CONFIDENCE = 0.50", "MIN_CONFIDENCE = 0.58")
