"""
One-shot cleanup script to purge enterprise/aggregator domains from leads.json and synthesized_leads.json.
Does NOT touch archive_stale/.
"""
from __future__ import annotations

import json
from pathlib import Path

from outreach.scanner import OutreachScanner

DATA_DIR = Path("data/outreach")
LEADS_PATH = DATA_DIR / "leads.json"
SYNTHESIZED_PATH = DATA_DIR / "synthesized_leads.json"
SKIPPED_PATH = DATA_DIR / "skipped_leads.jsonl"
ARCHIVE_DIR = DATA_DIR / "archive_stale"


def purge_file(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Failed to load {path}: {exc}")
        return 0

    if not isinstance(data, list):
        print(f"{path} is not a JSON array, skipping")
        return 0

    before = len(data)
    cleaned = []
    for item in data:
        if not isinstance(item, dict):
            continue
        url = item.get("url", "")
        if url and not OutreachScanner._is_business_url(url):
            continue
        cleaned.append(item)

    after = len(cleaned)
    path.write_text(json.dumps(cleaned, indent=2, default=str), encoding="utf-8")
    removed = before - after
    print(f"{path}: removed {removed} bad leads ({before} -> {after})")
    return removed


def main():
    total_removed = 0
    total_removed += purge_file(LEADS_PATH)
    total_removed += purge_file(SYNTHESIZED_PATH)
    print(f"Total bad leads removed: {total_removed}")


if __name__ == "__main__":
    main()
