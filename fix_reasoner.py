import re

with open('reasoner.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add this helper function at the top of the file (after imports)
helper_function = '''
def clean_json_string(json_str: str) -> str:
    \"\"\"Remove comments and clean JSON string before parsing.\"\"\"
    # Remove // single-line comments
    json_str = re.sub(r'//.*?$', '', json_str, flags=re.MULTILINE)
    # Remove /* multi-line comments */
    json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
    # Remove trailing commas before } or ]
    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
    return json_str.strip()
'''

# Insert after imports (find "class Reasoner:")
if 'def clean_json_string' not in content:
    content = content.replace('class Reasoner:', helper_function + '\n\nclass Reasoner:')

# Now replace json.loads(clean_json) with json.loads(clean_json_string(clean_json))
content = content.replace(
    'plan_data = json.loads(clean_json)',
    'plan_data = json.loads(clean_json_string(clean_json))'
)

with open('reasoner.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('✅ Robust JSON cleaner added to reasoner.py')
