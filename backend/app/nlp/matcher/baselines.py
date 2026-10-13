"""Research baselines: keyword / TF-IDF / semantic vs proposed requirement-aware matching.

Documented decision thresholds (also shown in the Research dashboard):
  keyword  >= 0.50 token overlap  -> FULLY_SATISFIED else MISSING
  tfidf    >= 0.30 cosine          -> FULLY_SATISFIED else MISSING
  semantic >= 0.62 cosine (or >= 0.30 when falling back to TF-IDF) else MISSING
These are fixed, standard cutoffs — not tuned per dataset — so all figures are
comparable and reproducible. See docs/RESEARCH.md.
"""
from __future__ import annotations
import re
from app.nlp.embeddings.similarity import tfidf_similarity, st_similarity


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9+#]+", s.lower()))


def baseline_keyword(requirement: str, resume_text: str) -> dict:
    rt, ct = _tokens(requirement), _tokens(resume_text)
    overlap = rt & ct
    score = len(overlap) / max(1, len(rt))
    return {"method": "keyword", "score": round(score, 3),
            "predicted": "FULLY_SATISFIED" if score >= 0.5 else "MISSING"}


def baseline_tfidf(requirement: str, resume_text: str) -> dict:
    s = tfidf_similarity(requirement, resume_text[:4000])
    return {"method": "tfidf", "score": round(s, 3),
            "predicted": "FULLY_SATISFIED" if s >= 0.3 else "MISSING"}


def baseline_semantic(requirement: str, resume_text: str) -> dict:
    s = st_similarity(requirement, resume_text[:4000])
    if s is None:
        s = tfidf_similarity(requirement, resume_text[:4000])
        method, cutoff = "tfidf-fallback", 0.30
    else:
        method, cutoff = "sentence-transformers", 0.62
    return {"method": method, "score": round(float(s), 3),
            "predicted": "FULLY_SATISFIED" if float(s) >= cutoff else "MISSING"}


def evaluate_cases(cases: list[dict], proposed_fn) -> dict:
    """Compute accuracy/precision/recall/F1 + false-positive rate per method. Only from calculated results."""
    from collections import Counter
    methods = ["keyword", "tfidf", "semantic", "proposed"]
    results: dict = {}
    for m in methods:
        y_true, y_pred = [], []
        for c in cases:
            exp = c["expected_status"]
            true_pos = exp in ("FULLY_SATISFIED", "PARTIALLY_SATISFIED")
            y_true.append(true_pos)
            if m == "keyword":
                p = baseline_keyword(c["requirement_text"], c["resume_text"])["predicted"]
            elif m == "tfidf":
                p = baseline_tfidf(c["requirement_text"], c["resume_text"])["predicted"]
            elif m == "semantic":
                p = baseline_semantic(c["requirement_text"], c["resume_text"])["predicted"]
            else:
                p = proposed_fn(c)["status"]
            y_pred.append(p in ("FULLY_SATISFIED", "PARTIALLY_SATISFIED"))
        tp = sum(1 for t, p in zip(y_true, y_pred) if t and p)
        tn = sum(1 for t, p in zip(y_true, y_pred) if not t and not p)
        fp = sum(1 for t, p in zip(y_true, y_pred) if not t and p)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t and not p)
        prec = tp / max(1, tp + fp); rec = tp / max(1, tp + fn)
        acc = (tp + tn) / max(1, len(y_true))
        f1 = 2 * prec * rec / max(1e-9, prec + rec) if (prec + rec) else 0.0
        results[m] = {"accuracy": round(acc, 3), "precision": round(prec, 3),
                      "recall": round(rec, 3), "f1": round(f1, 3),
                      "false_positive_rate": round(fp / max(1, fp + tn), 3),
                      "false_negative_rate": round(fn / max(1, fn + tp), 3),
                      "support": len(y_true), "confusion": {"tp": tp, "tn": tn, "fp": fp, "fn": fn}}
    return results
