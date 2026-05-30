"""
MECOS Cognition Layer — Skill-Tree-Driven Task Planner
Tasks are selected based on current skill levels and domain priorities.
Low-skill domains get foundational tasks; high-skill domains get advanced ones.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from loguru import logger


@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    layer: str = "core"
    phase: str = "foundation"
    status: str = "PENDING"
    difficulty: float = 0.5      # 0.0 = easiest, 1.0 = hardest
    domain: str = "general"      # for skill tracking
    subtasks: List["Task"] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# Task bank: organized by domain and difficulty
TASK_BANK: Dict[str, List[Dict]] = {
    "research": [
        {"title": "Basic Web Crawl", "difficulty": 0.1,
         "description": "Crawl and analyze local-first knowledge sources", "phase": "foundation"},
        {"title": "Topic Deep Dive", "difficulty": 0.4,
         "description": "Deep research on autonomous runtime architectures", "phase": "learning"},
        {"title": "Comparative Analysis", "difficulty": 0.6,
         "description": "Compare multiple approaches to recursive self-improvement", "phase": "learning"},
        {"title": "Novel Synthesis", "difficulty": 0.8,
         "description": "Synthesize research into actionable MECOS improvements", "phase": "evolution"},
        {"title": "Research Validation", "difficulty": 0.9,
         "description": "Validate research findings against real implementations", "phase": "evolution"},
    ],
    "coding": [
        {"title": "Sandbox Probe", "difficulty": 0.1,
         "description": "Generate and validate simple utility code in sandbox", "phase": "foundation"},
        {"title": "Module Refactor", "difficulty": 0.4,
         "description": "Refactor existing MECOS module for better performance", "phase": "learning"},
        {"title": "Tool Creation", "difficulty": 0.6,
         "description": "Create a new internal utility tool", "phase": "learning"},
        {"title": "Architecture Improvement", "difficulty": 0.8,
         "description": "Improve a core MECOS architectural component", "phase": "evolution"},
        {"title": "Self-Modification", "difficulty": 0.95,
         "description": "Safely modify own reasoning pipeline", "phase": "evolution"},
    ],
    "memory": [
        {"title": "Memory Sync", "difficulty": 0.1,
         "description": "Load vector memory and knowledge graph context", "phase": "foundation"},
        {"title": "Memory Compression", "difficulty": 0.4,
         "description": "Compress raw memories into structured knowledge", "phase": "learning"},
        {"title": "Contradiction Scan", "difficulty": 0.6,
         "description": "Detect and resolve contradictions in memory store", "phase": "learning"},
        {"title": "Knowledge Distillation", "difficulty": 0.8,
         "description": "Distill episodic memories into semantic concepts", "phase": "evolution"},
    ],
    "trading": [
        {"title": "Performance Review", "difficulty": 0.2,
         "description": "Ingest Sharpe and drawdown metrics into optimization loop", "phase": "evolution"},
        {"title": "Strategy Analysis", "difficulty": 0.5,
         "description": "Analyze which agents are performing best this session", "phase": "evolution"},
        {"title": "Walk-Forward Validation", "difficulty": 0.8,
         "description": "Run walk-forward backtest on accumulated data", "phase": "evolution"},
    ],
    "evolution": [
        {"title": "Benchmark Scoring", "difficulty": 0.3,
         "description": "Benchmark outcomes and feed self-improvement loop", "phase": "evolution"},
        {"title": "Strategy Evolution", "difficulty": 0.6,
         "description": "Evolve behavioral strategies based on benchmark results", "phase": "evolution"},
        {"title": "Hyperparameter Optimization", "difficulty": 0.8,
         "description": "Optimize meta-learning hyperparameters via genetic search", "phase": "evolution"},
    ],
    "orchestration": [
        {"title": "Runtime Boot", "difficulty": 0.1,
         "description": "Initialize autonomous runtime for goal", "phase": "foundation"},
        {"title": "Component Health Check", "difficulty": 0.3,
         "description": "Verify all subsystems are operating correctly", "phase": "foundation"},
        {"title": "Process Coordination", "difficulty": 0.7,
         "description": "Coordinate worker processes and message routing", "phase": "evolution"},
    ],
}


class SkillAwareTaskPlanner:
    """
    Selects tasks based on current skill levels per domain.
    Novice domains get easy foundational tasks.
    Expert domains get advanced evolution tasks.
    Tasks are randomized within difficulty band to prevent repetition.
    """

    def __init__(self):
        self.active_plan: List[Task] = []
        self._skill_levels: Dict[str, float] = {}  # domain -> 0.0-1.0

    def update_skill(self, domain: str, score: float):
        """Update skill level for a domain (called by CurriculumManager)."""
        current = self._skill_levels.get(domain, 0.0)
        # Exponential moving average: new skill = 0.8 * old + 0.2 * new_score
        self._skill_levels[domain] = 0.8 * current + 0.2 * float(score)

    def get_skill(self, domain: str) -> float:
        return self._skill_levels.get(domain, 0.0)

    def _select_task_for_domain(self, domain: str) -> Optional[Dict]:
        """Select a task appropriate for current skill level in domain."""
        import random
        tasks = TASK_BANK.get(domain, [])
        if not tasks:
            return None

        skill = self.get_skill(domain)
        # Allow tasks within ±0.25 of current skill level
        band_low  = max(0.0, skill - 0.1)
        band_high = min(1.0, skill + 0.35)
        candidates = [t for t in tasks if band_low <= t["difficulty"] <= band_high]
        if not candidates:
            # Fallback: easiest task
            candidates = [min(tasks, key=lambda t: t["difficulty"])]
        return random.choice(candidates)

    def create_plan(self, goal: str, max_tasks: int = 6) -> List[Task]:
        """Create a skill-aware plan for the given goal."""
        import random
        plan = []

        # Always include orchestration boot
        boot = self._select_task_for_domain("orchestration")
        if boot:
            plan.append(Task(
                title=boot["title"],
                description=f"{boot['description']} — goal: {goal}",
                layer="orchestration",
                phase=boot["phase"],
                difficulty=boot["difficulty"],
                domain="orchestration",
            ))

        # Always include memory sync
        mem = self._select_task_for_domain("memory")
        if mem:
            plan.append(Task(
                title=mem["title"],
                description=mem["description"],
                layer="memory",
                phase=mem["phase"],
                difficulty=mem["difficulty"],
                domain="memory",
            ))

        # Fill remaining slots based on priority and skill
        domains_by_priority = ["research", "coding", "trading", "evolution"]
        random.shuffle(domains_by_priority)

        for domain in domains_by_priority:
            if len(plan) >= max_tasks:
                break
            task_spec = self._select_task_for_domain(domain)
            if task_spec:
                plan.append(Task(
                    title=task_spec["title"],
                    description=task_spec["description"],
                    layer=domain,
                    phase=task_spec["phase"],
                    difficulty=task_spec["difficulty"],
                    domain=domain,
                ))

        self.active_plan = plan
        skill_summary = {d: f"{self.get_skill(d):.2f}" for d in ["research", "coding", "trading", "memory"]}
        logger.info(f"SkillAwareTaskPlanner: {len(plan)} tasks | skills={skill_summary}")
        return plan

    def record_task_outcome(self, domain: str, success: bool, score: float = None):
        """Record task outcome to update skill level."""
        if score is None:
            score = 0.8 if success else 0.2
        self.update_skill(domain, score)

    def update_task_status(self, task_id: str, status: str):
        for task in self.active_plan:
            if task.id == task_id:
                task.status = status
                return
            for subtask in task.subtasks:
                if subtask.id == task_id:
                    subtask.status = status
                    return

    def get_skill_summary(self) -> Dict[str, Any]:
        from curriculum_manager import SkillLevel
        return {
            domain: {
                "score": round(score, 3),
                "level": SkillLevel.from_score(score),
            }
            for domain, score in self._skill_levels.items()
        }


# Backward-compatible alias
class TaskPlanner(SkillAwareTaskPlanner):
    pass
