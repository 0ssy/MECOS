from pathlib import Path

from mecos.cross_domain_inference import CrossDomainInferenceEngine
from mecos.curiosity_engine import CuriosityEngine
from mecos.domain_connector import SemanticDomainConnector
from mecos.domain_graph import DomainGraph
from mecos.knowledge_core import KnowledgeGraph
from mecos.knowledge_synthesis import KnowledgeSynthesisEngine
from mecos.mastery_scorer import MasteryScorer


def _build_graphs(tmp_path: Path):
    kg = KnowledgeGraph(graph_path=tmp_path / "kg_test.gml")
    kg.add_triplet("economics", "CAUSES", "scarcity")
    kg.add_triplet("scarcity", "ENABLES", "loss aversion")
    kg.add_triplet("psychology", "CAUSES", "loss aversion")
    kg.add_triplet("neuroscience", "CAUSES", "dopamine response")
    kg.save()

    dg = DomainGraph(path=tmp_path / "domain_graph_test.json")
    dg.mark_learned("economics", triplets=30, cycle=1, category="social_science")
    dg.mark_learned("psychology", triplets=35, cycle=1, category="social_science")
    dg.mark_learned("neuroscience", triplets=28, cycle=1, category="science")
    dg.add_connection("economics", "psychology", relation="RELATED_TO", weight=0.9)
    dg.add_connection("psychology", "neuroscience", relation="RELATED_TO", weight=0.9)
    dg.save()
    return kg, dg


def test_semantic_domain_connector_fallback():
    connector = SemanticDomainConnector(threshold=0.05, use_embeddings=False)
    out = connector.find_connections(
        "game theory",
        ["auction design", "evolutionary game theory", "botany"],
    )
    assert any(pair[1] == "evolutionary game theory" for pair in out)


def test_cross_domain_inference_and_mastery(tmp_path: Path):
    kg, dg = _build_graphs(tmp_path)
    engine = CrossDomainInferenceEngine(kg, dg)
    query = engine.cross_domain_query("scarcity", max_hops=3)
    assert query["concept"] == "scarcity"
    assert isinstance(query["domains_touched"], list)

    scorer = MasteryScorer()
    scores = scorer.score_all(dg, kg)
    assert len(scores) >= 1
    assert "composite" in scores[0]


def test_curiosity_and_synthesis(tmp_path: Path):
    kg, dg = _build_graphs(tmp_path)
    curiosity = CuriosityEngine(kg, dg, queue_file=tmp_path / "curiosity_queue.json")
    curiosity.scan_after_learning(
        topic="quantum mechanics",
        triplets=[
            ("quantum mechanics", "USES", "bell inequalities"),
            ("entanglement", "CAUSES", "correlation"),
        ],
    )
    assert curiosity.queue_size() >= 1
    assert curiosity.next_curiosity() is not None

    synthesis = KnowledgeSynthesisEngine()
    insights = synthesis.synthesise(kg, dg)
    assert isinstance(insights, list)
