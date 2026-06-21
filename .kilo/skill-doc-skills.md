---
name: doc-skills
description: >
  Documentation generation, management, and publishing tools.
triggers:
  - docs: 文档/docs/
  - documentation: documentation/
metadata:
  category: productivity
---

# Doc Skills

## Documentation Generation

```bash
docs generate --source ./src --format typedoc
docs api --source ./openapi.json --template redoc
```

## Publishing

```bash
docs publish --platform github-pages --branch gh-pages
docs sync --source ./docs --target notion --format markdown
```