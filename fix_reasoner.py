import re

with open('reasoner.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove the broken validation function
# Look for the literal \n\n that broke it
content = content.replace('\\n\\nclass Reasoner:', '\n\nclass Reasoner:')
content = content.replace('\\n', '\n')  # Fix any other escaped newlines

# Remove the entire broken validation block if it exists
if '_validate_plan_step' in content:
    # Find and remove the validation function
    import re
    # Remove from the function definition to where Reasoner class starts
    pattern = r'def _validate_plan_step.*?(?=class Reasoner:)'
    content = re.sub(pattern, '', content, flags=re.DOTALL)

# Also remove any broken validation calls in the loop
if 'is_valid, error_msg = _validate_plan_step' in content:
    # Restore the original loop
    content = re.sub(
        r'for step in plan_data:.*?continue',
        'for step in plan_data:',
        content,
        flags=re.DOTALL
    )

with open('reasoner.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('✅ reasoner.py syntax errors fixed')
