"""
MECOS Curriculum Engine
========================
Takes the generated domain list and builds an intelligent
learning sequence — not random, not alphabetical, but
dependency-aware and optimised for knowledge retention.

Key insight: learning "machine learning" before "linear algebra"
wastes time. The curriculum engine builds a dependency graph
and sequences learning so foundations always come first.
"""

import json
import logging
from pathlib import Path
from collections import defaultdict, deque

logger = logging.getLogger("mecos.curriculum")


# ------------------------------------------------------------------ #
#  Domain dependency map                                               #
#  format: "advanced topic": ["prerequisite 1", "prerequisite 2"]     #
# ------------------------------------------------------------------ #

DEPENDENCIES = {
    # Math dependencies
    "calculus":                      ["algebra", "trigonometry"],
    "linear algebra":                ["algebra", "arithmetic"],
    "differential equations":        ["calculus", "linear algebra"],
    "probability theory":            ["algebra", "calculus"],
    "statistics":                    ["probability theory"],
    "stochastic processes":          ["probability theory", "calculus"],
    "measure theory":                ["calculus", "set theory"],
    "functional analysis":           ["linear algebra", "calculus"],
    "differential geometry":         ["calculus", "linear algebra"],
    "algebraic topology":            ["algebra", "set theory"],

    # CS dependencies
    "machine learning":              ["linear algebra", "statistics", "calculus"],
    "deep learning":                 ["machine learning", "linear algebra"],
    "natural language processing":   ["machine learning", "linguistics"],
    "computer vision":               ["machine learning", "linear algebra"],
    "reinforcement learning":        ["machine learning", "probability theory"],
    "neural architecture search":    ["deep learning"],
    "federated learning":            ["machine learning", "distributed systems"],
    "quantum algorithms":            ["quantum mechanics", "algorithms"],
    "compiler design":               ["algorithms", "data structures"],
    "distributed consensus":         ["distributed systems", "algorithms"],

    # Finance dependencies
    "derivatives pricing":           ["probability theory", "calculus", "finance"],
    "stochastic calculus finance":   ["stochastic processes", "finance"],
    "portfolio optimization":        ["statistics", "linear algebra", "finance"],
    "market microstructure":         ["economics", "finance"],
    "high frequency trading":        ["market microstructure", "algorithms"],
    "credit risk modelling":         ["statistics", "finance"],
    "volatility modelling":          ["statistics", "derivatives pricing"],
    "factor investing":              ["statistics", "finance"],
    "algorithmic trading":           ["programming", "finance", "statistics"],

    # Science dependencies
    "quantum mechanics":             ["classical physics", "linear algebra"],
    "quantum computing":             ["quantum mechanics", "computer science"],
    "relativity":                    ["classical physics", "calculus"],
    "nuclear physics":               ["quantum mechanics"],
    "biochemistry":                  ["chemistry", "biology"],
    "molecular biology":             ["biochemistry", "genetics"],
    "computational biology":         ["biology", "algorithms"],
    "systems biology":               ["biology", "systems engineering"],
    "synthetic biology":             ["molecular biology", "engineering"],
    "neuroeconomics":                ["neuroscience", "economics"],
    "computational neuroscience":    ["neuroscience", "mathematics"],

    # Advanced interdisciplinary
    "econophysics":                  ["physics", "economics", "statistics"],
    "computational social science":  ["sociology", "machine learning", "statistics"],
    "complexity economics":          ["economics", "complex adaptive systems"],
    "climate finance":               ["climate science", "finance"],
    "legal technology":              ["law", "natural language processing"],
}

# Category learning order — broad sequence
CATEGORY_ORDER = [
    "reinforcement",      # fix weak spots first
    "bridge",             # connect what we know
    "depth",              # go deeper
    "interdisciplinary",  # cross-domain
    "application",        # practical use
    "frontier",           # cutting edge
    "emerging",           # newest fields
]


