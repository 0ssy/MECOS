"""
MECOS Relationship Extractor
=============================
Extracts (subject, predicate, object) triplets from raw text using spaCy NLP.

No LLM required. No API keys. Runs fully offline.

Dependencies:
    pip install spacy
    python -m spacy download en_core_web_sm
"""

import logging
import re

logger = logging.getLogger(__name__)

_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        try:
            import spacy

            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.error("spaCy model not found. Run: python -m spacy download en_core_web_sm")
            raise
    return _nlp


COPULA_PATTERN = re.compile(
    r"([A-Z][a-zA-Z\s]{1,40})\s+(is|are|was|were|has been)\s+(a|an|the)?\s*([a-zA-Z\s]{2,40})",
    re.IGNORECASE,
)

USES_PATTERN = re.compile(
    r"([A-Z][a-zA-Z\s]{1,40})\s+(uses|uses a|uses an|consists of|includes|requires|relies on|depends on)\s+([a-zA-Z\s]{2,40})",
    re.IGNORECASE,
)


def extract_with_regex(text: str) -> list[tuple]:
    """Fast rule-based extraction. Good for clean, structured text."""
    triplets = []

    for match in COPULA_PATTERN.finditer(text):
        subject = match.group(1).strip()
        predicate = match.group(2).strip().upper().replace(" ", "_")
        obj = match.group(4).strip()
        if len(subject) > 2 and len(obj) > 2:
            triplets.append((subject, predicate, obj))

    for match in USES_PATTERN.finditer(text):
        subject = match.group(1).strip()
        predicate = match.group(2).strip().upper().replace(" ", "_")
        obj = match.group(3).strip()
        if len(subject) > 2 and len(obj) > 2:
            triplets.append((subject, predicate, obj))

    return triplets


def extract_with_spacy(text: str, max_triplets: int = 50) -> list[tuple]:
    """
    NLP-based extraction using spaCy dependency parse.
    Finds (noun_subject, verb, noun_object) patterns.
    """
    try:
        nlp = _get_nlp()
    except Exception:
        return []

    triplets = []
    doc = nlp(text[:10_000])

    for sentence in doc.sents:
        for token in sentence:
            if token.pos_ == "VERB" and token.dep_ not in ("aux", "auxpass"):
                subjects = [
                    word
                    for word in token.lefts
                    if word.dep_ in ("nsubj", "nsubjpass") and word.pos_ in ("NOUN", "PROPN")
                ]
                objects = [
                    word
                    for word in token.rights
                    if word.dep_ in ("dobj", "attr", "pobj", "iobj") and word.pos_ in ("NOUN", "PROPN")
                ]

                for subject in subjects:
                    subject_text = _expand_noun(subject)
                    for obj in objects:
                        object_text = _expand_noun(obj)
                        predicate = token.lemma_.upper().replace(" ", "_")
                        triplets.append((subject_text, predicate, object_text))
                        if len(triplets) >= max_triplets:
                            return triplets

    return triplets


def _expand_noun(token) -> str:
    """Get the full noun phrase for a token (include compound words)."""
    parts = [token.text]
    for child in token.children:
        if child.dep_ == "compound":
            parts.insert(0, child.text)
    return " ".join(parts)


def extract_entities(text: str) -> list[dict]:
    """
    Extract named entities: people, orgs, technologies, locations.
    Returns list of {text, label} dicts.
    """
    try:
        nlp = _get_nlp()
        doc = nlp(text[:10_000])
        seen = set()
        entities = []
        for ent in doc.ents:
            key = (ent.text.lower(), ent.label_)
            if key not in seen:
                seen.add(key)
                entities.append({"text": ent.text, "label": ent.label_})
        return entities
    except Exception as exc:
        logger.warning("Entity extraction failed: %s", exc)
        return []


def extract_triplets(text: str) -> list[tuple]:
    """
    Main entry point. Combines spaCy + regex for best coverage.
    Returns deduplicated list of (subject, predicate, object) tuples.
    """
    spacy_triplets = extract_with_spacy(text)
    regex_triplets = extract_with_regex(text)

    seen = set()
    results = []
    for triplet in spacy_triplets + regex_triplets:
        key = (triplet[0].lower(), triplet[1], triplet[2].lower())
        if key not in seen:
            seen.add(key)
            results.append(triplet)

    logger.debug("Extracted %d triplets from text", len(results))
    return results
