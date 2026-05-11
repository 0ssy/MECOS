import asyncio
import os
from main import MECOSEngine
from memory_system import MemorySystem
from config import settings
from loguru import logger

async def run_live_test():
    logger.info("Starting MECOS Live Test Run...")
    
    # 1. Initialize Engine
    engine = MECOSEngine()
    await engine.startup()
    
    # 2. Start the engine loop in the background
    engine_task = asyncio.create_task(engine.main_loop())
    
    try:
        # 3. Simulate "Environment Change" - Create a new knowledge file
        logger.info("Simulating environment change: Adding new knowledge file...")
        new_info_path = settings.DATA_DIR / "market_principles.txt"
        with open(new_info_path, "w") as f:
            f.write("MECOS Trading Principle #1: Always prioritize risk management over potential profit.")
        
        # 4. Wait for the engine to perform a collection cycle (loop sleep is 30s)
        logger.info("Waiting for engine to observe and ingest the new file (approx 35s)...")
        await asyncio.sleep(35)
        
        # 5. Verify the engine "learned" the new information
        logger.info("Verifying autonomous learning...")
        results = await engine.memory.retrieve_context("What is the first trading principle?")
        
        found = False
        for doc in results['documents'][0]:
            if "risk management" in doc.lower():
                found = True
                logger.success(f"Engine successfully learned: {doc[:60]}...")
                break
        
        if not found:
            logger.error("Engine failed to autonomously learn the new information.")
            
    finally:
        # 6. Stop the engine
        logger.info("Stopping engine...")
        await engine.shutdown()
        engine_task.cancel()
        try:
            await engine_task
        except asyncio.CancelledError:
            pass

if __name__ == "__main__":
    asyncio.run(run_live_test())
