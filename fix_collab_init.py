"""
fix_collab_init.py
Run from MECOS root: python fix_collab_init.py
"""
from pathlib import Path

p = Path("trading/trading_agent.py")
src = p.read_text(encoding="utf-8")

# Move collab_engine init to after register_agent calls
# Find the collab_engine init block and remove it from its current location
old_early = (
    "        # Unified collaborative engine — replaces MetaOrchestrator + ConsensusEngine chain\n"
    "        from trading.collaborative_decision_engine import CollaborativeDecisionEngine\n"
    "        self.collab_engine = CollaborativeDecisionEngine(\n"
    "            agents=self.meta_orchestrator.agents,\n"
    "            personas={name: self.consensus_engine._persona_analysis\n"
    "                      for name in self.consensus_engine.personas},\n"
    "        )"
)

# Remove it from its current (early) location
assert old_early in src, "Early collab_engine block not found"
src = src.replace(old_early, "        # collab_engine initialized after agent registration below")

# Find the last register_agent call and insert collab_engine init after it
# The last register_agent line registers "market_making"
last_register_marker = (
    "        self.meta_orchestrator.register_agent(\"market_making\", self.market_making_agent)"
)

new_after_register = (
    "        self.meta_orchestrator.register_agent(\"market_making\", self.market_making_agent)\n"
    "        # Unified collaborative engine — initialized after all agents are registered\n"
    "        from trading.collaborative_decision_engine import CollaborativeDecisionEngine\n"
    "        self.collab_engine = CollaborativeDecisionEngine(\n"
    "            agents=self.meta_orchestrator.agents,\n"
    "            personas={name: self.consensus_engine._persona_analysis\n"
    "                      for name in self.consensus_engine.personas},\n"
    "        )"
)

count = src.count(last_register_marker)
if count == 0:
    print("NOT FOUND: last register_agent line — checking what's there:")
    for line in src.splitlines():
        if "register_agent" in line:
            print(" ", repr(line))
elif count > 1:
    print(f"AMBIGUOUS ({count}x) — not patching")
else:
    src = src.replace(last_register_marker, new_after_register)
    p.write_text(src, encoding="utf-8")
    print("OK — collab_engine now initialized after all agents registered")

print("Done.")
