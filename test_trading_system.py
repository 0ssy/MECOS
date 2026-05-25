"""
Test script for unified TradingSystem integration.
"""
import asyncio
from memory_system import MemorySystem
from trading import TradingSystem

async def main():
    memory = MemorySystem()
    system = TradingSystem(memory_system=memory)
    print("TradingSystem components:")
    for k, v in system.get_components().items():
        print(f"  {k}: {type(v).__name__}")
    print("Starting trading system (validation mode)...")
    await system.start(use_starter_universe=True)

if __name__ == "__main__":
    asyncio.run(main())
