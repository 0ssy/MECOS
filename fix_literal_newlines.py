# Read the file
with open('reasoner.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the literal \n\n on line 52
content = content.replace('    return True, ""\n\\n\\nclass Reasoner:', '    return True, ""\n\n\nclass Reasoner:')

# Also fix any other escaped newlines that shouldn't be escaped
content = content.replace('\\n', '\n')

# Write it back
with open('reasoner.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('✅ Fixed literal backslash-n characters')
