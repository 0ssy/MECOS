"""
MECOS Phase 6 - Curriculum Manager
Adaptive task difficulty scheduling, skill progression tracking,
mastery detection, and automatic curriculum generation.
"""

import json
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
from loguru import logger

from memory_system import MemorySystem
from config import settings


class SkillLevel:
    NOVICE = "novice"
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"

    LEVELS = [NOVICE, BEGINNER, INTERMEDIATE, ADVANCED, EXPERT]
    THRESHOLDS = {NOVICE: 0.0, BEGINNER: 0.4, INTERMEDIATE: 0.6, ADVANCED: 0.75, EXPERT: 0.9}

    @classmethod
    def from_score(cls, score: float) -> str:
        level = cls.NOVICE
        for lvl, threshold in cls.THRESHOLDS.items():
            if score >= threshold:
                level = lvl
        return level


class SkillTracker:
    """Tracks performance and skill level per domain."""

    def __init__(self):
        self.skills: Dict[str, Dict[str, Any]] = {}

    def record(self, domain: str, score: float, task: str = ""):
        if domain not in self.skills:
            self.skills[domain] = {
                "scores": [],
                "level": SkillLevel.NOVICE,
                "tasks_completed": 0,
            }
        self.skills[domain]["scores"].append(score)
        self.skills[domain]["tasks_completed"] += 1

        recent = self.skills[domain]["scores"][-20:]
        avg = sum(recent) / len(recent)
        self.skills[domain]["level"] = SkillLevel.from_score(avg)
        self.skills[domain]["avg_score"] = round(avg, 3)
        logger.debug(f"Skill [{domain}]: score={score:.3f}, level={self.skills[domain]['level']}")

    def get_level(self, domain: str) -> str:
        return self.skills.get(domain, {}).get("level", SkillLevel.NOVICE)

    def get_avg_score(self, domain: str) -> float:
        return self.skills.get(domain, {}).get("avg_score", 0.0)

    def is_mastered(self, domain: str, threshold: float = 0.9) -> bool:
        return self.get_avg_score(domain) >= threshold

    def summary(self) -> Dict[str, Any]:
        return {
            domain: {
                "level": data["level"],
                "avg_score": data.get("avg_score", 0.0),
                "tasks_completed": data["tasks_completed"],
            }
            for domain, data in self.skills.items()
        }


CURRICULUM_TEMPLATES = {
    "coding": [
        {"level": SkillLevel.NOVICE, "task": "Write a Python function that adds two numbers", "difficulty": 1},
        {"level": SkillLevel.BEGINNER, "task": "Implement a binary search algorithm", "difficulty": 2},
        {"level": SkillLevel.INTERMEDIATE, "task": "Build a REST API with FastAPI", "difficulty": 3},
        {"level": SkillLevel.ADVANCED, "task": "Implement an async task queue with Redis", "difficulty": 4},
        {"level": SkillLevel.EXPERT, "task": "Design a distributed caching system", "difficulty": 5},
    ],
    "trading": [
        {"level": SkillLevel.NOVICE, "task": "Calculate RSI for a price series", "difficulty": 1},
        {"level": SkillLevel.BEGINNER, "task": "Implement a simple moving average crossover strategy", "difficulty": 2},
        {"level": SkillLevel.INTERMEDIATE, "task": "Build a multi-indicator signal generator", "difficulty": 3},
        {"level": SkillLevel.ADVANCED, "task": "Implement a portfolio optimization algorithm", "difficulty": 4},
        {"level": SkillLevel.EXPERT, "task": "Design a high-frequency trading simulation", "difficulty": 5},
    ],
    "research": [
        {"level": SkillLevel.NOVICE, "task": "Summarize a short article", "difficulty": 1},
        {"level": SkillLevel.BEGINNER, "task": "Extract key facts from a research paper", "difficulty": 2},
        {"level": SkillLevel.INTERMEDIATE, "task": "Compare and contrast two competing theories", "difficulty": 3},
        {"level": SkillLevel.ADVANCED, "task": "Synthesize findings from 5 sources into a report", "difficulty": 4},
        {"level": SkillLevel.EXPERT, "task": "Generate novel hypotheses from literature review", "difficulty": 5},
    ],
    "planning": [
        {"level": SkillLevel.NOVICE, "task": "Break a simple goal into 3 steps", "difficulty": 1},
        {"level": SkillLevel.BEGINNER, "task": "Create a plan with dependencies and priorities", "difficulty": 2},
        {"level": SkillLevel.INTERMEDIATE, "task": "Plan a multi-agent collaborative task", "difficulty": 3},
        {"level": SkillLevel.ADVANCED, "task": "Design a fault-tolerant execution plan", "difficulty": 4},
        {"level": SkillLevel.EXPERT, "task": "Optimize a plan under resource constraints", "difficulty": 5},
    ],
}


class CurriculumManager:
    """
    Adaptive curriculum manager for MECOS.
    Schedules tasks based on current skill levels, tracks mastery,
    and automatically advances difficulty.
    """

    def __init__(self, memory: MemorySystem):
        self.memory = memory
        self.tracker = SkillTracker()
        self.save_dir = settings.MEMORY_DIR / "curriculum"
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self._load()
        logger.info("CurriculumManager initialized.")

    def _load(self):
        path = self.save_dir / "skill_tracker.json"
        if path.exists():
            data = json.loads(path.read_text())
            self.tracker.skills = data
            logger.info(f"Curriculum loaded: {list(data.keys())} domains")

    def _save(self):
        path = self.save_dir / "skill_tracker.json"
        path.write_text(json.dumps(self.tracker.skills, default=str))

    def get_next_task(self, domain: str) -> Optional[Dict[str, Any]]:
        """Return the next appropriate task for the current skill level."""
        templates = CURRICULUM_TEMPLATES.get(domain, [])
        if not templates:
            return None

        current_level = self.tracker.get_level(domain)
        level_order = SkillLevel.LEVELS

        # Find tasks at or just above current level
        current_idx = level_order.index(current_level) if current_level in level_order else 0
        for task in templates:
            task_level = task.get("level", SkillLevel.NOVICE)
            task_idx = level_order.index(task_level) if task_level in level_order else 0
            if task_idx >= current_idx:
                return task

        # All tasks mastered — return the hardest
        return templates[-1]

    async def record_performance(self, domain: str, score: float, task: str = "") -> Dict[str, Any]:
        """Record a performance score and update the curriculum."""
        self.tracker.record(domain, score, task)
        self._save()

        level = self.tracker.get_level(domain)
        mastered = self.tracker.is_mastered(domain)

        await self.memory.add_experience(
            f"CURRICULUM [{domain}]: score={score:.3f}, level={level}, mastered={mastered}",
            source="curriculum_manager",
        )

        result = {
            "domain": domain,
            "score": score,
            "level": level,
            "mastered": mastered,
            "next_task": self.get_next_task(domain),
        }
        logger.info(f"Curriculum [{domain}]: level={level}, mastered={mastered}")
        return result

    def get_learning_plan(self, domains: Optional[List[str]] = None) -> Dict[str, Any]:
        """Generate a learning plan for the specified domains."""
        domains = domains or list(CURRICULUM_TEMPLATES.keys())
        plan = {}
        for domain in domains:
            plan[domain] = {
                "current_level": self.tracker.get_level(domain),
                "avg_score": self.tracker.get_avg_score(domain),
                "next_task": self.get_next_task(domain),
                "mastered": self.tracker.is_mastered(domain),
            }
        return plan

    def get_skill_summary(self) -> Dict[str, Any]:
        return self.tracker.summary()
