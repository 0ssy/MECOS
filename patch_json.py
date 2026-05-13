import re

# Read reasoner.py
with open('reasoner.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the JSON parsing section
# Add a cleaning step before json.loads()

# Look for the pattern where it tries to parse JSON
old_pattern = r'plan_data = json\.loads\(clean_json\)'

new_code = '''# Clean JSON (remove // comments)
        clean_json = re.sub(r'//.*', '', clean_json)  # Remove // comments
        clean_json = re.sub(r'/\*.*?\*/', '', clean_json, flags=re.DOTALL)  # Remove /* */ comments
        plan_data = json.loads(clean_json)'''

if old_pattern in content:
    content = re.sub(old_pattern, new_code, content)
    
    with open('reasoner.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('✅ JSON parser patched!')
else:
    print('⚠️ Pattern not found - manual fix needed')
