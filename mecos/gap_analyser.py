"""
MECOS Gap Analyser
==================
Analyses the domain graph after each cycle to find:
- Missing bridges between domains
- Weak areas needing deeper learning
- Cross-domain opportunities MECOS hasn't explored
- Completely missing categories

This tells the domain generator exactly what to build next.
"""

import logging
import sys
from collections import defaultdict
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).parent))
    from domain_graph import DomainGraph
else:
    from .domain_graph import DomainGraph

logger = logging.getLogger("mecos.gap_analyser")


# Known high-value cross-domain bridges that most curricula miss
KNOWN_BRIDGES = [
    ("neuroscience",          "machine learning"),
    ("game theory",           "trading strategy"),
    ("linguistics",           "natural language processing"),
    ("thermodynamics",        "economics"),
    ("evolutionary biology",  "genetic algorithms"),
    ("psychology",            "marketing"),
    ("graph theory",          "social networks"),
    ("information theory",    "cryptography"),
    ("control systems",       "reinforcement learning"),
    ("epidemiology",          "network theory"),
    ("materials science",     "nanotechnology"),
    ("philosophy of mind",    "artificial intelligence"),
    ("political science",     "game theory"),
    ("ecology",               "economics"),
    ("topology",              "data science"),
    ("military strategy",     "business strategy"),
    ("music theory",          "mathematics"),
    ("architecture",          "systems engineering"),
    ("anthropology",          "consumer behavior"),
    ("quantum mechanics",     "cryptography"),
]


