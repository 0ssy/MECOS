---
name: to-prd
description: >
  Turn the current conversation into a PRD and publish to the issue tracker. No interview — just synthesizes.
triggers:
  - prd: prd/PRD/需求/需求文档/
  - spec: spec/规格/规格说明/
metadata:
  category: engineering
---

# To PRD

Convert conversation/plan into a Product Requirements Document and publish to GitHub issues.

Process:
1. Synthesize discussed requirements
2. Structure as PRD with:
   - Problem statement
   - Goals & non-goals
   - Success criteria
   - Edge cases
   - Constraints
3. Publish to GitHub via `gh issue create`