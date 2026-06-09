import inspect
from trading.trade_database import TradeDatabase
print(inspect.getsource(TradeDatabase.close_trade))
print('---')
print(inspect.getsource(TradeDatabase.open_trade))
