import asyncio
from memory_system import MemorySystem
from outreach.outreach_agent import OutreachAgent

async def main():
    memory = MemorySystem()
    agent = OutreachAgent(memory)
    
    print("Running enrichment cycle...")
    enrich_result = await agent.run_cycle()
    print(f"Enrich result: {enrich_result}")
    
    print("\nRunning synthesis cycle...")
    synth_result = await agent.run_cycle()
    print(f"Synth result: {synth_result}")

asyncio.run(main())
