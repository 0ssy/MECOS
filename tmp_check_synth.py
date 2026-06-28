import json

data = json.load(open('data/outreach/synthesized_leads.json'))
print(f"Count: {len(data)}")
for d in data[-10:]:
    domain = d.get('domain', '?')
    pkg = d.get('recommended_package', {}).get('name', '?')
    status = d.get('status', '?')
    print(f"  {domain} | {pkg} | status={status}")
