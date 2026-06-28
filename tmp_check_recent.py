import json

data = json.load(open('data/outreach/leads.json'))
for l in data[-10:]:
    print(f"{l.get('domain','?')} | score={l.get('total_score',0)} | discovered={l.get('discovered_at','?')[:19]}")
