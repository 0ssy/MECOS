"""
MECOS Autonomous Learner
=========================
Runs continuously, learning from 200 topics across all knowledge domains.
No topics need to be specified manually — it cycles through them all.

Run:
    python auto_learn.py

Background (Linux/Mac):
    nohup python auto_learn.py > mecos_learn.log 2>&1 &

Stop it:
    kill $(cat mecos.pid)

Dependencies:
    pip install schedule
"""

import logging
import os
import random
import sys
import time
from pathlib import Path

import schedule

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).parent))
    from learning_pipeline import LearningPipeline
else:
    from .learning_pipeline import LearningPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("mecos_learn.log"),
    ],
)
logger = logging.getLogger("mecos.auto")

# ------------------------------------------------------------------ #
#  200 Knowledge Domains                                              #
# ------------------------------------------------------------------ #

TOPICS = [
    # Computing & Software (1-40)
    "Computer Science fundamentals",
    "Algorithms sorting searching",
    "Data structures trees graphs",
    "Operating systems Linux Windows",
    "Computer architecture CPU memory",
    "Software engineering principles",
    "Object-oriented programming",
    "Functional programming",
    "Software design patterns",
    "Relational databases",
    "SQL query language",
    "NoSQL databases MongoDB",
    "Distributed systems architecture",
    "Computer networking",
    "Internet protocols TCP IP HTTP",
    "Web development",
    "Frontend development HTML CSS JavaScript",
    "Backend development servers APIs",
    "Mobile app development",
    "Desktop application development",
    "Cloud computing AWS Azure",
    "DevOps practices",
    "CI/CD pipelines",
    "Docker containerization",
    "Kubernetes orchestration",
    "API design REST GraphQL",
    "Microservices architecture",
    "Artificial intelligence",
    "Machine learning algorithms",
    "Deep learning neural networks",
    "Natural language processing",
    "Computer vision image recognition",
    "Robotics automation",
    "Embedded systems programming",
    "Internet of Things IoT",
    "Blockchain technology",
    "Cryptography encryption",
    "Cybersecurity network defense",
    "Reverse engineering software",
    "Digital forensics investigation",

    # Mathematics (41-60)
    "Arithmetic number operations",
    "Algebra equations variables",
    "Geometry shapes space",
    "Trigonometry angles functions",
    "Calculus derivatives integrals",
    "Linear algebra matrices vectors",
    "Differential equations",
    "Probability theory",
    "Statistics data analysis",
    "Discrete mathematics",
    "Number theory prime numbers",
    "Set theory logic",
    "Graph theory networks",
    "Mathematical optimization",
    "Game theory strategy",
    "Mathematical logic proofs",
    "Chaos theory complex systems",
    "Operations research",
    "Numerical methods computation",
    "Financial mathematics",

    # Physical Sciences (61-90)
    "Classical physics mechanics",
    "Newtonian mechanics motion",
    "Thermodynamics heat energy",
    "Electromagnetism electricity magnetism",
    "Optics light lenses",
    "Acoustics sound waves",
    "Quantum mechanics particles",
    "Theory of relativity Einstein",
    "Nuclear physics fission fusion",
    "Particle physics standard model",
    "Astronomy stars planets",
    "Astrophysics galaxies",
    "Cosmology universe origin",
    "Chemistry elements compounds",
    "Organic chemistry carbon molecules",
    "Inorganic chemistry metals minerals",
    "Physical chemistry thermochemistry",
    "Analytical chemistry measurement",
    "Biochemistry metabolism",
    "Materials science polymers",
    "Nanotechnology nanoscale",
    "Earth science geology",
    "Geology rocks minerals",
    "Meteorology weather forecasting",
    "Oceanography marine science",
    "Climate science global warming",
    "Environmental science ecosystems",
    "Renewable energy solar wind",
    "Energy systems power grids",
    "Space science exploration",

    # Life Sciences (91-115)
    "Biology living organisms",
    "Cell biology organelles",
    "Genetics DNA heredity",
    "Evolution natural selection Darwin",
    "Microbiology bacteria viruses",
    "Immunology immune system",
    "Neuroscience brain nervous system",
    "Human physiology body systems",
    "Human anatomy organs",
    "Ecology ecosystems biodiversity",
    "Botany plants photosynthesis",
    "Zoology animal behavior",
    "Marine biology ocean life",
    "Biotechnology genetic engineering",
    "Bioinformatics genomics",
    "Agriculture farming crops",
    "Crop science plant breeding",
    "Animal science livestock",
    "Food science nutrition processing",
    "Human nutrition diet health",
    "Epidemiology disease spread",
    "Public health medicine prevention",
    "Medicine diagnosis treatment",
    "Pharmacology drugs medicine",
    "Biomedical engineering prosthetics",

    # Engineering (116-140)
    "Mechanical engineering machines",
    "Electrical engineering circuits",
    "Electronics engineering components",
    "Civil engineering infrastructure",
    "Structural engineering buildings bridges",
    "Chemical engineering processes",
    "Aerospace engineering aircraft spacecraft",
    "Industrial engineering manufacturing",
    "Systems engineering complexity",
    "Mechatronics robotics control",
    "Control systems automation",
    "Signal processing digital analog",
    "Telecommunications wireless networks",
    "Power systems electrical grid",
    "Automotive engineering vehicles",
    "Railway engineering trains",
    "Marine engineering ships",
    "Manufacturing engineering production",
    "Quality engineering standards",
    "Reliability engineering failure analysis",
    "Construction engineering projects",
    "Mining engineering extraction",
    "Petroleum engineering oil gas",
    "Environmental engineering pollution",
    "Engineering economics cost analysis",

    # Business & Economics (141-165)
    "Economics supply demand",
    "Microeconomics firms consumers",
    "Macroeconomics GDP inflation",
    "International trade globalization",
    "Finance investment capital",
    "Accounting financial statements",
    "Auditing compliance",
    "Investment analysis valuation",
    "Stock markets equities",
    "Forex currency trading",
    "Commodities trading gold oil",
    "Cryptocurrency markets Bitcoin Ethereum",
    "Entrepreneurship startups founding",
    "Startup ecosystem venture capital",
    "Business strategy competitive advantage",
    "Marketing brand advertising",
    "Digital marketing SEO social media",
    "Sales negotiation revenue",
    "Product management roadmap",
    "Operations management efficiency",
    "Supply chain logistics",
    "Human resource management talent",
    "Project management Agile Scrum",
    "Risk management mitigation",
    "Business analytics data decisions",

    # Social Sciences & Humanities (166-185)
    "Psychology human behavior",
    "Cognitive science thinking memory",
    "Sociology society culture",
    "Anthropology human civilization",
    "Political science government power",
    "International relations diplomacy",
    "Public policy governance",
    "Law legal systems",
    "Ethics moral philosophy",
    "Philosophy epistemology metaphysics",
    "Logic reasoning argument",
    "Linguistics language grammar",
    "Education pedagogy learning",
    "History ancient modern",
    "Archaeology ancient civilizations",
    "Cultural studies identity",
    "Religious studies world religions",
    "Communication studies rhetoric",
    "Journalism media reporting",
    "Media studies digital culture",

    # Creative & Practical Skills (186-200)
    "Writing composition storytelling",
    "Technical writing documentation",
    "Public speaking presentation",
    "Graphic design visual communication",
    "UI UX design user experience",
    "Product design industrial",
    "Photography composition lighting",
    "Video production filmmaking",
    "Music theory composition",
    "Game development programming",
    "3D modeling rendering",
    "Animation motion graphics",
    "Personal finance budgeting investing",
    "Leadership management skills",
    "Negotiation conflict resolution",
]


