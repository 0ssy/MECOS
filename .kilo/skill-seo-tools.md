---
name: seo-tools
description: >
  SEO analysis, keyword research, and content optimization.
triggers:
  - seo: SEO/搜索优化/关键词/
metadata:
  category: marketing
---

# SEO Tools

## Keyword Research

```bash
seo keywords --seed "ai development" --volume min-1000 --difficulty max-50
seo competitor-keywords --domain example.com --limit 100
```

## Content Optimization

```bash
seo optimize-content --file ./blog.md --target "artificial intelligence"
seo check-density --text "content here" --keyword "ai tools"
```

## Technical Audit

```bash
seo audit-site --url https://example.com --depth 3
seo check-links --url https://example.com --report broken,redirect
```