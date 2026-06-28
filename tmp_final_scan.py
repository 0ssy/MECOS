import asyncio
from memory_system import MemorySystem
from outreach.scanner import OutreachScanner

async def main():
    memory = MemorySystem()
    scanner = OutreachScanner(memory)
    
    print("Running scan...")
    leads = await scanner.scan_business_directories(limit=10)
    print(f"scan_business_directories: {len(leads)} leads")
    
    searxng_queries = [
        "looking for automation tools small business",
        "manual data entry help business",
        "workflow bottleneck process improvement",
        "automation needed for business",
    ]
    for q in searxng_queries:
        found = await scanner.search_leads(q, limit=5)
        print(f"search_leads '{q}': {len(found)} leads")
    
    new_leads = [l for l in scanner.leads if l.get('status') == 'new']
    print(f"\nTotal new leads: {len(new_leads)}")
    for l in new_leads[:10]:
        print(f"  {l.get('domain','?')} | score={l.get('total_score',0)} | terms={l.get('matched_terms',[])[:3]}")

asyncio.run(main())
