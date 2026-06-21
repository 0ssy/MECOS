---
name: caveman
description: >
  Simplified, direct approaches to common tasks.
triggers:
  - caveman: caveman/原始人/简/
  - simple: simple/简单/
metadata:
  philosophy: simple-first
---

# Caveman - Simple Solutions

## Quick Actions

```bash
caveman http "GET https://api.example.com" --json
caveman scrape "https://news.example.com" --extract headlines
caveman "analyze this page" --url https://example.com
```

## Direct Operations

```bash
caveman transform --input data.json --to csv --output data.csv
caveman notify --channel "slack" --message "Task complete"
```