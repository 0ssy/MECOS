"""
MECOS Memory Layer — Knowledge Graph
Structured relationship memory for architecture and skill evolution.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class Node:
    id: str
    type: str
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    source: str
    target: str
    relation: str
    weight: float = 1.0


class KnowledgeGraph:
    def __init__(self, storage_path: str | None = None):
        base = Path(storage_path) if storage_path else Path(__file__).resolve().parent / "data" / "knowledge_graph"
        self.storage_path = base
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.graph_file = self.storage_path / "graph.json"
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        self._load()

    def add_node(self, node_id: str, node_type: str, properties: Dict[str, Any] | None = None):
        self.nodes[node_id] = Node(node_id, node_type, properties or {})
        self._save()

    def add_edge(self, source: str, target: str, relation: str, weight: float = 1.0):
        self.edges.append(Edge(source, target, relation, float(weight)))
        self._save()

    def get_related(self, node_id: str) -> List[Dict[str, Any]]:
        related: List[Dict[str, Any]] = []
        for edge in self.edges:
            if edge.source == node_id:
                related.append({"id": edge.target, "relation": edge.relation})
            elif edge.target == node_id:
                related.append({"id": edge.source, "relation": f"inverse_{edge.relation}"})
        return related

    def _save(self):
        data = {
            "nodes": {k: {"id": v.id, "type": v.type, "properties": v.properties} for k, v in self.nodes.items()},
            "edges": [{"source": e.source, "target": e.target, "relation": e.relation, "weight": e.weight} for e in self.edges],
        }
        self.graph_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _load(self):
        if not self.graph_file.exists():
            return
        try:
            data = json.loads(self.graph_file.read_text(encoding="utf-8"))
            for _, node in data.get("nodes", {}).items():
                self.nodes[node["id"]] = Node(node["id"], node["type"], node.get("properties", {}))
            for edge in data.get("edges", []):
                self.edges.append(Edge(edge["source"], edge["target"], edge["relation"], float(edge.get("weight", 1.0))))
        except Exception:
            self.nodes = {}
            self.edges = []

