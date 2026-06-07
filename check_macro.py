import inspect
from trading.macro_data import MacroDataProvider
print(inspect.getsource(MacroDataProvider.get_macro_snapshot))
