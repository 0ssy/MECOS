import os, asyncio, re
from sentence_transformers import SentenceTransformer
from chromadb.utils import embedding_functions

print('='*60)
print('🔧 MECOS Setup Script')
print('='*60)

print('\n📥 Step 1/3: Downloading embedding model...')
print('   (This may take 2-5 minutes depending on your connection)')
SentenceTransformer('all-MiniLM-L6-v2')
print('   ✅ Embedding model ready')

print('\n📥 Step 2/3: Downloading ChromaDB ONNX model...')
ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name='all-MiniLM-L6-v2')
ef(['test'])
print('   ✅ ChromaDB ONNX model ready')

print('\n🔧 Step 3/3: Patching timeout configuration...')
with open('memory_system.py', 'r', encoding='utf-8') as f:
    content = f.read()
    
if 'chroma_client_timeout' not in content:
    if 'from chromadb.config import Settings as ChromaSettings' not in content:
        content = content.replace('import chromadb', 'import chromadb\nfrom chromadb.config import Settings as ChromaSettings')
    
    content = content.replace(
        'self.client = chromadb.PersistentClient(\n            path=str(settings.VECTOR_DB_PATH)\n        )',
        '''self.client = chromadb.PersistentClient(
            path=str(settings.VECTOR_DB_PATH),
            settings=ChromaSettings(
                anonymized_telemetry=False,
                chroma_client_timeout=600
            )
        )'''
    )
    
    with open('memory_system.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('   ✅ Timeout configuration patched')
else:
    print('   ✅ Already patched (skipping)')

print('\n🧪 Testing MECOS components...')
from memory_system import MemorySystem

async def test():
    m = MemorySystem()
    print('   ✅ Memory system initialized')
    
    await m.add_experience('Test experience', 'setup_test')
    print('   ✅ Can add experiences')
    
    results = await m.retrieve_context('Test')
    num_items = len(results['ids'][0])
    print(f'   ✅ Can retrieve context ({num_items} items found)')

asyncio.run(test())

print('\n' + '='*60)
print('🎉 MECOS SETUP COMPLETE!')
print('='*60)
print('\nNext steps:')
print('  1. Run: python main.py')
print('  2. Check that Ollama is running at 192.168.1.88:11434')
print('  3. Enjoy your autonomous AI system!')
print('='*60)
