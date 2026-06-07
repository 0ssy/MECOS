import inspect
from trading.market_data_stream import MarketDataStream
print(inspect.getsource(MarketDataStream.get_historical_cache))
