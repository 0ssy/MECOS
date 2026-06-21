---
name: notebook-llm
description: >
  Jupyter notebook integration with LLM assistance.
triggers:
  - notebook: notebook/笔记本/jupyter/
metadata:
  category: data
---

# Notebook LLM

## Notebook Operations

```bash
notebook new --template analysis-python
notebook run --file analysis.ipynb --params "symbol=AAPL,period=1y"
notebook explain --cell "df.groupby('category').sum()" --detail beginner
```

## Cell Management

```bash
notebook insert --after cell-5 --code "import pandas as pd"
notebook merge --notebooks part1.ipynb,part2.ipynb --output combined.ipynb
```