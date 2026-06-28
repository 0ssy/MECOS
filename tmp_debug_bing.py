import requests

r = requests.get('http://localhost:8888/search', params={'q': 'automation', 'format': 'json', 'engines': 'bing'}, timeout=15)
data = r.json()
results = data.get('results', [])
print(f"Results: {len(results)}")
for x in results[:10]:
    print(f"  {x.get('url','?')}")
    print(f"    {x.get('title','?')[:70]}")
    print(f"    {x.get('content','')[:100]}")
