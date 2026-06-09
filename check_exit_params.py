import inspect
from trading.paper_trading_executor import PaperTradingExecutor
src = inspect.getsource(PaperTradingExecutor.__init__)
for line in src.split('\n'):
    if any(x in line for x in ['stop_loss', 'take_profit', 'trailing', 'holding']):
        print(line)
