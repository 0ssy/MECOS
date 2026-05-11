# MECOS Architectural Diagram

```mermaid
graph TD
    subgraph "Phase 1: Memory System"
        MS[MemorySystem]
        MS --> VDB[(Vector DB: ChromaDB)]
        MS --> EM[Embeddings: sentence-transformers]
    end

    subgraph "Phase 2: Perception Layer"
        PL[PerceptionLayer]
        WP[WebPerception]
        SP[ScreenPerception]
        PL --> MS
        WP --> MS
        SP --> MS
    end

    subgraph "Phase 3: Reasoning Core"
        RE[Reasoner]
        RE --> MS
        RE --> LLM[Local LLM: Llama3/Mistral]
    end

    subgraph "Phase 4: Tool Orchestration"
        TO[ToolOrchestrator]
        AE[ActionExecutionEngine]
        TR[ToolRegistry]
        CE[CodeExecutor]
        FO[FileOperations]
        BA[BrowserAutomation]
        AC[AppController]
        
        RE --> AE
        AE --> TO
        TO --> TR
        TR --> CE
        TR --> FO
        TR --> BA
        TR --> AC
    end

    subgraph "Phase 5: Specialized Agents"
        CO[AgentCoordinator]
        TA[TradingAgent]
        CA[CodingAgent]
        RA[ResearchAgent]
        
        RE --> CO
        CO --> TA
        CO --> CA
        CO --> RA
        TA --> TO
        CA --> TO
        RA --> TO
    end

    subgraph "Phase 6: Learning Engines"
        LE[Learning Coordinator]
        RL[RLTrainer]
        SSL[SelfSupervisedTrainer]
        CM[CurriculumManager]
        MC[MemoryConsolidation]
        BE[BenchmarkingEngine]
        
        AE --> RL
        MS --> SSL
        MS --> MC
        RL --> CM
        BE --> LE
    end

    subgraph "Phase 7: Evolution & Meta-Learning"
        ML[MetaLearner]
        GO[GeneticOptimizer]
        SE[StrategyEvolution]
        CP[CheckpointManager]
        WM[WorldModel]
        
        LE --> ML
        ML --> GO
        ML --> SE
        ML --> CP
        RE --> WM
        WM --> AE
    end

    %% Flow of the Cognitive Loop
    User((User Goal)) --> RE
    RE -- "Plan" --> WM
    WM -- "Risk Assessment" --> AE
    AE -- "Execute" --> TO
    TO -- "Result" --> MS
    AE -- "Outcome" --> RL
    RL -- "Learn" --> MS
    AE -- "Reflect" --> RE
```

## Digital Organism Lifecycle
1. **Observe**: Perception layers scan files, web, and screen.
2. **Encode**: Data is converted to vector embeddings.
3. **Store**: Memories are persisted in the local vector database.
4. **Reason**: Local LLM generates plans and strategies.
5. **Act**: Tool orchestrator executes actions in a safe sandbox.
6. **Evaluate**: Benchmarking and reflection assess performance.
7. **Adapt**: Meta-learning and evolution mutate strategies for improvement.
