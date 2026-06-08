import inspect
from trading.autonomous_trading_loop import AutonomousTradingLoop
src = inspect.getsource(AutonomousTradingLoop._on_market_tick)
# Just show the exit signal section
lines = src.split('\n')
for i, line in enumerate(lines):
    if 'exit' in line.lower():
        print(f"{i}: {line}")
