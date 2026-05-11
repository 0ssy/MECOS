# MECOS — Modular Evolutionary Cognitive Operating System

MECOS is a fully autonomous, self-improving AI agent engine. It integrates seven architectural phases — from persistent memory and perception through to evolutionary meta-learning — into a single cohesive system capable of executing complex goals, learning from experience, and continuously improving its own strategies and capabilities.

> **Core Philosophy:** Observe → Encode → Store → Reason → Act → Evaluate → Adapt

---

## Architecture Overview

MECOS is organized into seven phases, each building on the last:

| Phase | Module(s) | Responsibility |
|-------|-----------|----------------|
| 1 | `memory_system.py` | Vector-based episodic and semantic memory (ChromaDB + sentence-transformers) |
| 2 | `perception.py`, `web_perception.py`, `screen_perception.py` | File system, web, and screen perception |
| 3 | `reasoner.py` | LLM-powered planning, reflection, and self-critique |
| 4 | `tool_registry.py`, `code_executor.py`, `file_operations.py`, `app_controller.py`, `browser_automation.py`, `tool_orchestrator.py`, `action_engine.py` | Full tool orchestration and sandboxed execution |
| 5 | `trading_agent.py`, `coding_agent.py`, `research_agent.py`, `agent_coordinator.py` | Specialized domain agents and multi-agent coordination |
| 6 | `rl_trainer.py`, `self_supervised_trainer.py`, `curriculum_manager.py`, `memory_consolidation.py`, `benchmarking.py` | Learning engines: RL, SSL, curriculum, memory distillation, benchmarking |
| 7 | `genetic_optimizer.py`, `strategy_evolution.py`, `meta_learner.py`, `checkpoint_manager.py`, `world_model.py` | Evolution and meta-learning: genetic search, strategy evolution, hyperparameter optimization, checkpointing, world model |

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
export OPENAI_API_KEY=your_key_here
```

### 3. Run the Engine

```bash
python main.py
```

### 4. Run Tests

```bash
python -m pytest tests/test_mecos.py -v
# 42 passed
```

---

## Phase Details

### Phase 1 — Memory System

Provides persistent vector memory using ChromaDB and `sentence-transformers`. All subsystems write to and read from this shared memory store.

```python
memory = MemorySystem()
await memory.add_experience("RSI below 30 signals oversold conditions", source="trading")
results = await memory.retrieve_context("RSI trading signal", n_results=5)
```

### Phase 2 — Perception Layer

- **`PerceptionLayer`** — monitors the file system, parses JSON/CSV/text, stores observations in memory.
- **`WebPerception`** — uses Playwright to browse URLs, extract page content, and store web observations.
- **`ScreenPerception`** — captures screenshots and uses OCR for visual environment awareness.

### Phase 3 — Reasoner

The cognitive core. Uses an LLM to generate structured action plans, reflect on execution results, route goals to specialized agents, and perform self-critique.

```python
plan = await reasoner.generate_plan("Analyze Bitcoin price trends and write a report")
await reasoner.reflect(goal, plan, results)
```

### Phase 4 — Tool Orchestration

- **`ToolRegistry`** — centralized registry with permission control, enable/disable, and metadata.
- **`CodeExecutor`** — sandboxed Python and Bash execution with timeout and output capture.
- **`FileOperations`** — safe file read/write/delete/search with path traversal protection and backups.
- **`AppController`** — allowlisted system command execution with process management.
- **`BrowserAutomation`** — Playwright-based browser control for navigation, clicking, and form filling.
- **`ToolOrchestrator`** — unified interface to all tools.
- **`ActionExecutionEngine`** — executes plans step-by-step with retry logic and an audit trail.

```python
result = await orchestrator.run_tool("execute_python", code="print(2 ** 10)")
# → "1024"
```

### Phase 5 — Specialized Domain Agents

- **`TradingAgent`** — RSI, MACD, Bollinger Bands, signal generation, backtesting, risk management.
- **`CodingAgent`** — code generation, AST-based syntax analysis, bug detection, test generation.
- **`ResearchAgent`** — multi-source information gathering, summarization, knowledge graph construction.
- **`AgentCoordinator`** — routes goals to the most appropriate agent, supports parallel execution.

```python
result = await coordinator.collaborative_solve("Analyze AAPL stock and write a trading strategy")
```

### Phase 6 — Learning Engines

- **`RLTrainer`** — Q-learning with epsilon-greedy exploration and experience replay. Learns which tools and actions lead to successful outcomes.
- **`SelfSupervisedTrainer`** — generates training tasks from memory (fill-in-the-blank, summarization, QA) and evaluates the engine's own responses.
- **`CurriculumManager`** — tracks skill levels (novice → expert) per domain, schedules appropriately-difficult tasks, advances difficulty as mastery is detected.
- **`MemoryConsolidation`** — distills episodic memories into semantic knowledge, scores importance, extracts patterns, prunes low-value memories.
- **`BenchmarkingEngine`** — standardized 8-task benchmark suite across reasoning, coding, planning, analysis, trading, and meta-learning. Detects regressions automatically.

### Phase 7 — Evolution & Meta-Learning

- **`GeneticOptimizer`** — evolutionary algorithm (tournament selection, uniform crossover, Gaussian mutation) for hyperparameter search.
- **`StrategyEvolution`** — evolves behavioral strategies through LLM-guided mutation and crossover. Maintains a population and selects the best performer.
- **`MetaLearner`** — top-level coordinator. Runs full meta-cycles: benchmark → detect regression → consolidate memory → RL training → SSL training → strategy evolution → adapt hyperparameters.
- **`CheckpointManager`** — full system state snapshots with versioning, rollback, diff comparison, and automatic pruning.
- **`WorldModel`** — records (state, action, outcome) triples, predicts action outcomes, simulates plan execution before committing, evaluates plan risk.

```python
results = await meta_learner.run_meta_cycle()
# Benchmarks, consolidates memory, trains RL, evolves strategies, adapts hyperparams
```

---

## Full Cognitive Cycle

When `engine.process_goal(goal)` is called:

```
1. Observe     → PerceptionLayer scans the environment
2. Plan        → Reasoner generates a structured action plan
3. Simulate    → WorldModel evaluates plan risk before execution
4. Execute     → ActionEngine runs each step with retry and audit
5. Record      → WorldModel records state transitions
6. Learn       → RLTrainer records experience and updates Q-values
7. Reflect     → Reasoner reflects on results and extracts lessons
8. Feedback    → StrategyEvolution records performance score
```

---

## File Structure

```
MECOS/
├── main.py                    # Full engine entry point (all 7 phases)
├── config.py                  # Centralized settings
│
├── memory_system.py           # Phase 1: Vector memory
├── perception.py              # Phase 2: File system perception
├── web_perception.py          # Phase 2: Web perception (Playwright)
├── screen_perception.py       # Phase 2: Screen/OCR perception
├── reasoner.py                # Phase 3: LLM planning & reflection
│
├── tool_registry.py           # Phase 4: Tool registration & permissions
├── code_executor.py           # Phase 4: Sandboxed code execution
├── file_operations.py         # Phase 4: Safe file operations
├── app_controller.py          # Phase 4: System command controller
├── browser_automation.py      # Phase 4: Browser automation
├── tool_orchestrator.py       # Phase 4: Unified tool interface
├── action_engine.py           # Phase 4: Plan execution engine
│
├── trading_agent.py           # Phase 5: Trading & market analysis
├── coding_agent.py            # Phase 5: Code generation & analysis
├── research_agent.py          # Phase 5: Research & knowledge graph
├── agent_coordinator.py       # Phase 5: Multi-agent coordination
│
├── rl_trainer.py              # Phase 6: Reinforcement learning (Q-learning)
├── self_supervised_trainer.py # Phase 6: Self-supervised training
├── curriculum_manager.py      # Phase 6: Adaptive curriculum (novice→expert)
├── memory_consolidation.py    # Phase 6: Memory distillation & pruning
├── benchmarking.py            # Phase 6: Performance benchmarking
│
├── genetic_optimizer.py       # Phase 7: Genetic hyperparameter search
├── strategy_evolution.py      # Phase 7: Behavioral strategy evolution
├── meta_learner.py            # Phase 7: Meta-learning coordinator
├── checkpoint_manager.py      # Phase 7: State checkpointing & rollback
├── world_model.py             # Phase 7: Environment world model
│
└── tests/
    └── test_mecos.py          # Full test suite (42 tests, all passing)
```

---

## Configuration

Key settings (configurable via environment variables):

| Setting | Default | Description |
|---------|---------|-------------|
| `OPENAI_API_KEY` | — | OpenAI API key (required) |
| `DEFAULT_MODEL` | `gpt-4.1-mini` | LLM model for reasoning |
| `BASE_DIR` | `~/MECOS` | Project root directory |
| `MEMORY_DIR` | `~/MECOS/memory_db` | Persistent memory storage |
| `DATA_DIR` | `~/MECOS/data` | Data directory for perception |
| `LOGS_DIR` | `~/MECOS/logs` | Log file directory |

---

## License

MIT License — see `LICENSE` for details.
