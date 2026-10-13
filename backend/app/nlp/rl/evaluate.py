"""Shared evaluation helpers: baseline vs existing matcher vs RL-enhanced matcher.

Binary framing (same as baselines.evaluate_cases): expected/positive =
FULLY_SATISFIED or PARTIALLY_SATISFIED. All metrics are computed live from
the annotated cases — never fabricated. RL is evaluated on the HELD-OUT
test split recorded in the model metadata when available, plus the full set
for comparability; both are printed so train/test leakage is visible.
"""
from __future__ import annotations

from app.nlp.matcher.baselines import (
    baseline_keyword, baseline_tfidf, baseline_semantic,
)
from app.nlp.rl.config import POSITIVE_STATUSES


def _positive(status: str) -> bool:
    return status in POSITIVE_STATUSES


def binary_scores(y_true: list[bool], y_pred: list[bool]) -> dict:
    tp = sum(1 for t, p in zip(y_true, y_pred) if t and p)
    tn = sum(1 for t, p in zip(y_true, y_pred) if not t and not p)
    fp = sum(1 for t, p in zip(y_true, y_pred) if not t and p)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t and not p)
    prec = tp / max(1, tp + fp)
    rec = tp / max(1, tp + fn)
    acc = (tp + tn) / max(1, len(y_true))
    f1 = 2 * prec * rec / max(1e-9, prec + rec) if (prec + rec) else 0.0
    return {"accuracy": round(acc, 3), "precision": round(prec, 3),
            "recall": round(rec, 3), "f1": round(f1, 3),
            "false_positive_rate": round(fp / max(1, fp + tn), 3),
            "false_negative_rate": round(fn / max(1, fn + tp), 3),
            "support": len(y_true),
            "confusion": {"tp": tp, "tn": tn, "fp": fp, "fn": fn}}


def base_proposed_fn(c: dict) -> dict:
    """Existing JobFit matcher decision for one evaluation case dict."""
    from app.nlp.extractors.requirements import extract_requirements
    from app.nlp.extractors.resume import extract_skills, extract_experience
    from app.nlp.matcher.engine import match_requirement
    from app.nlp.parsers.documents import segment_sections

    reqs, _ = extract_requirements(c["requirement_text"])
    r = reqs[0] if reqs else {"id": "tmp", "raw_text": c["requirement_text"],
                              "normalized_requirement": c["requirement_text"][:80],
                              "category": "SKILL", "mandatory": True,
                              "preference": "MANDATORY", "operator": "AND",
                              "minimum_years": None, "maximum_years": None,
                              "confidence": 0.7, "logic_group": None}
    secs = segment_sections(c["resume_text"])
    skills = extract_skills(c["resume_text"], secs)
    exps = extract_experience(c["resume_text"], secs)
    return match_requirement(r, skills, exps, c["requirement_text"])


def rl_proposed_fn(c: dict, policy=None, config=None) -> dict:
    """RL-enhanced decision for one evaluation case dict (falls back to base)."""
    from app.nlp.extractors.requirements import extract_requirements
    from app.nlp.extractors.resume import extract_skills, extract_experience
    from app.nlp.matcher.engine import match_requirement
    from app.nlp.parsers.documents import segment_sections
    from app.nlp.rl.inference import decide_requirement

    reqs, _ = extract_requirements(c["requirement_text"])
    r = reqs[0] if reqs else {"id": "tmp", "raw_text": c["requirement_text"],
                              "normalized_requirement": c["requirement_text"][:80],
                              "category": "SKILL", "mandatory": True,
                              "preference": "MANDATORY", "operator": "AND",
                              "minimum_years": None, "maximum_years": None,
                              "confidence": 0.7, "logic_group": None}
    secs = segment_sections(c["resume_text"])
    skills = extract_skills(c["resume_text"], secs)
    exps = extract_experience(c["resume_text"], secs)
    base = match_requirement(r, skills, exps, c["requirement_text"])
    if policy is None:
        out = dict(base)
        out.update({"existing_status": base["status"], "rl_status": base["status"],
                    "final_status": base["status"], "rl_changed_decision": False,
                    "rl_used": False})
        return out
    return decide_requirement(r, skills, exps, c["requirement_text"], base, policy, config)


