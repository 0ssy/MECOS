import os
import re

def patch_file(path, pattern, replacement):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    return False

# 1. Fix Indentation and Topics in continuous_loop.py
research_path = "continuous_loop.py"
topics_replacement = '''        self.base_topics = [
            "machine intelligence", "autonomous runtime", "local sovereign ai",
            "quantitative finance", "market microstructure", "recursive engineering",
            "distributed systems", "agentic workflows", "quant trading reinforcement learning",
            "multi-agent system coordination", "zero-shot engineering agents",
            "automated strategy synthesis", "sovereign compute orchestration",
            "high-frequency data ingestion"
        ]'''
if patch_file(research_path, r'self\.base_topics = \[.*?\]', topics_replacement):
    print("✅ Fixed Indentation & Expanded Research Topics.")

# 2. Smart-Active Tuning in autonomous_trading_loop.py (Dealing with the Cons)
loop_path = "trading/autonomous_trading_loop.py"
# We use 0.2 instead of 0.0 to ensure the trade has SOME edge, and 0.0001 for vol.
tuning_replacements = [
    (r'self\.trade_quality_spread_multiplier = \d+\.\d+', 'self.trade_quality_spread_multiplier = 0.2'),
    (r'self\.min_acceptable_volatility = \d+\.\d+', 'self.min_acceptable_volatility = 0.0001')
]
success = False
for pat, rep in tuning_replacements:
    if patch_file(loop_path, pat, rep):
        success = True
if success:
    print("✅ Applied Smart-Active Filter (Mitigating Spread & Volatility Cons).")

# 3. Increase Risk Limits in risk_engine.py
risk_path = "trading/risk_engine.py"
if patch_file(risk_path, r'self\.max_position_size = \d+\.\d+', 'self.max_position_size = 0.40'):
    print("✅ Risk Engine updated to 40% Max Position.")

