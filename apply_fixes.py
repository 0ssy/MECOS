import os

# 1. Fix Trading Loop (Force-Trade Mode)
loop_path = "trading/autonomous_trading_loop.py"
if os.path.exists(loop_path):
    with open(loop_path, "r") as f:
        content = f.read()
    content = content.replace("self.trade_quality_spread_multiplier = 2.5", "self.trade_quality_spread_multiplier = 0.0")
    content = content.replace("self.min_acceptable_volatility = 0.003", "self.min_acceptable_volatility = 0.0")
    with open(loop_path, "w") as f:
        f.write(content)
    print("✅ Trading Loop patched for Force-Trade mode.")

# 2. Fix Research Topics
research_path = "continuous_loop.py"
if os.path.exists(research_path):
    new_topics = 'self.base_topics = ["machine intelligence", "autonomous runtime", "local sovereign ai", "quantitative finance", "market microstructure", "recursive engineering", "distributed systems", "agentic workflows", "quant trading reinforcement learning", "multi-agent system coordination", "zero-shot engineering agents", "automated strategy synthesis", "sovereign compute orchestration", "high-frequency data ingestion"]'
    with open(research_path, "r") as f:
        lines = f.readlines()
    with open(research_path, "w") as f:
        for line in lines:
            if "self.base_topics =" in line:
                f.write(f"        {new_topics}\n")
            else:
                f.write(line)
    print("✅ Research Loop patched with 14 advanced domains.")

# 3. Fix Risk Engine (Higher Limits)
risk_path = "trading/risk_engine.py"
if os.path.exists(risk_path):
    with open(risk_path, "r") as f:
        content = f.read()
    content = content.replace("self.max_position_size = 0.10", "self.max_position_size = 0.50")
    with open(risk_path, "w") as f:
        f.write(content)
    print("✅ Risk Engine patched for 50% max position size.")
