import inspect
from trading.live_signal_generator import LiveSignalGenerator
print(inspect.getsource(LiveSignalGenerator.on_market_data))
