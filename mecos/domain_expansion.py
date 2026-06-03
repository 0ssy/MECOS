"""
MECOS Domain Expansion Controller
===================================
The master controller that runs the infinite learning cycle.

Cycle flow:
  1. Run 200 domains (auto_learn.py handles this)
  2. Detect cycle completion
  3. Run gap analysis on what was learned
  4. Generate next 200 domains from gaps
  5. Build optimised curriculum
  6. Hand off to auto_learn.py for execution
  7. Repeat forever

Run:
    python domain_expansion.py          # start from current state
    python domain_expansion.py --status # see where MECOS is
    python domain_expansion.py --preview 2  # preview cycle 2 domains
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import schedule
except ModuleNotFoundError:
    schedule = None

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).parent))
    from curriculum_engine import CurriculumEngine
    from domain_generator import DomainGenerator
    from domain_graph import DomainGraph
    from domain_connector import SemanticDomainConnector
    from cross_domain_inference import CrossDomainInferenceEngine
    from curiosity_engine import CuriosityEngine
    from gap_analyser import GapAnalyser
    from knowledge_synthesis import KnowledgeSynthesisEngine
    from learning_pipeline import LearningPipeline
    from mastery_scorer import MasteryScorer
else:
    from .curriculum_engine import CurriculumEngine
    from .domain_generator import DomainGenerator
    from .domain_graph import DomainGraph
    from .domain_connector import SemanticDomainConnector
    from .cross_domain_inference import CrossDomainInferenceEngine
    from .curiosity_engine import CuriosityEngine
    from .gap_analyser import GapAnalyser
    from .knowledge_synthesis import KnowledgeSynthesisEngine
    from .learning_pipeline import LearningPipeline
    from .mastery_scorer import MasteryScorer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("mecos_expansion.log"),
    ],
)
logger = logging.getLogger("mecos.expansion")

STATE_FILE = Path("mecos_expansion_state.json")


# ------------------------------------------------------------------ #
#  Cycle 1 seed topics (your original 200)                            #
# ------------------------------------------------------------------ #

CYCLE_1_TOPICS = [
    # Computing & Software
    "Computer Science fundamentals", "Algorithms sorting searching",
    "Data structures trees graphs", "Operating systems Linux Windows",
    "Computer architecture CPU memory", "Software engineering principles",
    "Object-oriented programming", "Functional programming",
    "Software design patterns", "Relational databases",
    "SQL query language", "NoSQL databases MongoDB",
    "Distributed systems architecture", "Computer networking",
    "Internet protocols TCP IP HTTP", "Web development",
    "Frontend development HTML CSS JavaScript",
    "Backend development servers APIs", "Mobile app development",
    "Desktop application development", "Cloud computing AWS Azure",
    "DevOps practices", "CI/CD pipelines", "Docker containerization",
    "Kubernetes orchestration", "API design REST GraphQL",
    "Microservices architecture", "Artificial intelligence",
    "Machine learning algorithms", "Deep learning neural networks",
    "Natural language processing", "Computer vision image recognition",
    "Robotics automation", "Embedded systems programming",
    "Internet of Things IoT", "Blockchain technology",
    "Cryptography encryption", "Cybersecurity network defense",
    "Reverse engineering software", "Digital forensics investigation",
    # Mathematics
    "Arithmetic number operations", "Algebra equations variables",
    "Geometry shapes space", "Trigonometry angles functions",
    "Calculus derivatives integrals", "Linear algebra matrices vectors",
    "Differential equations", "Probability theory",
    "Statistics data analysis", "Discrete mathematics",
    "Number theory prime numbers", "Set theory logic",
    "Graph theory networks", "Mathematical optimization",
    "Game theory strategy", "Mathematical logic proofs",
    "Chaos theory complex systems", "Operations research",
    "Numerical methods computation", "Financial mathematics",
    # Physical Sciences
    "Classical physics mechanics", "Newtonian mechanics motion",
    "Thermodynamics heat energy", "Electromagnetism electricity magnetism",
    "Optics light lenses", "Acoustics sound waves",
    "Quantum mechanics particles", "Theory of relativity Einstein",
    "Nuclear physics fission fusion", "Particle physics standard model",
    "Astronomy stars planets", "Astrophysics galaxies",
    "Cosmology universe origin", "Chemistry elements compounds",
    "Organic chemistry carbon molecules",
    "Inorganic chemistry metals minerals",
    "Physical chemistry thermochemistry",
    "Analytical chemistry measurement", "Biochemistry metabolism",
    "Materials science polymers", "Nanotechnology nanoscale",
    "Earth science geology", "Geology rocks minerals",
    "Meteorology weather forecasting", "Oceanography marine science",
    "Climate science global warming",
    "Environmental science ecosystems",
    "Renewable energy solar wind", "Energy systems power grids",
    "Space science exploration",
    # Life Sciences
    "Biology living organisms", "Cell biology organelles",
    "Genetics DNA heredity", "Evolution natural selection Darwin",
    "Microbiology bacteria viruses", "Immunology immune system",
    "Neuroscience brain nervous system", "Human physiology body systems",
    "Human anatomy organs", "Ecology ecosystems biodiversity",
    "Botany plants photosynthesis", "Zoology animal behavior",
    "Marine biology ocean life", "Biotechnology genetic engineering",
    "Bioinformatics genomics", "Agriculture farming crops",
    "Crop science plant breeding", "Animal science livestock",
    "Food science nutrition processing", "Human nutrition diet health",
    "Epidemiology disease spread", "Public health medicine prevention",
    "Medicine diagnosis treatment", "Pharmacology drugs medicine",
    "Biomedical engineering prosthetics",
    # Engineering
    "Mechanical engineering machines", "Electrical engineering circuits",
    "Electronics engineering components",
    "Civil engineering infrastructure",
    "Structural engineering buildings bridges",
    "Chemical engineering processes",
    "Aerospace engineering aircraft spacecraft",
    "Industrial engineering manufacturing",
    "Systems engineering complexity", "Mechatronics robotics control",
    "Control systems automation", "Signal processing digital analog",
    "Telecommunications wireless networks",
    "Power systems electrical grid", "Automotive engineering vehicles",
    "Railway engineering trains", "Marine engineering ships",
    "Manufacturing engineering production",
    "Quality engineering standards",
    "Reliability engineering failure analysis",
    "Construction engineering projects", "Mining engineering extraction",
    "Petroleum engineering oil gas",
    "Environmental engineering pollution",
    "Engineering economics cost analysis",
    # Business & Economics
    "Economics supply demand", "Microeconomics firms consumers",
    "Macroeconomics GDP inflation", "International trade globalization",
    "Finance investment capital", "Accounting financial statements",
    "Auditing compliance", "Investment analysis valuation",
    "Stock markets equities", "Forex currency trading",
    "Commodities trading gold oil",
    "Cryptocurrency markets Bitcoin Ethereum",
    "Entrepreneurship startups founding",
    "Startup ecosystem venture capital",
    "Business strategy competitive advantage",
    "Marketing brand advertising",
    "Digital marketing SEO social media",
    "Sales negotiation revenue", "Product management roadmap",
    "Operations management efficiency", "Supply chain logistics",
    "Human resource management talent",
    "Project management Agile Scrum",
    "Risk management mitigation", "Business analytics data decisions",
    # Social Sciences
    "Psychology human behavior", "Cognitive science thinking memory",
    "Sociology society culture", "Anthropology human civilization",
    "Political science government power",
    "International relations diplomacy",
    "Public policy governance", "Law legal systems",
    "Ethics moral philosophy",
    "Philosophy epistemology metaphysics",
    "Logic reasoning argument", "Linguistics language grammar",
    "Education pedagogy learning", "History ancient modern",
    "Archaeology ancient civilizations", "Cultural studies identity",
    "Religious studies world religions",
    "Communication studies rhetoric",
    "Journalism media reporting", "Media studies digital culture",
    # Creative & Practical
    "Writing composition storytelling",
    "Technical writing documentation",
    "Public speaking presentation",
    "Graphic design visual communication",
    "UI UX design user experience", "Product design industrial",
    "Photography composition lighting", "Video production filmmaking",
    "Music theory composition", "Game development programming",
    "3D modeling rendering", "Animation motion graphics",
    "Personal finance budgeting investing",
    "Leadership management skills", "Negotiation conflict resolution",
]


# ------------------------------------------------------------------ #
#  State management                                                    #
# ------------------------------------------------------------------ #

class ExpansionState:
    def __init__(self):
        self.data = self._load()

    def _load(self) -> dict:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text())
        return {
            "current_cycle":       1,
            "cycle_start_time":    datetime.utcnow().isoformat(),
            "domains_completed":   0,
            "total_domains_ever":  0,
            "cycles_completed":    0,
            "last_gap_analysis":   None,
            "active_topic_list":   CYCLE_1_TOPICS.copy(),
            "topic_index":         0,
        }

    def save(self):
        STATE_FILE.write_text(json.dumps(self.data, indent=2))

    def mark_domain_complete(self, domain: str, triplets: int):
        self.data["domains_completed"]  += 1
        self.data["total_domains_ever"] += 1
        self.data["topic_index"]        += 1
        self.save()

    def cycle_complete(self) -> bool:
        return self.data["topic_index"] >= len(self.data["active_topic_list"])

    def start_next_cycle(self, new_topics: list[str]):
        self.data["current_cycle"]     += 1
        self.data["cycles_completed"]  += 1
        self.data["domains_completed"]  = 0
        self.data["topic_index"]        = 0
        self.data["active_topic_list"]  = new_topics
        self.data["cycle_start_time"]   = datetime.utcnow().isoformat()
        self.save()
        logger.info(
            "Cycle %d started: %d domains queued",
            self.data["current_cycle"],
            len(new_topics),
        )

    def current_topic(self) -> str | None:
        idx  = self.data["topic_index"]
        lst  = self.data["active_topic_list"]
        return lst[idx] if idx < len(lst) else None


# ------------------------------------------------------------------ #
#  Main expansion controller                                           #
# ------------------------------------------------------------------ #

class DomainExpansionController:
    """
    The master controller for MECOS's infinite learning system.
    Wires together all expansion components.
    """

    def __init__(self):
        self.pipeline   = LearningPipeline()
        self.state      = ExpansionState()
        self.dg         = DomainGraph()
        self.ga         = GapAnalyser(self.dg)
        self.gen        = DomainGenerator(self.dg, self.ga)
        threshold = float(os.getenv("MECOS_DOMAIN_CONNECTOR_THRESHOLD", "0.72"))
        self.connector  = SemanticDomainConnector(threshold=threshold)
        self.inference  = CrossDomainInferenceEngine(self.pipeline.graph, self.dg)
        self.curiosity  = CuriosityEngine(self.pipeline.graph, self.dg)
        self.mastery    = MasteryScorer()
        self.synthesiser = KnowledgeSynthesisEngine()

    # ------------------------------------------------------------------ #
    #  Learning                                                            #
    # ------------------------------------------------------------------ #

    def learn_next(self):
        """Learn the next domain in the current cycle."""

        # Check if cycle just completed
        if self.state.cycle_complete():
            self._complete_cycle()
            return

        topic = self.state.current_topic()
        if not topic:
            return

        logger.info(
            "[Cycle %d | %d/%d] Learning: %s",
            self.state.data["current_cycle"],
            self.state.data["topic_index"] + 1,
            len(self.state.data["active_topic_list"]),
            topic,
        )

        # Learn via the existing pipeline
        result = self.pipeline.learn(topic)
        triplets = result.get("triplets_list", [])

        # Update domain graph
        self.dg.mark_learned(
            domain=topic,
            triplets=result.get("triplets", 0),
            cycle=self.state.data["current_cycle"],
        )

        # Detect connections to other known domains
        self._detect_connections(topic)
        self.curiosity.scan_after_learning(topic=topic, triplets=triplets)

        self.dg.save()
        self.state.mark_domain_complete(topic, result.get("triplets", 0))

        # Log progress
        self._log_progress()

    # ------------------------------------------------------------------ #
    #  Cycle completion                                                    #
    # ------------------------------------------------------------------ #

    def _complete_cycle(self):
        """Called when all domains in the current cycle are complete."""
        cycle = self.state.data["current_cycle"]
        logger.info("=" * 60)
        logger.info("CYCLE %d COMPLETE", cycle)
        logger.info("Total domains learned: %d", self.state.data["total_domains_ever"])
        logger.info("Knowledge graph: %s", self.dg.stats())
        logger.info("=" * 60)

        # Run gap analysis
        logger.info("Running gap analysis...")
        gap_report = self.ga.full_analysis(completed_cycle=cycle)
        self.state.data["last_gap_analysis"] = datetime.utcnow().isoformat()
        mastery_scores = self.mastery.score_all(self.dg, self.pipeline.graph)
        synthesis_insights = self.synthesiser.synthesise(self.pipeline.graph, self.dg)
        clusters = {}
        try:
            clusters = self.connector.cluster_domains(list(self.dg.graph.nodes), n_clusters=10)
        except Exception as exc:
            logger.warning("Domain clustering skipped: %s", exc)

        # Generate next 200 domains
        logger.info("Generating cycle %d domains...", cycle + 1)
        next_domains = self.gen.generate(cycle=cycle + 1, n_domains=200)

        # Build curriculum
        known = set(self.dg.graph.nodes)
        curriculum = CurriculumEngine(next_domains, known).build_curriculum()

        # Extract ordered topic names
        next_topics = [d["name"] for d in curriculum["ordered_domains"]]

        logger.info(
            "Cycle %d curriculum: %d domains, ~%.1f hours",
            cycle + 1,
            len(next_topics),
            curriculum["total_estimated_hours"],
        )

        # Start next cycle
        self.state.start_next_cycle(next_topics)

        # Save curriculum report
        self._save_cycle_report(
            cycle,
            gap_report,
            curriculum,
            mastery_scores=mastery_scores,
            synthesis_insights=synthesis_insights,
            semantic_clusters=clusters,
        )

    def _detect_connections(self, topic: str):
        """
        After learning a topic, find connections to other
        known domains and add them to the domain graph.
        """
        topic_lower = topic.lower()
        known       = list(self.dg.graph.nodes)
        known_others = [d for d in known if str(d).lower() != topic_lower]

        # Use the knowledge graph to find triplets involving this topic
        kg = self.pipeline.graph
        relations = kg.get_relations(topic_lower)

        for rel in relations[:20]:
            other = rel.get("object") or rel.get("subject")
            if other and other != topic_lower:
                # Check if other is a known domain
                for known_domain in known:
                    if other in known_domain.lower() or known_domain.lower() in other:
                        self.dg.add_connection(
                            topic,
                            known_domain,
                            relation=rel.get("predicate", "RELATED_TO"),
                        )
                        break
        semantic_connections = self.connector.find_connections(topic, known_others)
        for _, other_domain, score in semantic_connections[:20]:
            self.dg.add_connection(
                topic,
                other_domain,
                relation="SEMANTICALLY_RELATED",
                weight=float(score),
            )

    # ------------------------------------------------------------------ #
    #  Logging and reporting                                               #
    # ------------------------------------------------------------------ #

    def _log_progress(self):
        idx   = self.state.data["topic_index"]
        total = len(self.state.data["active_topic_list"])
        pct   = (idx / total * 100) if total else 0
        stats = self.dg.stats()
        logger.info(
            "Progress: %.1f%% (%d/%d) | Graph: %d nodes, %d edges | Coverage: %.1f%%",
            pct, idx, total,
            stats["total_domains"],
            stats["total_connections"],
            stats["coverage_score"] * 100,
        )

    def _save_cycle_report(
        self,
        cycle: int,
        gap_report: dict,
        curriculum: dict,
        mastery_scores: list[dict] | None = None,
        synthesis_insights: list[dict] | None = None,
        semantic_clusters: dict | None = None,
    ):
        path = Path(f"mecos_cycle_{cycle}_report.json")
        path.write_text(json.dumps({
            "cycle":      cycle,
            "completed":  datetime.utcnow().isoformat(),
            "gap_report": gap_report,
            "mastery_top10": (mastery_scores or [])[:10],
            "synthesis_top10": (synthesis_insights or [])[:10],
            "semantic_clusters": semantic_clusters or {},
            "next_curriculum": {
                "total_domains":         curriculum["total_domains"],
                "total_estimated_hours": curriculum["total_estimated_hours"],
                "weekly_batches":        curriculum["weekly_batches"],
            },
        }, indent=2))
        logger.info("Cycle report saved: %s", path)

    # ------------------------------------------------------------------ #
    #  Status                                                              #
    # ------------------------------------------------------------------ #

    def status(self):
        state = self.state.data
        stats = self.dg.stats()
        idx   = state["topic_index"]
        total = len(state["active_topic_list"])

        print("\n" + "=" * 60)
        print("MECOS EXPANSION STATUS")
        print("=" * 60)
        print(f"  Current cycle      : {state['current_cycle']}")
        print(f"  Cycles completed   : {state['cycles_completed']}")
        print(f"  Current progress   : {idx}/{total} ({idx/total*100:.1f}%)" if total else "  No active cycle")
        print(f"  Total learned      : {state['total_domains_ever']} domains")
        print(f"  Graph nodes        : {stats['total_domains']}")
        print(f"  Graph edges        : {stats['total_connections']}")
        print(f"  Coverage score     : {stats['coverage_score']*100:.1f}%")
        print(f"  Weak domains       : {stats['weak_domains']}")
        print(f"  Curiosity queue    : {self.curiosity.queue_size()}")
        print(f"  Hub domains        : {', '.join(stats['hub_domains'][:5])}")
        print(f"  Cycle started      : {state['cycle_start_time']}")
        print(f"  Last gap analysis  : {state.get('last_gap_analysis', 'never')}")
        if idx < total and state["active_topic_list"]:
            print(f"\n  Next topic         : {state['active_topic_list'][idx]}")
        print("=" * 60 + "\n")

    # ------------------------------------------------------------------ #
    #  Run                                                                 #
    # ------------------------------------------------------------------ #

    def run(self, interval_minutes: int = 10):
        """Start the autonomous expansion loop."""
        if schedule is None:
            raise RuntimeError("Missing dependency 'schedule'. Install with: pip install schedule")
        logger.info("MECOS Domain Expansion Controller started.")
        logger.info("Cycle: %d | Interval: %d min", self.state.data["current_cycle"], interval_minutes)

        Path("mecos_expansion.pid").write_text(str(os.getpid()))

        schedule.every(interval_minutes).minutes.do(self.learn_next)
        schedule.every(30).minutes.do(self._log_progress)

        # Learn immediately on start
        self.learn_next()

        while True:
            schedule.run_pending()
            time.sleep(30)


# ------------------------------------------------------------------ #
#  CLI                                                                 #
# ------------------------------------------------------------------ #

def main():
    parser = argparse.ArgumentParser(description="MECOS Domain Expansion Controller")
    parser.add_argument("--interval", type=int, default=10,
                        help="Minutes between topics (default: 10)")
    parser.add_argument("--status",   action="store_true",
                        help="Show current expansion status")
    parser.add_argument("--preview",  type=int, metavar="CYCLE",
                        help="Preview domains for a future cycle")
    parser.add_argument("--fast",     action="store_true",
                        help="1 minute intervals (testing)")
    parser.add_argument("--report",   type=int, metavar="CYCLE",
                        help="Show gap analysis report for a completed cycle")
    args = parser.parse_args()

    controller = DomainExpansionController()

    if args.status:
        controller.status()

    elif args.preview:
        print(f"\nPreviewing cycle {args.preview} domains...\n")
        domains = controller.gen.generate(cycle=args.preview, n_domains=200)
        for i, d in enumerate(domains, 1):
            print(f"  {i:3d}. [{d['category']:20s}] {d['name']}")
            print(f"       Reason: {d['reason'][:70]}")

    elif args.report:
        path = Path(f"mecos_cycle_{args.report}_report.json")
        if path.exists():
            data = json.loads(path.read_text())
            print(json.dumps(data["gap_report"], indent=2))
        else:
            print(f"No report found for cycle {args.report}")

    else:
        interval = 1 if args.fast else args.interval
        controller.run(interval_minutes=interval)


if __name__ == "__main__":
    main()
