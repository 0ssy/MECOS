import os
import re

def patch(path, old, new):
    if not os.path.exists(path): return False
    with open(path, 'r', encoding='utf-8') as f:
        c = f.read()
    if old in c:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(c.replace(old, new))
        print(f"✅ Scalper Tuned: {path}")
        return True
    return False

# 1. Tune: Mean Reversion Sensitivity (Lowering the bar for reversals)
# We make the agent 30% more sensitive to overbought/oversold conditions.
patch("trading/mean_reversion_agent.py", "self.rsi_period = 14", "self.rsi_period = 9")
patch("trading/mean_reversion_agent.py", "self.overbought = 70", "self.overbought = 65")
patch("trading/mean_reversion_agent.py", "self.oversold = 30", "self.oversold = 35")

# 2. Tune: Regime-Aware Fusion (Prioritize Mean Reversion in low-vol)
# We inject logic to favor scalping when the market is quiet.
fusion_path = "trading/quant_signal_fusion.py"
if os.path.exists(fusion_path):
    with open(fusion_path, 'r', encoding='utf-8') as f:
        c = f.read()
    if "weights = self.REGIME_AGENT_WEIGHTS.get(regime" in c:
        new_logic = '''        weights = self.REGIME_AGENT_WEIGHTS.get(regime, self.REGIME_AGENT_WEIGHTS["ranging"]).copy()
        volatility = float(features.get("realized_volatility", 0.0) or 0.0)
        if volatility < 0.005: # Low volatility 'Scalp' mode
            weights["mean_reversion"] = weights.get("mean_reversion", 0.3) * 2.0
            weights["trend"] = weights.get("trend", 0.3) * 0.5
'''
        c = re.sub(r'weights = self\.REGIME_AGENT_WEIGHTS\.get\(regime.*?\)\.copy\(\)', new_logic, c, flags=re.DOTALL)
        with open(fusion_path, 'w', encoding='utf-8') as f:
            f.write(c)
        print("✅ Scalper Tuned: trading/quant_signal_fusion.py")

# 3. Tune: Dynamic Quality Gate (The 'Smart-Active' 1.1x Multiplier)
# We set it to 1.1x - Profit must be 10% more than the spread. 
patch("trading/autonomous_trading_loop.py", "self.trade_quality_spread_multiplier = 1.5", "self.trade_quality_spread_multiplier = 1.1")
patch("trading/autonomous_trading_loop.py", "self.min_acceptable_volatility = 0.0015", "self.min_acceptable_volatility = 0.0005")

# 4. Tune: Lower Confidence for Scalping
patch("trading/config.py", "MIN_CONFIDENCE = 0.62", "MIN_CONFIDENCE = 0.55")
