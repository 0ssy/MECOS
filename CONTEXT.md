# MECOS Domain Context

## Core Concepts

- **Goal** — A user request or autonomous objective decomposed into actions
- **Plan** — Structured sequence of tool calls to achieve a goal
- **Action** — Single tool invocation step
- **Experience** — Episodic memory record of executed actions and outcomes

## Architectural Layers

- **Perception** — Raw data acquisition (files, web, screen, apps)
- **Memory** — Vector-based episodic and semantic storage (ChromaDB)
- **Reasoner** — LLM-powered planning and reflection
- **Tool Orchestration** — Unified interface to all tools
- **Action Engine** — Plan execution with retry and audit

## Domain Terms

- **Trading** — Stock/crypto signals, risk management, portfolio actions
- **Outreach** — Email campaigns, prospecting, lead generation
- **Knowledge Graph** — Relationship storage for cross-domain inference
- **Curiosity** — Knowledge gaps identified for learning

## Testing Vocabulary

- **Tracer Bullet** — Single test → single implementation → repeat
- **Red-Green-Refactor** — Write failing test → pass → improve