# ------------------------------------------------------------------ #
#  Autonomous runner                                                   #
# ------------------------------------------------------------------ #

class AutonomousLearner:
    def __init__(self):
        self.pipeline = LearningPipeline()
        self.topic_queue = TOPICS.copy()
        random.shuffle(self.topic_queue)  # randomize order each run
        self.current_index = 0
        self.total_learned = 0

    def learn_next_topic(self):
        """Learn the next topic in the queue. Loops infinitely."""
        if self.current_index >= len(self.topic_queue):
            # Completed a full cycle — shuffle and restart
            self.current_index = 0
            random.shuffle(self.topic_queue)
            logger.info("=== Completed full topic cycle. Starting again with new shuffle. ===")

        topic = self.topic_queue[self.current_index]
        self.current_index += 1

        try:
            result = self.pipeline.learn(topic)
            self.total_learned += 1
            stats = self.pipeline.stats()
            logger.info(
                "Progress: %d/%d topics | Graph: %d nodes, %d edges | Topic: '%s' → %d triplets",
                self.current_index,
                len(self.topic_queue),
                stats["knowledge_graph"]["nodes"],
                stats["knowledge_graph"]["edges"],
                topic,
                result["triplets"],
            )
        except Exception as exc:
            logger.warning("Failed to learn '%s': %s", topic, exc)

    def check_email(self):
        """Pull emails into the knowledge graph."""
        try:
            if __package__ in (None, ""):
                from email_ingester import EmailIngester
            else:
                from .email_ingester import EmailIngester
            ingester = EmailIngester()
            docs = ingester.fetch_unread(max_emails=10)
            if docs:
                result = self.pipeline.ingest_email_docs(docs)
                logger.info("Email: processed %d emails, %d triplets", result["emails_processed"], result["triplets"])
        except Exception as exc:
            logger.warning("Email ingestion failed: %s", exc)

    def print_stats(self):
        stats = self.pipeline.stats()
        logger.info(
            "STATS | Graph: %d nodes / %d edges | Vectors: %d docs | Topics learned: %d",
            stats["knowledge_graph"]["nodes"],
            stats["knowledge_graph"]["edges"],
            stats["vector_store"]["documents"],
            self.total_learned,
        )

    def run(self, learn_interval_minutes: int = 10):
        """
        Start the autonomous learning loop.
        Learns one topic every `learn_interval_minutes` minutes.
        Checks email every hour.
        Prints stats every 30 minutes.
        """
        logger.info("MECOS Autonomous Learner started.")
        logger.info("Topics loaded: %d", len(self.topic_queue))
        logger.info("Learning interval: every %d minutes", learn_interval_minutes)

        # Save PID so you can stop it: kill $(cat mecos.pid)
        Path("mecos.pid").write_text(str(os.getpid()))

        # Schedule tasks
        schedule.every(learn_interval_minutes).minutes.do(self.learn_next_topic)
        schedule.every(1).hours.do(self.check_email)
        schedule.every(30).minutes.do(self.print_stats)

        # Learn first topic immediately on startup
        self.learn_next_topic()

        while True:
            schedule.run_pending()
            time.sleep(30)


# ------------------------------------------------------------------ #
#  Entry point                                                         #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MECOS Autonomous Learner")
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Minutes between each topic (default: 10)",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Learn every 1 minute (for testing)",
    )
    args = parser.parse_args()

    interval = 1 if args.fast else args.interval
    learner = AutonomousLearner()
    learner.run(learn_interval_minutes=interval)
