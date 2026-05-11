import asyncio
from memory_system import MemorySystem
from perception import PerceptionLayer
from config import settings
from loguru import logger

async def verify():
    logger.info("Verifying MECOS Foundation...")
    
    # 1. Test Memory System
    memory = MemorySystem()
    test_content = "The core objective of MECOS is autonomous evolution."
    await memory.add_experience(test_content, source="verification_test")
    
    results = await memory.retrieve_context("What is the objective of MECOS?")
    if test_content in results['documents'][0]:
        logger.success("Memory System Verification: PASSED")
    else:
        logger.error("Memory System Verification: FAILED")

    # 2. Test Perception Layer (File Ingestion)
    test_file = settings.DATA_DIR / "test_knowledge.txt"
    with open(test_file, "w") as f:
        f.write("MECOS uses ChromaDB for vector storage.")
    
    perception = PerceptionLayer(memory)
    await perception.collect(str(settings.DATA_DIR))
    
    results = await memory.retrieve_context("database")
    if any("ChromaDB" in doc for doc in results['documents'][0]):
        logger.success("Perception Layer Verification: PASSED")
    else:
        logger.error("Perception Layer Verification: FAILED")

if __name__ == "__main__":
    asyncio.run(verify())
