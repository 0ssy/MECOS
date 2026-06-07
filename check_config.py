import inspect
from trading.config import TradingConfig
import trading.config as c
src = inspect.getsource(c)
print(src)
