import requests

r = requests.get('http://localhost:8888/search', params={'q': 'automation', 'format': 'json'}, timeout=15)
data = r.json()
results = data.get('results', [])
print(f"Results: {len(results)}")
for r in results[:10]:
    url = r.get('url', '?')
    title = r.get('title', '?')[:60]
    print(f"  {url}")
    print(f"    {title}")
