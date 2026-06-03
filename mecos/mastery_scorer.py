"""
Domain mastery scoring across breadth/depth/connectivity/recency/application.
"""

from __future__ import annotations

from datetime import datetime


class MasteryScorer:
    def score(self, domain: str, kg, dg) -> dict:
        domain_lower = str(domain).lower()

        related = kg.related_concepts(domain_lower, depth=1)
        breadth = min(1.0, len(related) / 20.0)

        deep_related = kg.related_concepts(domain_lower, depth=3)
        depth = min(1.0, len(deep_related) / 100.0)

        connections = dg.graph.degree(domain) if domain in dg.graph else 0
        connectivity = min(1.0, float(connections) / 10.0)

        node_data = dg.graph.nodes.get(domain, {})
        added_str = node_data.get("added", "")
        recency = 0.5
        if added_str:
            try:
                added = datetime.fromisoformat(added_str)
                age_days = (datetime.utcnow() - added).days
                recency = max(0.0, 1.0 - age_days / 30.0)
            except Exception:
                recency = 0.5

        application = float(node_data.get("application_score", 0.0) or 0.0)
        composite = breadth * 0.25 + depth * 0.25 + connectivity * 0.20 + recency * 0.15 + application * 0.15
        return {
            "domain": domain,
            "composite": round(composite, 3),
            "breadth": round(breadth, 3),
            "depth": round(depth, 3),
            "connectivity": round(connectivity, 3),
            "recency": round(recency, 3),
            "application": round(application, 3),
            "grade": self._grade(composite),
        }

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 0.85:
            return "mastered"
        if score >= 0.70:
            return "proficient"
        if score >= 0.50:
            return "developing"
        if score >= 0.30:
            return "basic"
        return "surface"

    def score_all(self, dg, kg) -> list[dict]:
        scores = [self.score(domain, kg, dg) for domain in dg.graph.nodes]
        return sorted(scores, key=lambda x: -x["composite"])
