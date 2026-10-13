"""Requirement-by-requirement matching engine (deterministic first, semantic second)."""
from __future__ import annotations
from app.nlp.ontology.skills import normalize_skill, transfer_strength, skill_category
from app.nlp.matcher.experience import estimate_skill_years, detect_contradiction
from app.nlp.embeddings.similarity import semantic_score


def _candidate_skill_set(candidate_skills: list[dict]) -> set[str]:
    return {normalize_skill(s.get("fact", "")).lower() for s in candidate_skills}


def _find_direct_evidence(requirement: str, candidate_skills: list[dict]) -> list[dict]:
    req = normalize_skill(requirement).lower()
    return [s for s in candidate_skills if normalize_skill(s.get("fact", "")).lower() == req]


def _find_transferable_evidence(requirement: str, candidate_skills: list[dict], threshold: float = 0.5) -> list[dict]:
    out = []
    for s in candidate_skills:
        rel, strength = transfer_strength(requirement, s.get("fact", ""))
        if rel in ("TRANSFERABLE", "SAME_FAMILY", "RELATED", "SUPERSET", "SUBSET") and strength >= threshold:
            out.append({**s, "relation": rel, "strength": strength})
    return sorted(out, key=lambda x: x.get("strength", 0), reverse=True)


def match_requirement(
    requirement: dict,
    candidate_skills: list[dict],
    experiences: list[dict],
    resume_text: str,
    thresholds: dict | None = None,
) -> dict:
    """Steps: direct -> threshold/dates -> transferable -> contradiction -> status."""
    th = thresholds or {}
    transfer_th = th.get("transferable", 0.55)
    sem_th = th.get("semantic", 0.62)
    norm = normalize_skill(requirement.get("normalized_requirement", ""))
    category = requirement.get("category", "OTHER")
    min_years = requirement.get("minimum_years")

    # EDUCATION branch
    if category in ("EDUCATION", "DEGREE"):
        from app.nlp.extractors.resume import extract_education
        edus = extract_education(resume_text)
        rank = {"PhD": 5, "M.Tech": 4, "Master's": 4, "MBA": 4, "B.Tech": 3, "B.E.": 3, "Bachelor's": 3}
        need = rank.get(norm, 3)
        best = max([rank.get(e.get("degree", ""), 0) for e in edus], default=0)
        if best >= need and best > 0:
            ev = [{"text": f"{e.get('degree','')} {e.get('specialization','')} — {e.get('institution','')}".strip(),
                   "section": "Education", "source": "resume", "confidence": 0.9} for e in edus]
            return _result(requirement, "FULLY_SATISFIED", 0.9, True, False, ev,
                           f"Required {norm} satisfied by candidate education.", None)
        if best > 0:
            ev = [{"text": f"{e.get('degree','')} {e.get('specialization','')}".strip(),
                   "section": "Education", "source": "resume", "confidence": 0.85} for e in edus]
            return _result(requirement, "MISSING", 0.85, False, False, ev,
                           f"Required {norm}; candidate holds lower qualification.", None)
        return _result(requirement, "MISSING", 0.8, False, False, [],
                       f"No evidence of required education ({norm}).", None)

    direct = _find_direct_evidence(norm, candidate_skills)

    # contradiction check first (explicit claim vs timeline)
    contra = detect_contradiction(norm, experiences, resume_text)
    if contra and direct:
        ev = [{"text": s.get("source_text", ""), "section": s.get("source_section", "Other"),
               "source": "resume", "confidence": s.get("confidence", 0.8)} for s in direct]
        return _result(requirement, "CONTRADICTORY", 0.7, True, False, ev, contra["explanation"], None)

    if direct:
        ev = [{"text": s.get("source_text", ""), "section": s.get("source_section", "Other"),
               "source": "resume", "confidence": s.get("confidence", 0.85)} for s in direct]
        if min_years:
            est = estimate_skill_years(norm, experiences, resume_text)
            if est["estimated_years"] is None:
                if est.get("undated_mentions"):
                    return _result(requirement, "INSUFFICIENT_EVIDENCE", 0.55, True, False, ev,
                                   f"Candidate mentions {norm} but no dated employment evidence supports the required {min_years} years.",
                                   None)
                return _result(requirement, "INSUFFICIENT_EVIDENCE", 0.5, True, False, ev,
                               f"Cannot verify {min_years} years of {norm}: insufficient date evidence.", None)
            if est["estimated_years"] >= min_years:
                return _result(requirement, "FULLY_SATISFIED", min(0.96, 0.8 + est["confidence"] * 0.16),
                               True, False, ev,
                               f"Direct {norm} experience demonstrated (~{est['estimated_years']} years vs required {min_years}).",
                               est["estimated_years"])
            return _result(requirement, "PARTIALLY_SATISFIED", 0.8, True, False, ev,
                           f"Candidate demonstrates {norm} but estimated relevant experience is {est['estimated_years']} years against required {min_years} years.",
                           est["estimated_years"])
        # semantic validation that evidence is substantive (guards false positives)
        scores = [semantic_score(norm, s.get("source_text", ""))[0] for s in direct]
        conf = 0.9 if not scores else min(0.95, 0.75 + max(scores) * 0.2)
        return _result(requirement, "FULLY_SATISFIED", round(conf, 3), True, False, ev,
                       f"Direct {norm} experience is demonstrated in professional work.", None)

    # no direct: transferable?
    trans = _find_transferable_evidence(norm, candidate_skills, transfer_th)
    if trans:
        best = trans[0]
        ev = [{"text": t.get("source_text", ""), "section": t.get("source_section", "Other"),
               "source": "resume", "confidence": t.get("confidence", 0.75),
               "relation": t.get("relation"), "strength": t.get("strength")} for t in trans[:3]]
        return _result(requirement, "TRANSFERABLE", round(0.55 + best.get("strength", 0.5) * 0.25, 3),
                       False, True, ev,
                       f"Candidate does not explicitly demonstrate {norm}, but has {best.get('fact')} "
                       f"({best.get('relation','RELATED')} strength {best.get('strength')}), a related "
                       f"{skill_category(norm).lower()} competency. Upskilling likely required.", None)

    # weak semantic fallback -> insufficient, not a silent match
    if resume_text.strip():
        score, _method = semantic_score(requirement.get("raw_text", norm), resume_text[:4000])
        if score >= sem_th:
            snippet = resume_text[:280]
            return _result(requirement, "INSUFFICIENT_EVIDENCE", round(score, 3), False, False,
                           [{"text": snippet, "section": "Other", "source": "resume", "confidence": round(score, 3)}],
                           f"Semantically related content found (score {score:.2f}) but no concrete {norm} evidence. Treated as insufficient, not a match.",
                           None)
    return _result(requirement, "MISSING", 0.85, False, False, [],
                   f"No evidence of {norm} found in resume.", None)


def _result(requirement, status, confidence, direct, transferable, evidence, explanation, estimated_years):
    return {
        "requirement_id": requirement.get("id"),
        "status": status,
        "confidence": round(float(confidence), 3),
        "direct_match": bool(direct),
        "transferable_match": bool(transferable),
        "evidence": evidence,
        "explanation": explanation,
        "estimated_years": estimated_years,
    }
