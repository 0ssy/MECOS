import asyncio
from unittest.mock import MagicMock
from trading.universe_scanner import UniverseScanner
from trading.market_data_stream import MarketDataStream

async def test():
    stream = MarketDataStream()
    memory = MagicMock()
    
    from trading.universe_manager import UniverseManager
    universe = UniverseManager(memory)
    scanner = UniverseScanner(universe, stream)
    
    results = await scanner.scan_universe(['AAPL', 'MSFT', 'BTC/USD', 'SPY'])
    for symbol, data in results.items():
        quality = data.get('data_quality', 'empty')
        price = data.get('price', 0)
        print(f'{symbol}: price={price:.2f} quality={quality}')

asyncio.run(test())
