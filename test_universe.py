from trading.universe_manager import UniverseManager
from memory_system import MemorySystem

memory = MemorySystem()
universe = UniverseManager(memory)

print('Total Universe:', universe.get_total_universe_size())
print('')

print('STARTER UNIVERSE:')
starter = universe.load_starter_universe()
print(f'Assets: {len(starter)}')
print(starter)
print('')

print('SECTOR ALLOCATION:')
allocation = universe.get_sector_allocation()
for sector, count in allocation.items():
    if count > 0:
        print(f'{sector}: {count}')
