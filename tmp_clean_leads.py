import json
from urllib.parse import urlparse

data = json.load(open('data/outreach/leads.json'))
AGGREGATOR_DOMAINS = {
    "hn.algolia.com", "news.ycombinator.com", "reddit.com", "indiehackers.com",
    "upwork.com", "linkedin.com", "gravityflow.io", "docparsemagic.com",
    "timedoctor.com", "techweez.com", "docsie.io", "freelancer.com",
    "pinterest.com", "bing.com", "google.com", "youtube.com", "twitter.com",
    "x.com", "facebook.com", "instagram.com", "tiktok.com", "craigslist.org",
    "ebay.com", "amazon.com", "github.com",
}

cleaned = []
removed = 0
for l in data:
    domain = urlparse(l.get("url", "")).netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    if domain in AGGREGATOR_DOMAINS:
        removed += 1
        continue
    if l.get("total_score", 0) < 3:
        removed += 1
        continue
    cleaned.append(l)

with open('data/outreach/leads.json', 'w') as f:
    json.dump(cleaned, f, indent=2, default=str)

print(f"Removed {removed} leads, kept {len(cleaned)} leads")