class CurriculumEngine:
    """
    Builds an optimised learning sequence from a domain list.

    Process:
    1. Build a dependency graph for the domain list
    2. Topological sort — prerequisites before advanced topics
    3. Group into weekly batches for pacing
    4. Assign learning intervals (fundamentals get more time)
    5. Output a structured curriculum with timing
    """

    def __init__(self, domains: list[dict], existing_knowledge: set):
        self.domains   = domains
        self.known     = set(k.lower() for k in existing_knowledge)
        self.dep_graph = self._build_dependency_graph()

    def _build_dependency_graph(self) -> dict:
        """Build a dependency graph for the domain list."""
        domain_names = {d["name"].lower() for d in self.domains}
        graph = defaultdict(list)

        for domain in self.domains:
            name = domain["name"].lower()
            # Find any known dependencies
            for dep_topic, prereqs in DEPENDENCIES.items():
                if dep_topic in name:
                    for prereq in prereqs:
                        prereq_lower = prereq.lower()
                        # Prereq is already known — no dependency needed
                        if any(prereq_lower in k for k in self.known):
                            continue
                        # Prereq is in this cycle's domains
                        if any(prereq_lower in d for d in domain_names):
                            matching = next(
                                (d for d in domain_names if prereq_lower in d), None
                            )
                            if matching:
                                graph[name].append(matching)  # name depends on matching

        return graph

    def topological_sort(self) -> list[dict]:
        """
        Kahn's algorithm for topological sort.
        Ensures prerequisites come before the topics that need them.
        """
        domain_map  = {d["name"].lower(): d for d in self.domains}
        in_degree   = defaultdict(int)
        adj         = defaultdict(list)

        for node, deps in self.dep_graph.items():
            for dep in deps:
                adj[dep].append(node)
                in_degree[node] += 1

        # Start with nodes that have no prerequisites
        queue = deque([
            name for name in domain_map
            if in_degree[name] == 0
        ])

        sorted_domains = []
        while queue:
            node = queue.popleft()
            if node in domain_map:
                sorted_domains.append(domain_map[node])
            for neighbour in adj[node]:
                in_degree[neighbour] -= 1
                if in_degree[neighbour] == 0:
                    queue.append(neighbour)

        # Add any remaining (circular deps or unresolved)
        added = {d["name"].lower() for d in sorted_domains}
        for d in self.domains:
            if d["name"].lower() not in added:
                sorted_domains.append(d)

        return sorted_domains

    def build_curriculum(self, learn_interval_minutes: int = 10) -> dict:
        """
        Build the full curriculum with timing and batching.

        Returns:
        - ordered domain list
        - weekly batches
        - estimated completion time
        - learning schedule
        """
        ordered = self.topological_sort()

        # Assign learning time per domain based on complexity
        for d in ordered:
            d["learn_minutes"]  = self._estimate_learn_time(d)
            d["repeat_after"]   = self._spaced_repetition_interval(d)

        # Group into weekly batches (7 days × 24h × 6 topics/hour = ~1000/week max)
        # At 10min intervals: 144 topics/day, 1008/week — so 200 domains ≈ 2 days
        batches = self._build_weekly_batches(ordered, learn_interval_minutes)

        total_minutes = sum(d["learn_minutes"] for d in ordered)

        curriculum = {
            "total_domains":          len(ordered),
            "total_estimated_hours":  round(total_minutes / 60, 1),
            "learn_interval_minutes": learn_interval_minutes,
            "ordered_domains":        ordered,
            "weekly_batches":         batches,
            "spaced_repetition":      self._build_repetition_schedule(ordered),
        }

        return curriculum

    def _estimate_learn_time(self, domain: dict) -> int:
        """Estimate minutes needed to learn a domain well."""
        category = domain.get("category", "general")
        name     = domain["name"].lower()

        base = 10  # default

        # Complex domains need more time
        if any(w in name for w in ["advanced", "theory", "mathematics", "computational"]):
            base = 20
        if category in ("depth", "interdisciplinary"):
            base = 15
        if category == "reinforcement":
            base = 8   # already partially known

        return base

    def _spaced_repetition_interval(self, domain: dict) -> int:
        """
        How many hours until MECOS should revisit this domain.
        Based on Ebbinghaus forgetting curve.
        """
        coverage = domain.get("coverage", 0)
        if coverage > 0.8:   return 168   # 1 week
        if coverage > 0.5:   return 72    # 3 days
        if coverage > 0.3:   return 24    # 1 day
        return 12                         # 12 hours (new/weak)

    def _build_weekly_batches(self, domains: list[dict], interval: int) -> list[dict]:
        """Group domains into weekly learning batches."""
        per_day   = (60 // interval) * 24   # domains per day at given interval
        per_week  = per_day * 7
        batches   = []
        week      = 1

        for i in range(0, len(domains), per_week):
            batch = domains[i:i + per_week]
            batches.append({
                "week":    week,
                "domains": [d["name"] for d in batch],
                "count":   len(batch),
                "focus":   self._batch_focus(batch),
            })
            week += 1

        return batches

    def _batch_focus(self, batch: list[dict]) -> str:
        """Describe the main focus of a batch."""
        categories = [d.get("category", "general") for d in batch]
        most_common = max(set(categories), key=categories.count)
        return {
            "reinforcement":   "Strengthening weak foundations",
            "bridge":          "Building cross-domain connections",
            "depth":           "Deep specialisation",
            "interdisciplinary": "Interdisciplinary synthesis",
            "application":     "Practical applications",
            "frontier":        "Frontier knowledge",
            "emerging":        "Emerging fields",
        }.get(most_common, "General expansion")

    def _build_repetition_schedule(self, domains: list[dict]) -> list[dict]:
        """Build a spaced repetition schedule for weak domains."""
        schedule = []
        for d in domains:
            if d.get("coverage", 1.0) < 0.5:
                schedule.append({
                    "domain":        d["name"],
                    "revisit_after": d.get("repeat_after", 24),
                    "current_coverage": d.get("coverage", 0),
                })
        return sorted(schedule, key=lambda x: x["revisit_after"])
