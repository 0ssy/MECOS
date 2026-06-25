---
name: grill-with-docs
description: >
  Grilling session that builds project domain model, sharpening terminology and updating CONTEXT.md/ADR inline.
triggers:
  - design: design/设计/架构/架构设计/
  - domain: domain/领域/术语/术语表/
  - context: context/上下文/
metadata:
  category: engineering
---

# Grill With Docs

Runs a grilling session to sharpen plans/design AND builds/updates project domain documentation.

Before implementation:
1. Grill through every branch of the decision tree
2. Extract domain terms and decisions
3. Update CONTEXT.md with domain language
4. Create ADRs for architectural decisions

Ensures alignment and builds shared language.