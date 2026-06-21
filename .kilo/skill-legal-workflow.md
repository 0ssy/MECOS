---
name: legal-workflow
description: >
  Legal document analysis, contract review, and compliance tools.
triggers:
  - legal: 法律/legal/法规/
  - contract: 合同/contract/
metadata:
  compliance: true
  category: legal
---

# Legal Workflow

## Document Review

```bash
legal review --file ./contract.pdf --checklist standard
legal extract-clauses --document ./nda.docx --type confidentiality
legal diff --old contract-v1.docx --new contract-v2.docx
```

## Compliance

```bash
legal compliance-check --jurisdiction us --document ./policy.md
legal risk-assess --contract ./employment.pdf --level high
```