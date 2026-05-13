# Read the file
with open('reasoner.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix line 91: context_str = "\n".join(docs[0]) if docs else ""
if len(lines) > 90:
    lines[90] = '            context_str = "\\n".join(docs[0]) if docs else ""\n'

# Fix line 204: logger.debug(f"RAW JSON:\n{json_str}")
if len(lines) > 203:
    lines[203] = '                logger.debug(f"RAW JSON:\\n{json_str}")\n'

# Fix line 333: f"REFLECTION LESSON:\n{lesson}",
if len(lines) > 332:
    lines[332] = '                    f"REFLECTION LESSON:\\n{lesson}",\n'

# Write it back
with open('reasoner.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('✅ Fixed all unterminated string literals')
