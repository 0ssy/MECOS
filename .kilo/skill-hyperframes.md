---
name: hyperframes
description: >
  Advanced UI framework patterns and component libraries.
triggers:
  - hyperframes: hyperframes/框架/framework/
  - framework: framework/ui-library/
metadata:
  category: frontend
---

# Hyperframes - UI Framework Tools

## Component Generation

```bash
hyperframes component --type card --framework react --variant elevated
hyperframes layout --type responsive-grid --breakpoints "320px,768px"
hyperframes animation --type fade --duration 300ms
```

## Framework Setup

```bash
hyperframes init --template nextjs-shadcn --typescript
hyperframes add-component --name DataTable --props "data,columns"
```