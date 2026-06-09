import inspect
from trading.paper_trading_executor import PaperTradingExecutor
src = inspect.getsource(PaperTradingExecutor.execute_signal)
for i, line in enumerate(src.split('\n')):
    if any(x in line.lower() for x in ['price', 'database', 'save', 'order', 'fill']):
        print(f"{i}: {line}")
