"""RL state construction from existing pipeline features.

Every feature is derived from data the current pipeline already produces —
no invented information. Numerical features are normalized to [0, 1]
(except exp_gap, which is in [-1, 1] by construction) so a lightweight
linear policy can consume them directly.

Feature order is fixed and documented here (STATE_FEATURES); the trained
model JSON records the same order so inference can validate compatibility.
"""
from __future__ import annotations


STATE_FEATURES: list[str] = [
    "is_mandatory",       # 0: requirement.get("mandatory") as 0/1
    "has_min_years",      # 1: 1 if minimum_years is set
    "req_years_norm",     # 2: min(minimum_years or 0 / 10, 1)
    "has_direct",         # 3: 1 if normalized direct skill evidence exists
    "has_transfer",       # 4: 1 if ontology transferable evidence >= threshold
    "transfer_max",       # 5: max transfer strength in [0,1], else 0
    "semantic",           # 6: semantic_score(raw_text, resume_text) in [0,1]
    "est_years_norm",     # 7: min(estimated_years or 0 / 10, 1); 0 when unverifiable
    "exp_gap",            # 8: clip((est - required) / 10, -1, 1); -req/10 when est None
    "evidence_count",     # 9: min((n_direct + n_transfer) / 3, 1)
    "evidence_conf",      # 10: mean confidence of direct+transfer evidence (0 if none)
    "contradiction",      # 11: 1 if detect_contradiction fires
    "is_education",       # 12: 1 if category in (EDUCATION, DEGREE)
    "edu_satisfied",      # 13: 1 if candidate rank >= required rank (0 otherwise/non-edu)
    "is_or_group",        # 14: 1 if operator == OR or logic_group set
    "base_confidence",    # 15: base matcher confidence in [0,1]
    "base_is_positive",   # 16: 1 if base status in (FULLY, PARTIALLY)
]

STATE_DIM = len(STATE_FEATURES)

_EDU_RANK = {"PhD": 5, "M.Tech": 4, "Master's": 4, "MBA": 4,
             "B.Tech": 3, "B.E.": 3, "Bachelor's": 3}


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def build_state(
    requirement: dict,
    candidate_skills: list[dict],
    experiences: list[dict],
    resume_text: str,
    base_result: dict | None = None,
    transfer_threshold: float = 0.55,
) -> dict:
    """Build the normalized RL state vector plus a debug info dict.

    Returns {"vector": [...], "info": {...}} where info holds unnormalized
    intermediates (counts, raw scores) used by guardrails and explanations.
    """
    from app.nlp.ontology.skills import normalize_skill, transfer_strength
    from app.nlp.matcher.experience import estimate_skill_years, detect_contradiction
    from app.nlp.embeddings.similarity import semantic_score

    norm = normalize_skill(requirement.get("normalized_requirement", ""))
    category = requirement.get("category", "OTHER")
    mandatory = bool(requirement.get("mandatory", True))
    min_years = requirement.get("minimum_years")
    has_min_years = 1.0 if min_years else 0.0
    req_years_norm = _clip(float(min_years or 0.0) / 10.0, 0.0, 1.0)

    req_low = (norm or "").lower()
    direct = [s for s in (candidate_skills or [])
              if normalize_skill(s.get("fact", "")).lower() == req_low]
    has_direct = 1.0 if direct else 0.0

    strengths: list[float] = []
    trans = []
    for s in (candidate_skills or []):
        rel, strength = transfer_strength(norm, s.get("fact", ""))
        if rel in ("TRANSFERABLE", "SAME_FAMILY", "RELATED", "SUPERSET", "SUBSET") \
                and strength >= transfer_threshold:
            trans.append(s)
            strengths.append(float(strength))
    has_transfer = 1.0 if trans else 0.0
    transfer_max = max(strengths) if strengths else 0.0

    try:
        sem, _ = semantic_score(requirement.get("raw_text", norm) or norm,
                                (resume_text or "")[:4000])
    except Exception:
        sem = 0.0
    semantic = _clip(float(sem or 0.0), 0.0, 1.0)

    est_years = None
    est_conf = 0.0
    if min_years or has_direct:
        try:
            est = estimate_skill_years(norm, experiences or [], resume_text or "")
            est_years = est.get("estimated_years")
            est_conf = float(est.get("confidence", 0.0) or 0.0)
        except Exception:
            est_years = None
    est_years_norm = _clip(float(est_years or 0.0) / 10.0, 0.0, 1.0)
    if min_years:
        gap_raw = (float(est_years) - float(min_years)) / 10.0 if est_years is not None \
            else -float(min_years) / 10.0
    else:
        gap_raw = 0.0
    exp_gap = _clip(gap_raw, -1.0, 1.0)

    n_evidence = len(direct) + len(trans)
    evidence_count = _clip(n_evidence / 3.0, 0.0, 1.0)
    confs = [float(s.get("confidence", 0.8) or 0.0) for s in (direct + trans)]
    evidence_conf = sum(confs) / len(confs) if confs else 0.0

    try:
        contra = detect_contradiction(norm, experiences or [], resume_text or "")
    except Exception:
        contra = None
    contradiction = 1.0 if contra else 0.0

    is_education = 1.0 if category in ("EDUCATION", "DEGREE") else 0.0
    edu_satisfied = 0.0
    if is_education:
        try:
            from app.nlp.extractors.resume import extract_education
            edus = extract_education(resume_text or "")
            need = _EDU_RANK.get(norm, 3)
            best = max([_EDU_RANK.get(e.get("degree", ""), 0) for e in edus], default=0)
            edu_satisfied = 1.0 if (best >= need and best > 0) else 0.0
        except Exception:
            edu_satisfied = 0.0

    operator = (requirement.get("operator") or "AND").upper()
    is_or_group = 1.0 if (operator == "OR" or requirement.get("logic_group")) else 0.0

    base_conf = float((base_result or {}).get("confidence", 0.0) or 0.0)
    base_status = (base_result or {}).get("status", "")
    base_is_positive = 1.0 if base_status in ("FULLY_SATISFIED", "PARTIALLY_SATISFIED") else 0.0

    vector = [
        1.0 if mandatory else 0.0,
        has_min_years,
        req_years_norm,
        has_direct,
        has_transfer,
        _clip(transfer_max, 0.0, 1.0),
        semantic,
        est_years_norm,
        exp_gap,
        evidence_count,
        _clip(evidence_conf, 0.0, 1.0),
        contradiction,
        is_education,
        edu_satisfied,
        is_or_group,
        _clip(base_conf, 0.0, 1.0),
        base_is_positive,
    ]
    info = {
        "n_direct": len(direct),
        "n_transfer": len(trans),
        "transfer_max": round(float(transfer_max), 3),
        "semantic": round(float(semantic), 3),
        "estimated_years": est_years,
        "estimated_confidence": round(float(est_conf), 3),
        "has_contradiction": bool(contra),
        "base_status": base_status,
        "base_confidence": round(float(base_conf), 3),
    }
    return {"vector": [round(float(v), 4) for v in vector], "info": info}
