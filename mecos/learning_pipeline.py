"""
MECOS Learning Pipeline
========================
Orchestrates the full knowledge ingestion cycle:

  Search -> Extract Triplets -> Store in Graph + Vector DB
"""

import argparse
import hashlib
import logging
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).parent))
    from free_search import free_search
    from knowledge_core import KnowledgeGraph
    from relationship_extractor import extract_entities, extract_triplets
    from vector_store import VectorStore
else:
    from .free_search import free_search
    from .knowledge_core import KnowledgeGraph
    from .relationship_extractor import extract_entities, extract_triplets
    from .vector_store import VectorStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mecos.pipeline")


class LearningPipeline:
    """
    End-to-end pipeline:
    1. Search a topic using free sources (Wikipedia + DuckDuckGo)
    2. Extract (subject, predicate, object) triplets from results
    3. Store triplets in the Knowledge Graph
    4. Store full text in the Vector Store for semantic search
    """

    def __init__(self):
        self.graph = KnowledgeGraph()
        self.vectors = VectorStore()

    def learn(self, topic: str, max_results: int = 8) -> dict:
        """Run a full learning cycle for a topic."""
        logger.info("=== Learning about: %s ===", topic)

        results = free_search(topic, max_total=max_results)
        if not results:
            logger.warning("No results found for '%s'", topic)
            return {"topic": topic, "results": 0, "triplets": 0}

        total_triplets = 0
        for result in results:
            if not result.snippet:
                continue

            text = f"{result.title}. {result.snippet}"

            triplets = extract_triplets(text)
            self.graph.add_triplets(triplets, source=result.url)
            total_triplets += len(triplets)

            doc_id = hashlib.md5(result.url.encode()).hexdigest()[:12]
            self.vectors.add(
                doc_id=doc_id,
                text=text,
                metadata={"title": result.title, "url": result.url, "source": result.source, "topic": topic},
            )

            entities = extract_entities(text)
            for ent in entities:
                self.graph.add_triplet(
                    subject=topic,
                    predicate="MENTIONS",
                    obj=ent["text"],
                    source=result.url,
                )

        self.graph.save()
        logger.info("Learned '%s': %d sources, %d triplets added", topic, len(results), total_triplets)
        return {"topic": topic, "results": len(results), "triplets": total_triplets}

    def query_graph(self, concept: str) -> list[dict]:
        """Get all known relationships for a concept."""
        return self.graph.get_relations(concept)

    def query_semantic(self, question: str, top_k: int = 5) -> list[dict]:
        """Find relevant text chunks by semantic similarity."""
        return self.vectors.search(question, top_k=top_k)

    def find_path(self, start: str, end: str) -> list[str] | None:
        """Find the relationship path between two concepts."""
        return self.graph.path_between(start, end)

    def related(self, concept: str, depth: int = 2) -> list[str]:
        """Return concepts connected to this one within N hops."""
        return self.graph.related_concepts(concept, depth=depth)

    def stats(self) -> dict:
        return {
            "knowledge_graph": self.graph.stats(),
            "vector_store": self.vectors.stats(),
        }

    def ingest_email_docs(self, docs) -> dict:
        """Process EmailDocument objects from the email ingester."""
        total_triplets = 0
        for doc in docs:
            text = f"{doc.subject}. {doc.body}"
            triplets = extract_triplets(text)
            self.graph.add_triplets(triplets, source=f"email:{doc.sender}")
            total_triplets += len(triplets)

            doc_id = hashlib.md5(doc.uid.encode()).hexdigest()[:12]
            self.vectors.add(
                doc_id=doc_id,
                text=text[:2000],
                metadata={"subject": doc.subject, "from": doc.sender, "date": doc.date},
            )

            for attach_text in doc.attachments:
                if attach_text:
                    attach_triplets = extract_triplets(attach_text)
                    self.graph.add_triplets(attach_triplets, source=f"email:{doc.sender}:attachment")
                    total_triplets += len(attach_triplets)

        self.graph.save()
        return {"emails_processed": len(docs), "triplets": total_triplets}


def main():
    parser = argparse.ArgumentParser(description="MECOS Learning Pipeline")
    sub = parser.add_subparsers(dest="cmd")

    learn_parser = sub.add_parser("learn", help="Learn about a topic")
    learn_parser.add_argument("topic", nargs="+")

    query_parser = sub.add_parser("query", help="Query the knowledge graph")
    query_parser.add_argument("concept")

    sem_parser = sub.add_parser("semantic", help="Semantic search")
    sem_parser.add_argument("question", nargs="+")

    path_parser = sub.add_parser("path", help="Find path between two concepts")
    path_parser.add_argument("start")
    path_parser.add_argument("end")

    related_parser = sub.add_parser("related", help="Find related concepts")
    related_parser.add_argument("concept")
    related_parser.add_argument("--depth", type=int, default=2)

    sub.add_parser("stats", help="Show system statistics")
    sub.add_parser("email", help="Ingest emails from IMAP inbox")

    args = parser.parse_args()
    pipeline = LearningPipeline()

    if args.cmd == "learn":
        topic = " ".join(args.topic)
        result = pipeline.learn(topic)
        print(f"\nLearned '{topic}': {result['results']} sources, {result['triplets']} triplets")

    elif args.cmd == "query":
        relations = pipeline.query_graph(args.concept)
        if not relations:
            print(f"No relations found for '{args.concept}'")
        else:
            print(f"\nRelations for '{args.concept}':")
            for relation in relations:
                print(f"  [{relation['subject']}] --({relation['predicate']})--> [{relation['object']}]")

    elif args.cmd == "semantic":
        question = " ".join(args.question)
        results = pipeline.query_semantic(question)
        if not results:
            print("No results. Try running 'learn' on some topics first.")
        else:
            print(f"\nSemantic results for '{question}':")
            for index, result in enumerate(results, 1):
                print(f"\n  [{index}] Score: {result['score']:.2f} | {result['metadata'].get('title', '')}")
                print(f"      {result['text'][:200]}...")

    elif args.cmd == "path":
        path = pipeline.find_path(args.start, args.end)
        if path:
            print(f"\nPath from '{args.start}' to '{args.end}':")
            print("  " + " -> ".join(path))
        else:
            print(f"No path found between '{args.start}' and '{args.end}'")

    elif args.cmd == "related":
        related = pipeline.related(args.concept, depth=args.depth)
        if related:
            print(f"\nConcepts related to '{args.concept}' (depth={args.depth}):")
            for concept in sorted(related)[:30]:
                print(f"  - {concept}")
        else:
            print(f"No related concepts found for '{args.concept}'")

    elif args.cmd == "stats":
        stats = pipeline.stats()
        print("\nMECOS Knowledge Stats:")
        print(f"  Graph nodes : {stats['knowledge_graph']['nodes']}")
        print(f"  Graph edges : {stats['knowledge_graph']['edges']}")
        print(f"  Graph file  : {stats['knowledge_graph']['graph_file']}")
        print(f"  Vector docs : {stats['vector_store']['documents']}")
        print(f"  Vector dir  : {stats['vector_store']['persist_dir']}")

    elif args.cmd == "email":
        if __package__ in (None, ""):
            from email_ingester import EmailIngester
        else:
            from .email_ingester import EmailIngester

        ingester = EmailIngester()
        docs = ingester.fetch_unread()
        result = pipeline.ingest_email_docs(docs)
        print(f"\nProcessed {result['emails_processed']} emails, {result['triplets']} triplets extracted")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
