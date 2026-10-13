"""Embedding + TF-IDF similarity helpers. Heavy models are lazy/optional (CPU, no GPU required)."""
from __future__ import annotations
from functools import lru_cache

_st_model = None


def get_st_model():
    global _st_model
    if _st_model is not None:
        return _st_model
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        from app.core.config import get_settings

        _st_model = SentenceTransformer(get_settings().EMBEDDING_MODEL, device="cpu")
        return _st_model
    except Exception:
        return None


def st_similarity(a: str, b: str) -> float | None:
    model = get_st_model()
    if model is None:
        return None
    try:
        import numpy as np

        ea, eb = model.encode([a, b], convert_to_numpy=True, show_progress_bar=False)
        denom = (float((ea**2).sum() ** 0.5) * float((eb**2).sum() ** 0.5)) or 1.0
        return float(ea.dot(eb) / denom)
    except Exception:
        return None


def tfidf_similarity(a: str, b: str) -> float:
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
        from sklearn.metrics.pairwise import cosine_similarity  # type: ignore
    except ImportError:
        # token-overlap fallback
        sa, sb = set(a.lower().split()), set(b.lower().split())
        return len(sa & sb) / max(1, len(sa | sb))
    try:
        vec = TfidfVectorizer().fit_transform([a, b])
        return float(cosine_similarity(vec[0], vec[1])[0][0])
    except ValueError:
        return 0.0


def semantic_score(requirement: str, evidence_text: str) -> tuple[float, str]:
    """Return (score, method). Prefers ST when available, else TF-IDF."""
    s = st_similarity(requirement, evidence_text)
    if s is not None:
        return (max(0.0, min(1.0, s)), "sentence-transformers")
    return (tfidf_similarity(requirement, evidence_text), "tfidf")
