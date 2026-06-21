---
name: last30days
version: "3.7.0"
description: >
  Research topics across social platforms in the last 30 days.
triggers:
  - last30days: /last30days/research the last 30 days/
  - research: 调研/research/search/
metadata:
  compatible: agent_reach
  sources: [reddit, x, youtube, hackernews, github, web]
---

# Last30Days - Recency Research Skill

Research ANY topic across social platforms. Works with agent_reach.

## Usage

```bash
/last30days "topic"
/last30days "topic" --github-user username
/last30days "topic" --competitors
```

## Commands

```bash
mcporter call 'reddit.search_feeds(keyword: "topic")' --timeout 120000
twitter search "topic" -n 10
yt-dlp --write-sub --skip-download -o "/tmp/%(id)s" "URL"
```