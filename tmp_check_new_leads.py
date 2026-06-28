import json

data = json.load(open('data/outreach/leads.json'))
for l in data[-25:]:
    domain = l.get('domain', '?')
    score = l.get('total_score', 0)
    terms = l.get('matched_terms', [])[:3]
    url = l.get('url', '?')
    print(f"{domain:30s} | score={score:2d} | terms={terms}")
    print(f"    {url}")
