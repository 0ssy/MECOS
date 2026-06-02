"""
MECOS Knowledge Core
====================
Local knowledge graph using NetworkX. No API keys required.
Stores Subject-Predicate-Object triplets and supports graph traversal.
"""

import logging
from datetime import datetime
from pathlib import Path

import networkx as nx

logger = logging.getLogger(__name__)

GRAPH_FILE = Path("mecos_brain.gml")


class KnowledgeGraph:
    """
    Stores facts as a directed graph of (subject, predicate, object) triplets.
    Persists to disk as a GML file.
    """

    def __init__(self, graph_path: Path = GRAPH_FILE):
        self.graph_path = graph_path
        self.graph: nx.DiGraph = self._load()

    def _load(self) -> nx.DiGraph:
        if self.graph_path.exists():
            try:
                graph = nx.read_gml(str(self.graph_path))
                logger.info("Loaded graph: %d nodes, %d edges", graph.number_of_nodes(), graph.number_of_edges())
                return nx.DiGraph(graph)
            except Exception as exc:
                logger.warning("Could not load graph (%s). Starting fresh.", exc)
        return nx.DiGraph()

    def save(self):
        nx.write_gml(self.graph, str(self.graph_path))
        logger.info("Graph saved: %d nodes, %d edges", self.graph.number_of_nodes(), self.graph.number_of_edges())

    def add_triplet(self, subject: str, predicate: str, obj: str, source: str = "", confidence: float = 1.0):
        """Add a single (subject, predicate, object) fact."""
        subject_token = subject.strip().lower()
        object_token = obj.strip().lower()
        predicate_token = predicate.strip().upper().replace(" ", "_")

        if not self.graph.has_node(subject_token):
            self.graph.add_node(subject_token, label=subject.strip(), added=datetime.utcnow().isoformat())
        if not self.graph.has_node(object_token):
            self.graph.add_node(object_token, label=obj.strip(), added=datetime.utcnow().isoformat())

        self.graph.add_edge(
            subject_token,
            object_token,
            predicate=predicate_token,
            source=source,
            confidence=confidence,
            added=datetime.utcnow().isoformat(),
        )

    def add_triplets(self, triplets: list[tuple], source: str = ""):
        for triplet in triplets:
            if len(triplet) == 3:
                self.add_triplet(triplet[0], triplet[1], triplet[2], source=source)

    def get_relations(self, concept: str) -> list[dict]:
        """Return all edges (both directions) touching a concept."""
        concept_token = concept.strip().lower()
        results = []
        for _, target, data in self.graph.out_edges(concept_token, data=True):
            results.append({"subject": concept_token, "predicate": data.get("predicate"), "object": target})
        for source, _, data in self.graph.in_edges(concept_token, data=True):
            results.append({"subject": source, "predicate": data.get("predicate"), "object": concept_token})
        return results

    def path_between(self, start: str, end: str) -> list[str] | None:
        """Find a relationship path from start to end concept."""
        start_token, end_token = start.strip().lower(), end.strip().lower()
        try:
            return nx.shortest_path(self.graph.to_undirected(), start_token, end_token)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def related_concepts(self, concept: str, depth: int = 2) -> list[str]:
        """BFS: return all concepts reachable within `depth` hops."""
        concept_token = concept.strip().lower()
        if concept_token not in self.graph:
            return []
        visited = set()
        frontier = {concept_token}
        for _ in range(depth):
            next_frontier = set()
            for node in frontier:
                neighbors = set(self.graph.successors(node)) | set(self.graph.predecessors(node))
                next_frontier |= neighbors - visited
            visited |= frontier
            frontier = next_frontier
        visited.discard(concept_token)
        return list(visited)

    def stats(self) -> dict:
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "graph_file": str(self.graph_path),
        }
