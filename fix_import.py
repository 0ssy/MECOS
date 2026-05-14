# Add missing import to main.py
with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Check if PerceptionLayer import is missing
if 'from perception import PerceptionLayer' not in content:
    # Find the import section (usually after the first few imports)
    # Add it after the memory_system import
    content = content.replace(
        'from memory_system import MemorySystem',
        'from memory_system import MemorySystem\nfrom perception import PerceptionLayer'
    )
    
    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print('✅ Added PerceptionLayer import')
else:
    print('✅ Import already exists')
