"""
MECOS Domain Graph
==================
Tracks every domain MECOS has learned, how well it knows it,
and how domains connect to each other.

This is the map of MECOS's mind.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import networkx as nx

logger = logging.getLogger("mecos.domain_graph")

DOMAIN_GRAPH_FILE = Path("mecos_domain_graph.json")


class DomainGraph:
    """
    Tracks:
    - Which domains have been learned
    - How well each domain is understood (coverage score 0-1)
    - How domains connect to each other
    - Which domains are missing connections (gaps)
    - Which domains are most central (hubs)
    """

    def __init__(self, path: Path = DOMAIN_GRAPH_FILE):
        self.path  = path
        self.graph = nx.DiGraph()
        self._load()

    # ------------------------------------------------------------------ #
    #  Persistence                                                         #
    # ------------------------------------------------------------------ #

    def _load(self):
        if self.path.exists():
            data = json.loads(self.path.read_text())
            for node in data.get("nodes", []):
                self.graph.add_node(
                    node["name"],
                    cycle=node.get("cycle", 1),
                    coverage=node.get("coverage", 0.0),
                    triplets=node.get("triplets", 0),
                    added=node.get("added", ""),
                    category=node.get("category", "general"),
                    depth=node.get("depth", 1),
                )
            for edge in data.get("edges", []):
                self.graph.add_edge(
                    edge["source"], edge["target"],
                    weight=edge.get("weight", 1.0),
                    relation=edge.get("relation", "RELATED_TO"),
                )
            logger.info(
                "Domain graph loaded: %d domains, %d connections",
                self.graph.number_of_nodes(),
                self.graph.number_of_edges(),
            )
        else:
            logger.info("No domain graph found. Starting fresh.")

    def save(self):
        data = {
            "nodes": [
                {
                    "name":     n,
                    "cycle":    self.graph.nodes[n].get("cycle", 1),
                    "coverage": self.graph.nodes[n].get("coverage", 0.0),
                    "triplets": self.graph.nodes[n].get("triplets", 0),
                    "added":    self.graph.nodes[n].get("added", ""),
                    "category": self.graph.nodes[n].get("category", "general"),
                    "depth":    self.graph.nodes[n].get("depth", 1),
                }
                for n in self.graph.nodes
            ],
            "edges": [
                {
                    "source":   u,
                    "target":   v,
                    "weight":   self.graph[u][v].get("weight", 1.0),
                    "relation": self.graph[u][v].get("relation", "RELATED_TO"),
                }
                for u, v in self.graph.edges
            ],
            "saved": datetime.utcnow().isoformat(),
        }
        self.path.write_text(json.dumps(data, indent=2))

    # ------------------------------------------------------------------ #
    #  Writing                                                             #
    # ------------------------------------------------------------------ #

    def mark_learned(self, domain: str, triplets: int, cycle: int = 1, category: str = "general"):
        """Called after a domain has been learned."""
        coverage = min(1.0, triplets / 50)  # 50 triplets = full coverage
        if self.graph.has_node(domain):
            self.graph.nodes[domain]["coverage"] = max(
                self.graph.nodes[domain].get("coverage", 0), coverage
            )
            self.graph.nodes[domain]["triplets"] += triplets
        else:
            self.graph.add_node(
                domain,
                cycle=cycle,
                coverage=coverage,
                triplets=triplets,
                added=datetime.utcnow().isoformat(),
                category=category,
                depth=cycle,
            )

    def add_connection(self, domain_a: str, domain_b: str, relation: str = "RELATED_TO", weight: float = 1.0):
        """Add a discovered connection between two domains."""
        self.graph.add_edge(domain_a, domain_b, relation=relation, weight=weight)
        self.graph.add_edge(domain_b, domain_a, relation=f"INVERSE_{relation}", weight=weight * 0.8)

    def graph_path(self, domain_a: str, domain_b: str) -> list[str]:
        """Shortest path between two domains in the undirected graph."""
        try:
            return nx.shortest_path(self.graph.to_undirected(), domain_a, domain_b)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    # ------------------------------------------------------------------ #
    #  Analysis                                                            #
    # ------------------------------------------------------------------ #

    def coverage_score(self) -> float:
        """Overall knowledge coverage across all learned domains."""
        if not self.graph.nodes:
            return 0.0
        scores = [self.graph.nodes[n].get("coverage", 0) for n in self.graph.nodes]
        return round(sum(scores) / len(scores), 3)

    def weak_domains(self, threshold: float = 0.3) -> list[str]:
        """Domains that were learned but not deeply enough."""
        return [
            n for n in self.graph.nodes
            if self.graph.nodes[n].get("coverage", 0) < threshold
        ]

    def isolated_domains(self) -> list[str]:
        """Domains with fewer than 2 connections — isolated knowledge."""
        return [
            n for n in self.graph.nodes
            if self.graph.degree(n) < 2
        ]

    def hub_domains(self, top_n: int = 20) -> list[str]:
        """Most connected domains — the core of MECOS's knowledge."""
        centrality = nx.degree_centrality(self.graph)
        return sorted(centrality, key=centrality.get, reverse=True)[:top_n]

    def missing_bridges(self) -> list[tuple]:
        """
        Find pairs of domains that SHOULD be connected but aren't.
        These represent knowledge gaps — missing cross-domain understanding.
        """
        undirected = self.graph.to_undirected()
        # Find nodes that are close in the graph but have no direct edge
        gaps = []
        nodes = list(self.graph.nodes)
        for i, a in enumerate(nodes):
            for b in nodes[i+1:]:
                if not undirected.has_edge(a, b):
                    try:
                        path_len = nx.shortest_path_length(undirected, a, b)
                        if path_len == 2:  # connected through one intermediary but not directly
                            gaps.append((a, b, path_len))
                    except nx.NetworkXNoPath:
                        pass
        return sorted(gaps, key=lambda x: x[2])[:50]

    def stats(self) -> dict:
        return {
            "total_domains":    self.graph.number_of_nodes(),
            "total_connections": self.graph.number_of_edges(),
            "coverage_score":   self.coverage_score(),
            "weak_domains":     len(self.weak_domains()),
            "isolated_domains": len(self.isolated_domains()),
            "hub_domains":      self.hub_domains(5),
        }
