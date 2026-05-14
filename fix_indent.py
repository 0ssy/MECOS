# Fix the indentation in file_operations.py
with open('file_operations.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Remove the broken helper function
new_lines = []
skip_until_class = False

for line in lines:
    # Skip the broken _normalize_path function
    if 'def _normalize_path' in line:
        skip_until_class = True
        continue
    
    if skip_until_class:
        # Stop skipping when we hit the class definition
        if line.strip().startswith('class FileOperations'):
            skip_until_class = False
            new_lines.append(line)
        continue
    
    new_lines.append(line)

# Now find the __init__ method and add the helper INSIDE the class
final_lines = []
for i, line in enumerate(new_lines):
    final_lines.append(line)
    
    # Add the helper method right after the class definition
    if 'class FileOperations:' in line:
        # Add the helper method with proper indentation (4 spaces for class method)
        helper = '''    def _normalize_path(self, path: str):
        \"\"\"Normalize path - strip /data/ prefix that LLM often adds.\"\"\"
        from pathlib import Path
        # Strip leading /data/ or data/
        if path.startswith('/data/'):
            path = path[6:]
        elif path.startswith('data/'):
            path = path[5:]
        # Remove leading slashes
        path = path.lstrip('/\\\\')
        return self.base_dir / Path(path)

'''
        final_lines.append(helper)

# Write back
with open('file_operations.py', 'w', encoding='utf-8') as f:
    f.writelines(final_lines)

print('✅ Fixed indentation in file_operations.py')
