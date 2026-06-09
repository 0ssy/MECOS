import inspect
from trading.trade_database import TradeDatabase
print(inspect.getsource(TradeDatabase.insert_order))
