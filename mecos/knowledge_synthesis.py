"""
Cross-domain knowledge synthesis for emergent insights.
"""

from __future__ import annotations

from typing import Dict, List, Set


class KnowledgeSynthesisEngine:
    def synthesise(self, kg, dg) -> list[dict]:
        insights = []

        concept_domains = self._map_concepts_to_domains(kg, dg)
        for concept, domains in concept_domains.items():
            if len(domains) >= 3:
                insights.append(
                    {
                        "type": "universal_concept",
                        "concept": concept,
                        "domains": domains,
                        "insight": f"'{concept}' is a universal principle appearing in: {', '.join(domains[:5])}",
                        "value": len(domains),
                    }
                )

        hub_domains = dg.hub_domains(top_n=10)
        for i, da in enumerate(hub_domains):
            for db in hub_domains[i + 1 :]:
                shared = self._shared_predicates(da, db, kg)
                if len(shared) >= 3:
                    insights.append(
                        {
                            "type": "structural_analogy",
                            "domain_a": da,
                            "domain_b": db,
                            "shared": list(shared),
                            "insight": f"{da} and {db} share structural pattern: {', '.join(list(shared)[:3])}",
                            "value": len(shared),
                        }
                    )

        causal_chains = self._find_causal_chains(kg)
        for chain in causal_chains[:5]:
            domains_in_chain = self._domains_for_chain(chain, dg)
            if len(set(domains_in_chain)) >= 2:
                insights.append(
                    {
                        "type": "causal_chain",
                        "chain": chain,
                        "domains": list(set(domains_in_chain)),
                        "insight": " -> ".join(chain),
                        "value": len(set(domains_in_chain)),
                    }
                )

        return sorted(insights, key=lambda x: -x["value"])

    def _map_concepts_to_domains(self, kg, dg) -> Dict[str, List[str]]:
        concept_domains: Dict[str, List[str]] = {}
        for node in kg.graph.nodes:
            node_lower = str(node).lower()
            domains = []
            for domain in dg.graph.nodes:
                domain_lower = str(domain).lower()
                if node_lower in domain_lower or domain_lower in node_lower:
                    domains.append(domain)
            if domains:
                concept_domains[node_lower] = domains
        return concept_domains

    def _shared_predicates(self, domain_a: str, domain_b: str, kg) -> Set[str]:
        def get_predicates(domain: str) -> Set[str]:
            preds = set()
            for rel in kg.get_relations(str(domain).lower()):
                predicate = rel.get("predicate")
                if predicate:
                    preds.add(str(predicate))
            return preds

        return get_predicates(domain_a) & get_predicates(domain_b)

    def _find_causal_chains(self, kg) -> list[list]:
        chains = []
        causal_edges = [
            (u, v)
            for u, v, d in kg.graph.edges(data=True)
            if str(d.get("predicate", "")).upper() in ("CAUSES", "LEADS_TO", "RESULTS_IN", "ENABLES")
        ]
        for start, _ in causal_edges[:20]:
            chain = [start]
            current = start
            for _ in range(4):
                next_nodes = [
                    v
                    for _, v, d in kg.graph.out_edges(current, data=True)
                    if str(d.get("predicate", "")).upper() in ("CAUSES", "LEADS_TO", "RESULTS_IN", "ENABLES")
                ]
                if not next_nodes:
                    break
                current = next_nodes[0]
                chain.append(current)
            if len(chain) >= 3:
                chains.append(chain)
        return chains

    def _domains_for_chain(self, chain: list, dg) -> list:
        domains = []
        for concept in chain:
            concept_lower = str(concept).lower()
            for domain in dg.graph.nodes:
                domain_lower = str(domain).lower()
                if concept_lower in domain_lower:
                    domains.append(domain)
                    break
        return domains
