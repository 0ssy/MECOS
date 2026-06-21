---
name: gstack
description: >
  Google Cloud Stack integration for deploying and managing cloud functions,
  containers, and infrastructure with AI assistance.
triggers:
  - gcp: gcp/google cloud/gcloud/
  - stack: gstack/deploy stack/
metadata:
  cloud: gcp
  categories: [cloud, deployment]
---

# GStack - Google Cloud Integration

## Deployment Commands

```bash
gstack deploy-function --source ./src --entry-point handler --runtime python311
gstack deploy-run --image gcr.io/project/app --port 8080
```

## Monitoring

```bash
gstack logs --service my-service --tail
gstack metrics --resource cpu --duration 1h
```