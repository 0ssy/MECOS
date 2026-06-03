"""
Semantic domain connection detector for MECOS expansion.
"""

from __future__ import annotations

import logging
import math
import re
from typing import Dict, List, Tuple

import numpy as np

logger = logging.getLogger("mecos.domain_connector")


class SemanticDomainConnector:
    """
    Finds semantically-related domains using sentence embeddings.
    Falls back to a lightweight lexical embedding if the model is unavailable.
    """

    def __init__(self, threshold: float = 0.72, model_name: str = "all-MiniLM-L6-v2", use_embeddings: bool = True):
        self.threshold = float(threshold)
        self.model_name = model_name
        self.use_embeddings = bool(use_embeddings)
        self._model = None
        self._cache: Dict[str, np.ndarray] = {}

    def _ensure_model(self):
        if self._model is not None or not self.use_embeddings:
            return
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
            logger.info("Semantic connector model loaded: %s", self.model_name)
        except Exception as exc:
            logger.warning("SentenceTransformer unavailable, using lexical fallback: %s", exc)
            self.use_embeddings = False
            self._model = None

    def _lexical_embed(self, text: str, dim: int = 384) -> np.ndarray:
        tokens = re.findall(r"[a-z0-9]+", str(text).lower())
        vec = np.zeros(dim, dtype=np.float32)
        if not tokens:
            return vec
        for token in tokens:
            idx = hash(token) % dim
            vec[idx] += 1.0
            if len(token) > 4:
                bi = hash(token[:3] + token[-2:]) % dim
                vec[bi] += 0.5
        norm = float(np.linalg.norm(vec))
        if norm > 0.0:
            vec /= norm
        return vec

    def _embed(self, text: str) -> np.ndarray:
        key = str(text)
        if key in self._cache:
            return self._cache[key]
        self._ensure_model()
        if self._model is not None:
            emb = self._model.encode(key, normalize_embeddings=True)
            vec = np.asarray(emb, dtype=np.float32)
        else:
            vec = self._lexical_embed(key)
        self._cache[key] = vec
        return vec

    def find_connections(self, new_domain: str, known_domains: List[str]) -> List[Tuple[str, str, float]]:
        new_emb = self._embed(new_domain)
        connections: List[Tuple[str, str, float]] = []
        for domain in known_domains:
            if str(domain).strip().lower() == str(new_domain).strip().lower():
                continue
            emb = self._embed(domain)
            score = float(np.dot(new_emb, emb))
            if math.isfinite(score) and score >= self.threshold:
                connections.append((new_domain, domain, round(score, 3)))
        return sorted(connections, key=lambda x: -x[2])

    def cluster_domains(self, domains: List[str], n_clusters: int = 10) -> Dict[int, List[str]]:
        if not domains:
            return {}
        try:
            from sklearn.cluster import KMeans
        except Exception as exc:
            raise RuntimeError("scikit-learn is required for domain clustering") from exc

        embeddings = np.array([self._embed(d) for d in domains], dtype=np.float32)
        k = max(1, min(int(n_clusters), len(domains)))
        model = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = model.fit_predict(embeddings)
        clusters: Dict[int, List[str]] = {}
        for domain, label in zip(domains, labels):
            clusters.setdefault(int(label), []).append(domain)
        return clusters
