# MECOS Architecture

The Modular Evolutionary Cognitive Operating System is structured as a hierarchical yet distributed society of cognitive layers.

## Layered Hierarchy

1.  **Perception Layer**: Raw data acquisition from screen, files, and web.
2.  **Encoding Layer**: Semantic conversion of raw data into processable formats.
3.  **Memory Layer**: Multi-tier storage (Short-term, Episodic, Semantic, Procedural, Strategic, Reflection, Vector, and Cold).
4.  **Retrieval Layer**: Context-aware similarity search and data fetching.
5.  **Transformer Reasoning Layer**: The core inference engine utilizing custom transformer architectures.
6.  **Reflection Layer**: Self-analysis of actions and outcomes.
7.  **Planning Layer**: Strategic decomposition of goals into actionable steps.
8.  **Tool Orchestration Layer**: Execution of actions via system tools and APIs.
9.  **Evolution Layer**: Recursive improvement of prompts, strategies, and architectures.
10. **World Model Layer**: Predictive modeling of environment consequences.
11. **Meta-Learning Layer**: Optimization of the learning process itself.

## Communication: Event Bus System
Subsystems do not necessarily call each other directly in a monolithic fashion. Instead, they communicate via an **Event Bus**.
- *Example*: A pattern detected by the Vision Agent emits an event that triggers the Planner and Memory systems simultaneously.

## Deployment Strategy
- **Main Node**: Primary reasoning and coordination.
- **Memory Node**: (e.g., an old laptop) Dedicated to vector storage, archives, and semantic graphs.
- **Training/Evaluation Nodes**: Offloaded compute for reinforcement learning and benchmarking.
