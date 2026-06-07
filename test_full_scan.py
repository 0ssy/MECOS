import asyncio
from unittest.mock import MagicMock
from trading.universe_scanner import UniverseScanner
from trading.universe_manager import UniverseManager
from trading.market_data_stream import MarketDataStream

async def test():
    stream = MarketDataStream()
    universe = UniverseManager(MagicMock())
    scanner = UniverseScanner(universe, stream)
    
    all_symbols = universe.get_all_symbols() if hasattr(universe, 'get_all_symbols') else []
    if not all_symbols:
        all_symbols = []
        for category in universe.universe.values():
            if isinstance(category, dict):
                for symbols in category.values():
                    all_symbols.extend(symbols)
            elif isinstance(category, list):
                all_symbols.extend(category)

    print(f'Total symbols to scan: {len(all_symbols)}')
    results = await scanner.scan_universe(all_symbols)
    
    success = sum(1 for d in results.values() if d.get('price', 0) > 0)
    empty   = sum(1 for d in results.values() if d.get('price', 0) == 0)
    print(f'Success: {success}/{len(results)} | Empty: {empty}')
    
    for symbol, data in list(results.items())[:10]:
        print(f'  {symbol}: price={data.get("price",0):.2f}')

asyncio.run(test())
