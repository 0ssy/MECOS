---
name: kilocode
description: >
  Code management and development workflow tools.
triggers:
  - kilocode: kilocode/代码/开发/
metadata:
  ecosystem: kilo
---

# KiloCode - Development Tools

## Code Generation

```bash
kilocode generate --template python-fastapi --name myapi
kilocode component --type react --name MyComponent
```

## Workspace Management

```bash
kilocode init --template agent-project
kilocode checkpoint --message "save point"
```