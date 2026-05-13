import re

# Read the reasoner's system prompt
with open('reasoner.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the system prompt section (where it tells the LLM about tools)
# Add clearer tool usage examples

# Look for the planning instructions
if 'generate_plan' in content:
    # Add a helper function that validates the plan before returning
    validation_code = '''
def _validate_plan_step(step: dict) -> tuple[bool, str]:
    """Validate that a plan step has proper tool arguments."""
    tool = step.get('tool', '')
    args = step.get('args', {})
    
    # Validation rules
    if tool == 'execute_python':
        code = args.get('code', '')
        # Check if they put a filename instead of code
        if code.endswith('.py') and '\\n' not in code and 'import' not in code:
            return False, f"execute_python requires actual Python CODE, not a filename. Got: {code}"
    
    if tool == 'execute_bash':
        command = args.get('command', '')
        if not command:
            return False, "execute_bash requires a 'command' argument"
    
    if tool == 'file_write':
        path = args.get('path', '')
        content_arg = args.get('content', '')
        if not path or not content_arg:
            return False, "file_write requires both 'path' and 'content' arguments"
    
    return True, ""
'''
    
    # Insert validation function before the Reasoner class
    if '_validate_plan_step' not in content:
        content = content.replace('class Reasoner:', validation_code + '\\n\\nclass Reasoner:')
        
        # Now modify generate_plan to use validation
        # Find the section where it parses the plan
        old_pattern = r'for step in plan_data:'
        new_pattern = '''for step in plan_data:
            # Validate each step
            is_valid, error_msg = _validate_plan_step(step)
            if not is_valid:
                logger.warning(f"Invalid plan step detected: {error_msg}")
                # Skip invalid steps or fix them
                continue'''
        
        content = re.sub(old_pattern, new_pattern, content)
    
    with open('reasoner.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print('✅ Plan validation added to reasoner.py')
else:
    print('⚠️ Could not find generate_plan function')
