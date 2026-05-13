import re

with open('mecos_llm.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the system prompt and add tool usage examples
tool_examples = '''

TOOL USAGE RULES:
1. execute_python: Provide ACTUAL Python code, not filenames
   ✅ CORRECT: {"code": "import yfinance\\ndata = yf.download('BTC-USD')\\nprint(data)"}
   ❌ WRONG: {"code": "volatility_calculator.py"}  # This is a filename, not code!

2. file_write: Create the file FIRST, then execute_bash to run it
   Step 1: {"tool": "file_write", "args": {"path": "/data/script.py", "content": "print('hello')"}}
   Step 2: {"tool": "execute_bash", "args": {"command": "python /data/script.py"}}

3. execute_bash: Provide shell commands
   ✅ CORRECT: {"command": "python my_script.py"}
   ❌ WRONG: {"command": "my_script.py"}  # Missing python interpreter!
'''

# Insert after the main system prompt
old_prompt = 'You are MECOS, a Meta-Evolving Cognitive Operating System.'
if tool_examples not in content:
    content = content.replace(old_prompt, old_prompt + tool_examples)
    
    with open('mecos_llm.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print('✅ Tool usage examples added to system prompt')
else:
    print('✅ Already patched')
