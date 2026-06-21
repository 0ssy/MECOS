---
name: social-media-skills
description: >
  Social media management across platforms - posting, scheduling, analytics.
triggers:
  - social: 社媒/社交/social media/twitter/facebook/linkedin/
  - schedule: 定时发帖/发布/
metadata:
  platforms: [twitter, linkedin, facebook, instagram, tiktok]
---

# Social Media Skills

## Platform Management

```bash
social post --platform twitter --content "Hello world!"
social schedule --platforms twitter,linkedin --content "New post" --time "2024-01-01T12:00"
social analytics --platform all --period last-week
```