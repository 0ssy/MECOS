"""
MECOS Domain Generator
=======================
Takes the gap analysis report and generates the next 200 domains.

This is the system that makes MECOS self-expanding.
After every 200-domain cycle, this runs and produces
the next 200 — targeted, intelligent, and prioritised.

No API keys. Runs fully offline using the gap analysis
and a set of domain expansion rules.
"""

import json
import logging
import random
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).parent))
    from domain_graph import DomainGraph
    from gap_analyser import GapAnalyser
else:
    from .domain_graph import DomainGraph
    from .gap_analyser import GapAnalyser

logger = logging.getLogger("mecos.domain_generator")

GENERATED_DOMAINS_FILE = Path("mecos_generated_domains.json")


# ------------------------------------------------------------------ #
#  Domain expansion rules                                              #
#  These rules define HOW to generate new domains from existing ones  #
# ------------------------------------------------------------------ #

EXPANSION_RULES = {
    "go_deeper": [
        "advanced {domain}",
        "{domain} theory",
        "{domain} mathematics",
        "{domain} research methods",
        "computational {domain}",
        "applied {domain}",
        "history of {domain}",
        "philosophy of {domain}",
        "{domain} ethics",
        "{domain} policy",
    ],
    "go_wider": [
        "{domain} and society",
        "{domain} in emerging markets",
        "{domain} applications",
        "{domain} case studies",
        "{domain} future trends",
        "global {domain}",
        "{domain} regulation",
        "{domain} economics",
    ],
    "cross_pollinate": [
        "{domain_a} and {domain_b}",
        "{domain_a} applications in {domain_b}",
        "{domain_b} perspective on {domain_a}",
        "intersection of {domain_a} and {domain_b}",
    ],
    "go_practical": [
        "{domain} tools and frameworks",
        "{domain} best practices",
        "{domain} project management",
        "{domain} career paths",
        "{domain} industry applications",
        "building with {domain}",
        "{domain} business models",
    ],
}


# ------------------------------------------------------------------ #
#  200 additional seed domains for cycle 3+                           #
#  Used when gap analysis alone doesn't fill the 200 slots            #
# ------------------------------------------------------------------ #

CYCLE_3_SEEDS = [
    # Deep mathematics
    "algebraic topology", "differential geometry", "measure theory",
    "functional analysis", "abstract algebra", "combinatorics",
    "stochastic processes", "ergodic theory", "category theory",
    "model theory",

    # Deep computer science
    "type theory", "formal verification", "compiler design",
    "distributed consensus", "byzantine fault tolerance",
    "zero knowledge systems", "homomorphic encryption",
    "neuromorphic computing", "quantum algorithms",
    "program synthesis",

    # Deep finance
    "stochastic calculus finance", "market microstructure",
    "high frequency trading", "volatility modelling",
    "credit risk modelling", "interest rate derivatives",
    "commodity markets structure", "private equity mechanics",
    "hedge fund strategies", "family office management",

    # Deep science
    "systems biology", "proteomics", "metabolomics",
    "epigenetics", "synthetic biology", "structural biology",
    "chemical biology", "astrobiology", "plasma physics",
    "condensed matter physics",

    # Philosophy and reasoning
    "epistemology", "ontology", "philosophy of science",
    "decision theory", "formal epistemology", "bayesian reasoning",
    "argumentation theory", "rhetoric", "semiotics",
    "phenomenology",

    # Law and governance
    "constitutional law", "international law", "contract law",
    "intellectual property law", "securities law",
    "antitrust law", "administrative law", "criminal law",
    "human rights law", "cyber law",

    # Social systems
    "institutional economics", "complex adaptive systems",
    "network science", "agent based modelling",
    "system dynamics", "resilience theory",
    "social choice theory", "collective intelligence",
    "emergence", "self-organization",

    # Engineering depth
    "control theory", "optimal control", "robust control",
    "nonlinear dynamics", "fluid dynamics",
    "computational fluid dynamics", "finite element analysis",
    "structural dynamics", "acoustic engineering",
    "photonics",

    # Practical domains
    "negotiation theory", "conflict resolution",
    "mediation and arbitrage", "executive decision making",
    "organizational behaviour", "change management",
    "innovation management", "technology forecasting",
    "scenario planning", "wargaming and simulation",

    # Emerging technology
    "spatial computing", "extended reality",
    "ambient computing", "edge computing",
    "federated systems", "zero trust security",
    "supply chain digitization", "smart contracts",
    "decentralized autonomous organizations",
    "token economics",

    # Human sciences depth
    "cognitive neuroscience", "social neuroscience",
    "neuromarketing", "psychophysiology",
    "evolutionary psychology", "cultural evolution",
    "memetics", "information ecology",
    "attention economics", "persuasion science",

    # Global systems
    "geopolitics", "grand strategy", "energy geopolitics",
    "food security", "water security", "pandemic preparedness",
    "climate adaptation", "geoengineering",
    "space economics", "asteroid mining",
]

