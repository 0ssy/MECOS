---
name: improve-codebase-architecture
description: >
  Scan codebase for deepening opportunities, present as HTML report, then grill through chosen opportunities.
triggers:
  - refactor: refactor/重构/优化/
  - architecture: architecture/架构/架构设计/
  - module: module/模块/模块化/
metadata:
  category: engineering
---

# Improve Codebase Architecture

Analyzes codebase for opportunities to create deeper modules (more behavior behind simpler interfaces).

Process:
1. Scan codebase structure
2. Identify areas with shallow modules or poor seams
3. Generate HTML report with findings
4. Grill through selected opportunities
5. Propose refactoring improvements