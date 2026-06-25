---
name: tdd-skill
description: >
  Test-driven development with red-green-refactor loop for Python projects.
triggers:
  - test: test/测试/test/测试覆盖/测试用例/
  - pytest: pytest/unittest/测试框架/
metadata:
  category: engineering
---

# TDD - Test-Driven Development

Run red-green-refactor cycle for Python projects using pytest. When triggered:
1. Read CONTEXT.md if it exists for domain language
2. Plan with user the behaviors to test (priority order)
3. Write ONE failing test, run it, see it fail
4. Write minimal code to pass, run test, see it pass
5. Repeat until all behaviors covered
6. Refactor if needed, run all tests

Tests verify behavior through public interfaces, not implementation details.