---
name: financial-services
description: >
  Financial data, trading, analysis, and compliance tools.
triggers:
  - financial: 金融/financial/投资/
  - trading: 交易/trading/
metadata:
  category: finance
  compliance: true
---

# Financial Services

## Market Data

```bash
finance quote AAPL --period 3mo --interval 1d
finance screen --criteria "market_cap>10B,roe>15%" --limit 50
```

## Analysis

```bash
finance analyze --symbol AAPL --model buffett
finance portfolio-optimize --holdings holdings.json --risk tolerance
```