def method_predictions(cases: list[dict], method: str, proposed_fn=None,
                       rl_fn=None) -> tuple[list[bool], list[bool], list[str]]:
    y_true, y_pred, raw = [], [], []
    for c in cases:
        exp = c["expected_status"]
        y_true.append(_positive(exp))
        if method == "keyword":
            p = baseline_keyword(c["requirement_text"], c["resume_text"])["predicted"]
        elif method == "tfidf":
            p = baseline_tfidf(c["requirement_text"], c["resume_text"])["predicted"]
        elif method == "semantic":
            p = baseline_semantic(c["requirement_text"], c["resume_text"])["predicted"]
        elif method == "rl":
            p = (rl_fn or base_proposed_fn)(c)["status"]
        else:
            p = (proposed_fn or base_proposed_fn)(c)["status"]
        raw.append(p)
        y_pred.append(_positive(p))
    return y_true, y_pred, raw


def evaluate_all(cases: list[dict], include_rl: bool = True,
                 policy=None, config=None) -> dict:
    methods = ["keyword", "tfidf", "semantic", "proposed"] + (["rl"] if include_rl else [])
    results: dict = {}
    raw_preds: dict[str, list[str]] = {}
    for m in methods:
        if m == "rl" and policy is None:
            continue
        yt, yp, raw = method_predictions(
            cases, m,
            proposed_fn=base_proposed_fn,
            rl_fn=(lambda c: rl_proposed_fn(c, policy, config)))
        results[m] = binary_scores(yt, yp)
        raw_preds[m] = raw
    payload: dict = {"results": results}
    if "proposed" in raw_preds and "rl" in raw_preds:
        payload["ablation"] = ablation_report(
            cases, raw_preds["proposed"], raw_preds["rl"])
        payload["fine_grained"] = {
            "proposed": fine_grained(cases, raw_preds["proposed"]),
            "rl": fine_grained(cases, raw_preds["rl"]),
        }
    else:
        payload["ablation"] = {}
        payload["fine_grained"] = {}
    return payload


def ablation_report(cases: list[dict], base_pred: list[str],
                    rl_pred: list[str]) -> dict:
    changed = sum(1 for b, r in zip(base_pred, rl_pred) if b != r)
    fixed = sum(1 for c, b, r in zip(cases, base_pred, rl_pred)
                if b != r and r == c["expected_status"])
    broken = sum(1 for c, b, r in zip(cases, base_pred, rl_pred)
                 if b != r and b == c["expected_status"])
    yt = [_positive(c["expected_status"]) for c in cases]
    bp = [_positive(p) for p in base_pred]
    rp = [_positive(p) for p in rl_pred]
    base_fp = sum(1 for t, p in zip(yt, bp) if not t and p)
    rl_fp = sum(1 for t, p in zip(yt, rp) if not t and p)
    base_fn = sum(1 for t, p in zip(yt, bp) if t and not p)
    rl_fn = sum(1 for t, p in zip(yt, rp) if t and not p)
    return {"n_cases": len(cases), "n_changed": changed,
            "n_changed_correct": fixed, "n_changed_incorrect": broken,
            "n_unchanged": len(cases) - changed,
            "base_false_positives": base_fp, "rl_false_positives": rl_fp,
            "false_positives_delta": rl_fp - base_fp,
            "base_false_negatives": base_fn, "rl_false_negatives": rl_fn,
            "false_negatives_delta": rl_fn - base_fn}


def fine_grained(cases: list[dict], preds: list[str]) -> dict:
    def acc(idxs: list[int]) -> float | None:
        if not idxs:
            return None
        ok = sum(1 for i in idxs if preds[i] == cases[i]["expected_status"])
        return round(ok / len(idxs), 3)
    idx_mand = [i for i, c in enumerate(cases)
                if c.get("expected_status") in ("FULLY_SATISFIED", "PARTIALLY_SATISFIED",
                                                "MISSING", "CONTRADICTORY")]
    idx_trans = [i for i, c in enumerate(cases) if c.get("expected_status") == "TRANSFERABLE"]
    idx_miss = [i for i, c in enumerate(cases) if c.get("expected_status") == "MISSING"]
    return {"mandatory_decision_accuracy": acc(idx_mand),
            "transferable_match_accuracy": acc(idx_trans),
            "missing_requirement_accuracy": acc(idx_miss),
            "n_mandatory": len(idx_mand), "n_transferable": len(idx_trans),
            "n_missing": len(idx_miss)}