CYCLE_4_SEEDS = [
    # Frontier science
    "topological quantum computing", "quantum error correction",
    "quantum machine learning", "quantum cryptography",
    "photonic computing", "DNA computing",
    "molecular machines", "nanosensors",
    "metamaterials", "programmable matter",

    # Deep AI
    "mechanistic interpretability", "AI consciousness",
    "embodied cognition", "developmental robotics",
    "swarm intelligence", "stigmergy",
    "artificial life", "open ended evolution",
    "curiosity driven learning", "intrinsic motivation",

    # Deep economics
    "complexity economics", "evolutionary game theory",
    "experimental economics", "neuroeconomics",
    "post keynesian economics", "modern monetary theory",
    "degrowth economics", "doughnut economics",
    "natural capital accounting", "ecosystem services valuation",

    # Deep biology
    "xenobiology", "protocell research",
    "systems pharmacology", "precision medicine",
    "longevity science", "geroscience",
    "microbiome research", "virome",
    "horizontal gene transfer", "endosymbiosis",

    # Culture and power
    "hegemony theory", "soft power",
    "propaganda analysis", "information warfare",
    "cognitive warfare", "narrative strategy",
    "cultural diplomacy", "diaspora networks",
    "civilizational theory", "historical cycles",
]


class DomainGenerator:
    """
    Generates the next N domains for MECOS to learn.

    Strategy:
    1. Use gap analysis to fill high-priority slots (reinforcement, bridges, depth)
    2. Use expansion rules to generate new domains from existing ones
    3. Pull from cycle-specific seed lists for genuinely new territory
    4. Deduplicate against already-learned domains
    5. Sequence by learning dependency (fundamentals before advanced)
    """

    def __init__(self, domain_graph: DomainGraph, gap_analyser: GapAnalyser):
        self.dg  = domain_graph
        self.ga  = gap_analyser
        self.generated_history = self._load_history()

    def _load_history(self) -> set:
        if GENERATED_DOMAINS_FILE.exists():
            data = json.loads(GENERATED_DOMAINS_FILE.read_text())
            return set(data.get("all_generated", []))
        return set()

    def _save_history(self, domains: list[str]):
        self.generated_history.update(domains)
        data = {"all_generated": list(self.generated_history)}
        GENERATED_DOMAINS_FILE.write_text(json.dumps(data, indent=2))

    def generate(self, cycle: int, n_domains: int = 200) -> list[dict]:
        """
        Generate the next n_domains for the given cycle.
        Returns a list of domain dicts with name, reason, category, priority.
        """
        logger.info("Generating %d domains for cycle %d...", n_domains, cycle)

        # Step 1: gap-driven domains (highest priority)
        gap_report  = self.ga.full_analysis(completed_cycle=cycle - 1)
        gap_domains = self._from_gap_report(gap_report)

        # Step 2: expansion-rule domains
        expansion_domains = self._from_expansion_rules(cycle)

        # Step 3: seed domains for this cycle
        seed_domains = self._from_seeds(cycle)

        # Step 4: combine, deduplicate, limit to n
        all_candidates = gap_domains + expansion_domains + seed_domains
        final = self._deduplicate_and_select(all_candidates, n_domains)

        # Step 5: sequence by dependency
        sequenced = self._sequence_by_dependency(final, cycle)

        self._save_history([d["name"] for d in sequenced])
        self._save_plan(sequenced, cycle)

        logger.info("Generated %d domains for cycle %d", len(sequenced), cycle)
        return sequenced

    # ------------------------------------------------------------------ #
    #  Generation methods                                                  #
    # ------------------------------------------------------------------ #

    def _from_gap_report(self, gap_report: dict) -> list[dict]:
        domains = []
        for rec in gap_report.get("recommendations", []):
            domains.append({
                "name":     rec["domain"],
                "reason":   rec["reason"],
                "category": rec["type"],
                "priority": rec["priority"],
                "source":   "gap_analysis",
            })
        return domains

    def _from_expansion_rules(self, cycle: int) -> list[dict]:
        """Apply expansion rules to existing hub domains."""
        domains = []
        hubs = self.dg.hub_domains(top_n=30)
        isolated = self.dg.isolated_domains()[:20]

        for hub in hubs:
            # Go deeper into hub domains
            for template in EXPANSION_RULES["go_deeper"][:3]:
                name = template.format(domain=hub)
                domains.append({
                    "name":     name,
                    "reason":   f"Deeper exploration of hub domain: {hub}",
                    "category": "depth",
                    "priority": 3,
                    "source":   "expansion_rule",
                })

        for domain in isolated:
            # Connect isolated domains to others
            for template in EXPANSION_RULES["go_wider"][:2]:
                name = template.format(domain=domain)
                domains.append({
                    "name":     name,
                    "reason":   f"Connecting isolated domain: {domain}",
                    "category": "bridge",
                    "priority": 2,
                    "source":   "expansion_rule",
                })

        # Cross-pollinate hub domains
        hubs_sample = random.sample(hubs, min(10, len(hubs)))
        for i in range(0, len(hubs_sample) - 1, 2):
            a, b = hubs_sample[i], hubs_sample[i + 1]
            for template in EXPANSION_RULES["cross_pollinate"][:2]:
                name = template.format(domain_a=a, domain_b=b)
                domains.append({
                    "name":     name,
                    "reason":   f"Cross-domain: {a} × {b}",
                    "category": "interdisciplinary",
                    "priority": 4,
                    "source":   "cross_pollination",
                })

        return domains

    def _from_seeds(self, cycle: int) -> list[dict]:
        """Pull from cycle-specific seed lists."""
        seeds = []

        if cycle == 2:
            seed_list = CYCLE_3_SEEDS
        elif cycle >= 3:
            seed_list = CYCLE_4_SEEDS + CYCLE_3_SEEDS
        else:
            seed_list = []

        for seed in seed_list:
            seeds.append({
                "name":     seed,
                "reason":   f"Cycle {cycle} frontier domain",
                "category": "frontier",
                "priority": 5,
                "source":   "seed_list",
            })

        return seeds

    def _deduplicate_and_select(self, candidates: list[dict], n: int) -> list[dict]:
        """Remove duplicates and already-learned domains."""
        learned = set(d.lower() for d in self.dg.graph.nodes)
        seen    = set()
        final   = []

        for c in sorted(candidates, key=lambda x: x.get("priority", 9)):
            name_lower = c["name"].lower()

            # Skip if already learned or already in this batch
            if name_lower in learned:
                continue
            if name_lower in seen:
                continue
            if name_lower in self.generated_history:
                continue
            # Skip if too similar to something already selected
            if any(self._similar(name_lower, s) for s in seen):
                continue

            seen.add(name_lower)
            final.append(c)

            if len(final) >= n:
                break

        return final

    def _similar(self, a: str, b: str, threshold: int = 4) -> bool:
        """Simple overlap check to avoid near-duplicate domains."""
        words_a = set(a.split())
        words_b = set(b.split())
        overlap = words_a & words_b
        return len(overlap) >= threshold

    def _sequence_by_dependency(self, domains: list[dict], cycle: int) -> list[dict]:
        """
        Order domains so fundamentals come before advanced topics.
        Simple heuristic: shorter/simpler names first,
        then bridges, then depth, then emerging.
        """
        order = {"reinforcement": 0, "bridge": 1, "depth": 2,
                 "interdisciplinary": 3, "application": 4,
                 "frontier": 5, "emerging": 6, "general": 7}

        return sorted(
            domains,
            key=lambda d: (
                order.get(d.get("category", "general"), 7),
                len(d["name"])
            )
        )

    def _save_plan(self, domains: list[dict], cycle: int):
        """Save the generated domain plan to disk."""
        path = Path(f"mecos_cycle_{cycle}_domains.json")
        path.write_text(json.dumps({
            "cycle":   cycle,
            "n":       len(domains),
            "domains": domains,
        }, indent=2))
        logger.info("Domain plan saved: %s", path)

    def preview(self, cycle: int, n: int = 200) -> None:
        """Print a preview of what would be generated."""
        domains = self.generate(cycle, n)
        print(f"\nCycle {cycle} — {len(domains)} domains generated:\n")
        for i, d in enumerate(domains, 1):
            print(f"  {i:3d}. [{d['category']:20s}] {d['name']}")
            print(f"       → {d['reason'][:80]}")
