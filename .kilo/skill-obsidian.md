---
name: obsidian
description: >
  Obsidian integration for knowledge management and note-taking.
triggers:
  - obsidian: obsidian/黑曜石/
  - wikis: wiki/维基/
metadata:
  category: productivity
---

# Obsidian Integration

## Vault Operations

```bash
obsidian create --title "Daily Note" --template daily
obsidian search --query "tag:project" --limit 50
obsidian backlinks --note "Current Project"
```

## Workflow

```bash
obsidian daily --date today --template work
obsidian weekly-review --week 2024-W24 --vault ~/notes
obsidian sync --remote github --branch main
```