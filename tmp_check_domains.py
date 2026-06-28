import json
from urllib.parse import urlparse

data = json.load(open('data/outreach/leads.json'))
print(f"Total leads: {len(data)}")
domains = {}
for l in data:
    domain = urlparse(l.get('url', '')).netloc
    if domain.startswith('www.'):
        domain = domain[4:]
    domains[domain] = domains.get(domain, 0) + 1

for domain, count in sorted(domains.items(), key=lambda x: -x[1])[:20]:
    print(f"  {domain}: {count}")