class GapAnalyser:
    """
    Analyses completed learning cycles and identifies what's missing.
    Produces a structured gap report that the domain generator uses
    to build the next 200 domains.
    """

    def __init__(self, domain_graph: DomainGraph):
        self.dg = domain_graph

    def full_analysis(self, completed_cycle: int) -> dict:
        """
        Run the complete gap analysis after a cycle completes.
        Returns a structured report driving next cycle generation.
        """
        logger.info("Running gap analysis after cycle %d...", completed_cycle)

        report = {
            "cycle_analysed":      completed_cycle,
            "weak_domains":        self._find_weak_domains(),
            "isolated_domains":    self._find_isolated_domains(),
            "missing_bridges":     self._find_missing_bridges(),
            "shallow_categories":  self._find_shallow_categories(),
            "unexplored_depths":   self._find_unexplored_depths(),
            "cross_domain_gaps":   self._find_cross_domain_gaps(),
            "emerging_fields":     self._find_emerging_fields(completed_cycle),
            "application_gaps":    self._find_application_gaps(),
            "recommendations":     [],
        }

        # Build prioritised recommendations
        report["recommendations"] = self._prioritise(report)
        logger.info(
            "Gap analysis complete: %d recommendations generated",
            len(report["recommendations"])
        )
        return report

    # ------------------------------------------------------------------ #
    #  Individual gap finders                                              #
    # ------------------------------------------------------------------ #

    def _find_weak_domains(self) -> list[dict]:
        """Domains learned but with low coverage — need revisiting."""
        weak = self.dg.weak_domains(threshold=0.4)
        return [
            {
                "domain":   d,
                "coverage": self.dg.graph.nodes[d].get("coverage", 0),
                "priority": "high" if self.dg.graph.nodes[d].get("coverage", 0) < 0.2 else "medium",
            }
            for d in weak
        ]

    def _find_isolated_domains(self) -> list[str]:
        """Domains with almost no connections to other knowledge."""
        return self.dg.isolated_domains()

    def _find_missing_bridges(self) -> list[dict]:
        """
        High-value cross-domain connections that are missing.
        Combines graph analysis with known important bridges.
        """
        graph_gaps = self.dg.missing_bridges()
        bridges = []

        # Graph-detected gaps
        for a, b, dist in graph_gaps[:20]:
            bridges.append({
                "domain_a": a,
                "domain_b": b,
                "gap_type": "graph_detected",
                "bridge_topic": f"{a} and {b} intersection",
            })

        # Known important bridges not yet in graph
        learned = set(self.dg.graph.nodes)
        for a, b in KNOWN_BRIDGES:
            a_learned = any(a in n.lower() for n in learned)
            b_learned = any(b in n.lower() for n in learned)
            if a_learned and b_learned:
                bridges.append({
                    "domain_a": a,
                    "domain_b": b,
                    "gap_type": "known_bridge",
                    "bridge_topic": f"intersection of {a} and {b}",
                })

        return bridges

    def _find_shallow_categories(self) -> list[dict]:
        """
        Categories where MECOS only knows surface-level topics
        but hasn't gone deep into subtopics.
        """
        category_counts = defaultdict(list)
        for node in self.dg.graph.nodes:
            cat = self.dg.graph.nodes[node].get("category", "general")
            category_counts[cat].append(node)

        shallow = []
        for cat, domains in category_counts.items():
            avg_coverage = sum(
                self.dg.graph.nodes[d].get("coverage", 0) for d in domains
            ) / len(domains)
            if avg_coverage < 0.5 or len(domains) < 5:
                shallow.append({
                    "category":    cat,
                    "n_domains":   len(domains),
                    "avg_coverage": round(avg_coverage, 3),
                    "needs":       "more depth" if avg_coverage < 0.5 else "more breadth",
                })

        return sorted(shallow, key=lambda x: x["avg_coverage"])

    def _find_unexplored_depths(self) -> list[dict]:
        """
        Topics that exist in the graph as general concepts
        but whose subtopics haven't been explored.
        """
        # These broad topics each have 10+ important subtopics
        DEEP_TOPICS = {
            "machine learning": [
                "gradient boosting", "bayesian optimization", "federated learning",
                "meta-learning", "few-shot learning", "self-supervised learning",
                "causal inference", "uncertainty quantification", "model compression",
                "neural architecture search",
            ],
            "economics": [
                "behavioral economics", "mechanism design", "auction theory",
                "information asymmetry", "principal agent problem", "public goods",
                "externalities", "market microstructure", "monetary theory",
                "fiscal policy transmission",
            ],
            "neuroscience": [
                "synaptic plasticity", "neurogenesis", "default mode network",
                "predictive coding", "neural oscillations", "memory consolidation",
                "decision neuroscience", "computational psychiatry",
                "connectomics", "optogenetics",
            ],
            "cryptography": [
                "zero knowledge proofs", "homomorphic encryption",
                "post-quantum cryptography", "secure multiparty computation",
                "Byzantine fault tolerance", "threshold signatures",
                "verifiable random functions", "commitment schemes",
                "lattice-based cryptography", "elliptic curve cryptography",
            ],
            "finance": [
                "market microstructure", "high frequency trading",
                "factor investing", "risk parity", "volatility surface",
                "credit default swaps", "structured products",
                "algorithmic market making", "statistical arbitrage",
                "alternative risk premia",
            ],
        }

        unexplored = []
        learned = set(n.lower() for n in self.dg.graph.nodes)

        for parent, subtopics in DEEP_TOPICS.items():
            if any(parent in n for n in learned):
                missing_subs = [
                    s for s in subtopics
                    if not any(s in n for n in learned)
                ]
                if missing_subs:
                    unexplored.append({
                        "parent_domain":    parent,
                        "missing_subtopics": missing_subs,
                        "depth_score":      len(missing_subs) / len(subtopics),
                    })

        return sorted(unexplored, key=lambda x: -x["depth_score"])

    def _find_cross_domain_gaps(self) -> list[dict]:
        """
        Emerging interdisciplinary fields that sit between
        multiple known domains but haven't been learned yet.
        """
        INTERDISCIPLINARY = [
            {
                "topic":    "computational social science",
                "parents":  ["computer science", "sociology", "economics"],
                "why":      "Understanding mass human behavior through data",
            },
            {
                "topic":    "neuroeconomics",
                "parents":  ["neuroscience", "economics", "psychology"],
                "why":      "How the brain makes financial decisions",
            },
            {
                "topic":    "quantum computing",
                "parents":  ["quantum mechanics", "computer science"],
                "why":      "Next generation computation affecting cryptography and AI",
            },
            {
                "topic":    "synthetic biology",
                "parents":  ["genetics", "engineering", "chemistry"],
                "why":      "Engineering biological systems — massive commercial potential",
            },
            {
                "topic":    "digital twins",
                "parents":  ["systems engineering", "IoT", "simulation"],
                "why":      "Virtual replicas of physical systems for prediction",
            },
            {
                "topic":    "affective computing",
                "parents":  ["psychology", "machine learning", "human computer interaction"],
                "why":      "Systems that understand human emotion",
            },
            {
                "topic":    "econophysics",
                "parents":  ["physics", "economics", "complex systems"],
                "why":      "Applying physics models to financial markets",
            },
            {
                "topic":    "legal technology",
                "parents":  ["law", "computer science", "natural language processing"],
                "why":      "Automating legal reasoning and document analysis",
            },
            {
                "topic":    "computational creativity",
                "parents":  ["artificial intelligence", "cognitive science", "art"],
                "why":      "Understanding and building creative machines",
            },
            {
                "topic":    "climate finance",
                "parents":  ["climate science", "finance", "economics"],
                "why":      "Carbon markets, ESG investing, physical climate risk",
            },
        ]

        learned = set(n.lower() for n in self.dg.graph.nodes)
        gaps = []

        for field in INTERDISCIPLINARY:
            if not any(field["topic"] in n for n in learned):
                parent_coverage = sum(
                    1 for p in field["parents"]
                    if any(p in n for n in learned)
                )
                gaps.append({
                    **field,
                    "parent_coverage": f"{parent_coverage}/{len(field['parents'])}",
                    "ready_to_learn":  parent_coverage >= 2,
                })

        return sorted(gaps, key=lambda x: -x["ready_to_learn"])

    def _find_emerging_fields(self, cycle: int) -> list[dict]:
        """
        Fields that are emerging NOW — important for MECOS to stay current.
        Updates based on which cycle we're on (deeper cycles get cutting edge).
        """
        EMERGING = [
            # Technology frontier
            {"topic": "large language model alignment",         "cycle_relevance": 1},
            {"topic": "retrieval augmented generation systems", "cycle_relevance": 1},
            {"topic": "multimodal AI systems",                  "cycle_relevance": 1},
            {"topic": "AI agent frameworks",                    "cycle_relevance": 1},
            {"topic": "neuromorphic computing",                 "cycle_relevance": 2},
            {"topic": "DNA data storage",                       "cycle_relevance": 2},
            {"topic": "brain computer interfaces",              "cycle_relevance": 2},
            {"topic": "autonomous weapons systems",             "cycle_relevance": 3},
            {"topic": "room temperature superconductors",       "cycle_relevance": 3},
            {"topic": "programmable matter",                    "cycle_relevance": 3},
            # Finance frontier
            {"topic": "decentralized finance protocols",        "cycle_relevance": 1},
            {"topic": "tokenization of real world assets",      "cycle_relevance": 1},
            {"topic": "central bank digital currencies",        "cycle_relevance": 1},
            {"topic": "prediction markets",                     "cycle_relevance": 2},
            {"topic": "catastrophe bonds",                      "cycle_relevance": 2},
            # Science frontier
            {"topic": "mRNA therapeutics",                      "cycle_relevance": 1},
            {"topic": "CRISPR gene therapy",                    "cycle_relevance": 1},
            {"topic": "fusion energy",                          "cycle_relevance": 2},
            {"topic": "carbon capture technology",              "cycle_relevance": 2},
            {"topic": "quantum sensing",                        "cycle_relevance": 3},
        ]

        learned = set(n.lower() for n in self.dg.graph.nodes)
        return [
            e for e in EMERGING
            if e["cycle_relevance"] <= cycle
            and not any(e["topic"] in n for n in learned)
        ]

    def _find_application_gaps(self) -> list[dict]:
        """
        MECOS knows theory but might be missing practical applications.
        These are real-world application domains.
        """
        APPLICATIONS = [
            "algorithmic trading strategy development",
            "venture capital deal evaluation",
            "merger and acquisition analysis",
            "real estate investment analysis",
            "intellectual property valuation",
            "startup equity structuring",
            "tax optimization strategies",
            "regulatory compliance frameworks",
            "crisis management decision making",
            "geopolitical risk assessment",
            "supply chain resilience",
            "brand valuation methods",
            "patent landscape analysis",
            "competitive intelligence gathering",
            "technology transfer licensing",
        ]
        learned = set(n.lower() for n in self.dg.graph.nodes)
        return [
            {"topic": a, "type": "application"}
            for a in APPLICATIONS
            if not any(a in n for n in learned)
        ]

    # ------------------------------------------------------------------ #
    #  Prioritisation                                                      #
    # ------------------------------------------------------------------ #

    def _prioritise(self, report: dict) -> list[dict]:
        """
        Turn gap analysis into a prioritised list of
        recommended next domains to learn.
        """
        recommendations = []

        # 1. Weak domains first — reinforce what's shaky
        for d in report["weak_domains"][:10]:
            recommendations.append({
                "domain":   d["domain"] + " advanced",
                "reason":   f"Coverage only {d['coverage']*100:.0f}% — needs reinforcement",
                "priority": 1,
                "type":     "reinforcement",
            })

        # 2. Missing bridges — high value cross-domain
        for b in report["missing_bridges"][:20]:
            recommendations.append({
                "domain":   b["bridge_topic"],
                "reason":   f"Bridge between {b['domain_a']} and {b['domain_b']}",
                "priority": 2,
                "type":     "bridge",
            })

        # 3. Unexplored depths — go deeper
        for u in report["unexplored_depths"]:
            for sub in u["missing_subtopics"][:5]:
                recommendations.append({
                    "domain":   sub,
                    "reason":   f"Deep subtopic of {u['parent_domain']}",
                    "priority": 3,
                    "type":     "depth",
                })

        # 4. Cross-domain gaps — interdisciplinary
        for c in report["cross_domain_gaps"]:
            if c["ready_to_learn"]:
                recommendations.append({
                    "domain":   c["topic"],
                    "reason":   c["why"],
                    "priority": 4,
                    "type":     "interdisciplinary",
                })

        # 5. Emerging fields
        for e in report["emerging_fields"]:
            recommendations.append({
                "domain":   e["topic"],
                "reason":   "Emerging field — cutting edge knowledge",
                "priority": 5,
                "type":     "emerging",
            })

        # 6. Applications
        for a in report["application_gaps"][:20]:
            recommendations.append({
                "domain":   a["topic"],
                "reason":   "Practical application domain",
                "priority": 6,
                "type":     "application",
            })

        return sorted(recommendations, key=lambda x: x["priority"])
