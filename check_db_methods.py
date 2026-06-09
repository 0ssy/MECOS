import inspect
from trading.trade_database import TradeDatabase
import inspect
methods = ['insert_fill', 'insert_trade', 'save_portfolio_snapshot', 'get_open_trade_for_symbol']
for m in methods:
    if hasattr(TradeDatabase, m):
        print(f'\n=== {m} ===')
        print(inspect.getsource(getattr(TradeDatabase, m)))
    else:
        print(f'\n=== {m} === NOT FOUND')
