---
name: triage
description: >
  Move issues through a state machine of triage roles (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix).
triggers:
  - issue: issue/问题/议题/议题跟踪/
  - github: github/GitHub/
metadata:
  category: engineering
---

# Triage

Process incoming issues through the five-role triage state machine:

1. **needs-triage** → Evaluate issue
2. **needs-info** → Waiting on reporter
3. **ready-for-agent** → Fully specified, ready for AFK agent
4. **ready-for-human** → Needs human implementation
5. **wontfix** → Will not be actioned

Uses GitHub CLI (`gh`) to read, label, and update issues.