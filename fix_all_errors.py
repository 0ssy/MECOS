import re

print('🔧 Fixing all MECOS errors...\n')

# ============================================
# Fix 1: Memory Consolidation API
# ============================================
print('1. Fixing memory consolidation API...')
with open('memory_consolidation.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove n_results parameter
content = re.sub(
    r'n_results=n_memories',
    '',
    content
)

# Clean up trailing commas
content = re.sub(
    r',\s*\)',
    ')',
    content
)

with open('memory_consolidation.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('   ✅ Memory consolidation fixed')

# ============================================
# Fix 2: Path Normalization (file_operations)
# ============================================
print('2. Adding path normalization...')
with open('file_operations.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add path normalization helper
if '_normalize_path' not in content:
    helper = '''
    def _normalize_path(self, path: str) -> Path:
        \"\"\"Normalize path - strip /data/ prefix that LLM often adds.\"\"\"
        # Strip leading /data/ or data/
        if path.startswith('/data/'):
            path = path[6:]
        elif path.startswith('data/'):
            path = path[5:]
        
        # Remove leading slashes
        path = path.lstrip('/\\\\')
        
        return self.base_dir / path
'''
    
    # Insert before class
    content = content.replace(
        'class FileOperations:',
        helper + '\n\nclass FileOperations:'
    )
    
    # Update write method
    old_resolve = 'resolved = (self.base_dir / path).resolve()'
    new_resolve = 'resolved = self._normalize_path(path).resolve()'
    content = content.replace(old_resolve, new_resolve)
    
    with open('file_operations.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('   ✅ Path normalization added')
else:
    print('   ✅ Already patched')

# ============================================
# Fix 3: Add LLM Timeout (prevent hanging)
# ============================================
print('3. Checking LLM timeout...')
with open('mecos_llm.py', 'r', encoding='utf-8') as f:
    content = f.read()

if 'timeout=' not in content:
    # Add timeout to OpenAI client
    content = content.replace(
        'self.client = OpenAI(',
        'self.client = OpenAI(\n            timeout=300.0,'
    )
    
    with open('mecos_llm.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('   ✅ LLM timeout added (5 minutes)')
else:
    print('   ✅ Timeout already configured')

print('\n🎉 All fixes applied!')
print('\nNext steps:')
print('1. Run: python main.py')
print('2. Try goal: Create a file called success.txt with content \"MECOS works!\"')
print('3. Should complete successfully this time!')
