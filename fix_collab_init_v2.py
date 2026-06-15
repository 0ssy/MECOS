"""
fix_collab_init_v2.py
Run from MECOS root: python fix_collab_init_v2.py
"""
from pathlib import Path

p = Path("trading/trading_agent.py")
src = p.read_text(encoding="utf-8")

# Find the last register_agent call
lines = src.splitlines()
last_reg_idx = None
for i, line in enumerate(lines):
    if "self.meta_orchestrator.register_agent(" in line:
        last_reg_idx = i

if last_reg_idx is None:
    print("ERROR: No register_agent calls found")
    exit(1)

print(f"Last register_agent at line {last_reg_idx + 1}: {lines[last_reg_idx].strip()}")

# Find the collab_engine init block
collab_start = None
collab_end = None
for i, line in enumerate(lines):
    if "self.collab_engine = CollaborativeDecisionEngine(" in line:
        collab_start = i
    if collab_start and i > collab_start and line.strip() == ")":
        collab_end = i
        break

if collab_start is None:
    print("ERROR: collab_engine init not found")
    exit(1)

print(f"collab_engine init at lines {collab_start + 1}-{collab_end + 1}")
print(f"Is before last register_agent? {collab_start < last_reg_idx}")

if collab_start > last_reg_idx:
    print("collab_engine is already after register_agent calls — no fix needed")
    exit(0)

# Extract the collab block (including the import line above it if present)
import_line_idx = collab_start - 1
if "CollaborativeDecisionEngine" in lines[import_line_idx]:
    block_start = import_line_idx
    # Also check for comment line above import
    if collab_start >= 2 and "collab" in lines[import_line_idx - 1].lower():
        block_start = import_line_idx - 1
else:
    block_start = collab_start

collab_block = "\n".join(lines[block_start:collab_end + 1])
print(f"\nBlock to move (lines {block_start + 1}-{collab_end + 1}):")
print(collab_block)

# Remove the block from its current location
new_lines = lines[:block_start] + lines[collab_end + 1:]

# Find new position of last register_agent (after removal)
new_last_reg = None
for i, line in enumerate(new_lines):
    if "self.meta_orchestrator.register_agent(" in line:
        new_last_reg = i

# Insert after last register_agent
insert_after = new_last_reg
new_lines = (
    new_lines[:insert_after + 1]
    + ["        # Unified collaborative engine — initialized after all agents registered"]
    + collab_block.splitlines()
    + new_lines[insert_after + 1:]
)

result = "\n".join(new_lines)
p.write_text(result, encoding="utf-8")
print(f"\nOK — collab_engine moved to after line {insert_after + 1}")

# Verify
src2 = p.read_text(encoding="utf-8")
lines2 = src2.splitlines()
reg_positions = [i for i, l in enumerate(lines2) if "register_agent(" in l]
collab_positions = [i for i, l in enumerate(lines2) if "collab_engine = Collaborative" in l]
print(f"register_agent calls at lines: {[i+1 for i in reg_positions]}")
print(f"collab_engine init at line: {[i+1 for i in collab_positions]}")
print(f"Correct order: {max(reg_positions) < min(collab_positions)}")
