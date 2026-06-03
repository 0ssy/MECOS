"""
Cross-domain inference engine for MECOS knowledge synthesis and analogies.
"""

from __future__ import annotations

from typing import Dict, List


class CrossDomainInferenceEngine:
    def __init__(self, kg, domain_graph):
        self.kg = kg
        self.dg = domain_graph

    def cross_domain_query(self, concept: str, max_hops: int = 4) -> dict:
        concept_token = str(concept).strip().lower()
        direct = self.kg.get_relations(concept_token)
        related = self.kg.related_concepts(concept_token, depth=max_hops)
        domain_map = self._map_to_domains(related)
        paths = self._find_cross_domain_paths(concept_token, domain_map)
        insight = self._synthesise(concept_token, paths, domain_map)
        return {
            "concept": concept_token,
            "direct_facts": direct[:10],
            "domains_touched": list(domain_map.keys()),
            "cross_paths": paths[:5],
            "insight": insight,
        }

    def find_analogies(self, source_domain: str, target_domain: str) -> list[dict]:
        source_concepts = self._get_domain_concepts(source_domain)
        target_concepts = self._get_domain_concepts(target_domain)
        analogies = []
        for sc in source_concepts[:20]:
            sc_rels = {r["predicate"] for r in self.kg.get_relations(sc) if r.get("predicate")}
            for tc in target_concepts[:20]:
                tc_rels = {r["predicate"] for r in self.kg.get_relations(tc) if r.get("predicate")}
                overlap = sc_rels & tc_rels
                if len(overlap) >= 2:
                    analogies.append(
                        {
                            "source_concept": sc,
                            "target_concept": tc,
                            "shared_relations": list(overlap),
                            "analogy": f"{sc} in {source_domain} is analogous to {tc} in {target_domain}",
                        }
                    )
        return sorted(analogies, key=lambda x: -len(x["shared_relations"]))

    def _map_to_domains(self, concepts: List[str]) -> Dict[str, List[str]]:
        domain_map: Dict[str, List[str]] = {}
        for node in self.dg.graph.nodes:
            node_lower = str(node).lower()
            for concept in concepts:
                concept_lower = str(concept).lower()
                if concept_lower in node_lower or node_lower in concept_lower:
                    domain_map.setdefault(str(node), []).append(concept_lower)
        return domain_map

    def _find_cross_domain_paths(self, concept: str, domain_map: dict) -> list[list]:
        paths = []
        domains = list(domain_map.keys())
        for i in range(len(domains) - 1):
            if hasattr(self.dg, "graph_path"):
                path = self.dg.graph_path(domains[i], domains[i + 1])
            else:
                path = []
            if path:
                paths.append(path)
        return paths

    def _synthesise(self, concept: str, paths: list, domain_map: dict) -> str:
        domains = list(domain_map.keys())
        if not domains:
            return f"No cross-domain connections found for '{concept}'"
        return (
            f"'{concept}' connects {len(domains)} domains: "
            f"{', '.join(domains[:5])}. "
            f"Cross-domain paths found: {len(paths)}."
        )

    def _get_domain_concepts(self, domain: str) -> list[str]:
        domain_lower = str(domain).lower()
        return [n for n in self.kg.graph.nodes if domain_lower in n or n in domain_lower]
