import json
from urllib.parse import urlparse

data = json.load(open('data/outreach/leads.json'))
cleaned = []
for l in data:
    url = l.get('url', '')
    if url == 'https://test.com':
        continue
    cleaned.append(l)

with open('data/outreach/leads.json', 'w') as f:
    json.dump(cleaned, f, indent=2, default=str)

print(f"Removed test lead, kept {len(cleaned)} leads")
