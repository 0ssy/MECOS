"""
Curiosity queue for self-directed domain discovery.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional


class CuriosityEngine:
    QUEUE_FILE = Path("mecos_curiosity_queue.json")

    def __init__(self, kg, domain_graph, queue_file: Optional[Path] = None):
        self.kg = kg
        self.dg = domain_graph
        self.queue_file = Path(queue_file) if queue_file is not None else self.QUEUE_FILE
        self.queue = self._load()

    def _load(self) -> List[dict]:
        if self.queue_file.exists():
            return json.loads(self.queue_file.read_text()).get("queue", [])
        return []

    def _save(self):
        self.queue_file.write_text(json.dumps({"queue": self.queue}, indent=2))

    def scan_after_learning(self, topic: str, triplets: list[tuple]):
        known = set(n.lower() for n in self.kg.graph.nodes)
        for triplet in triplets or []:
            if not isinstance(triplet, (list, tuple)) or len(triplet) != 3:
                continue
            subj, pred, obj = triplet
            for concept in [str(subj).lower(), str(obj).lower()]:
                if concept not in known and len(concept) > 3:
                    self._add_curiosity(
                        concept=concept,
                        source_topic=topic,
                        reason=f"encountered while learning {topic} - not yet known",
                        priority=self._score_priority(concept, str(pred)),
                    )

    def _score_priority(self, concept: str, predicate: str) -> int:
        important_preds = {"IS_A", "USES", "CAUSES", "ENABLES", "REQUIRES", "PART_OF"}
        return 1 if str(predicate).upper() in important_preds else 3

    def _add_curiosity(self, concept: str, source_topic: str, reason: str, priority: int):
        if any(q.get("concept") == concept for q in self.queue):
            return
        self.queue.append(
            {
                "concept": concept,
                "source_topic": source_topic,
                "reason": reason,
                "priority": int(priority),
            }
        )
        self.queue.sort(key=lambda x: int(x.get("priority", 3)))
        self._save()

    def next_curiosity(self) -> dict | None:
        if not self.queue:
            return None
        item = self.queue.pop(0)
        self._save()
        return item

    def queue_size(self) -> int:
        return len(self.queue)

    def top_curiosities(self, n: int = 10) -> list[dict]:
        return self.queue[: max(0, int(n))]
