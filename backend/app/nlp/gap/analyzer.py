"""Resume Gap Analysis: derivation layer over requirement-level match results.

Reads the ALREADY-PERSISTED (requirement, match) pairs produced by the
existing pipeline (JD extraction -> resume extraction -> normalization /
ontology -> requirement matching -> optional RL layer) and reorganizes them
into a candidate-facing gap report. It performs NO matching, NO extraction
and NO re-scoring of its own.

Honesty contract (enforced by construction + unit tests):
- every gap references a real requirement_id / raw_text from the input;
- evidence blocks are copied verbatim from the stored match evidence;
- explanations reuse the stored match explanation plus structured arithmetic
  on stored fields (required vs estimated years) — never new claims;
- suggestions are conditional templates ("If you have genuine ... experience")
  that only name the requirement itself — they never assert, invent, or add
  skills, experience, projects, certifications, education or achievements.
"""
from __future__ import annotations

TOOL_CATEGORIES = {"TOOL", "CLOUD"}
SKILL_CATEGORIES = {"PROGRAMMING_LANGUAGE", "FRAMEWORK", "DATABASE", "DOMAIN", "OTHER", "SKILL"}

HONESTY_NOTE = (
    "Gaps are derived only from this job description's requirements and the "
    "evidence found in the resume. Nothing here claims experience the resume "
    "does not document."
)


def gap_category_for(requirement: dict, status: str) -> str:
    cat = (requirement.get("category") or "OTHER").upper()
    if status == "CONTRADICTORY":
        return "Contradictory Evidence"
    if status == "INSUFFICIENT_EVIDENCE":
        return "Missing Evidence"
    if status == "TRANSFERABLE":
        return "Transferable Skills"
    if status == "PARTIALLY_SATISFIED":
        return "Insufficient Experience"
    if cat in ("EDUCATION", "DEGREE"):
        return "Missing Education"
    if cat == "EXPERIENCE":
        return "Insufficient Experience"
    if cat in TOOL_CATEGORIES:
        return "Missing Tools/Technologies"
    return "Missing Skills"


def _evidence_confidence(evidence: list[dict]) -> float | None:
    confs = [e.get("confidence") for e in (evidence or []) if isinstance(e.get("confidence"), (int, float))]
    return round(max(confs), 3) if confs else None


def _years_gap_text(requirement: dict, match: dict) -> str | None:
    req_years = requirement.get("minimum_years")
    est_years = match.get("estimated_years")
    if req_years and est_years is not None:
        shortfall = round(float(req_years) - float(est_years), 2)
        if shortfall > 0:
            return (f"Required: {req_years}+ years; documented: ~{est_years} years "
                    f"(about {shortfall} years below the stated requirement).")
        return (f"Required: {req_years}+ years; documented: ~{est_years} years.")
    if req_years and est_years is None:
        return (f"Required: {req_years}+ years; the resume does not contain dated "
                f"evidence to verify this duration.")
    return None


def _suggestion_for(requirement: dict, status: str, gap_category: str) -> str:
    req = requirement.get("normalized_requirement") or requirement.get("raw_text", "")
    if status == "CONTRADICTORY":
        return ("Review the stated durations for consistency with the dated work history, "
                "and keep only claims the timeline supports.")
    if status == "TRANSFERABLE":
        return (f"If you have actually used {req} in a project, include that project and "
                f"describe your specific contribution. Do not list {req} based only on related skills.")
    if status == "INSUFFICIENT_EVIDENCE":
        return (f"If the experience exists but is not currently documented, add a relevant "
                f"project, responsibility, or achievement that demonstrates {req}, with dates where possible.")
    if gap_category == "Insufficient Experience":
        return (f"If you have additional genuine {req} experience, document the roles and "
                f"dates that demonstrate it.")
    if gap_category == "Missing Education":
        return ("If a higher qualification is in progress or completed, add the degree, "
                "institution, and dates as stated on the certificate.")
    return (f"If you have genuine {req} experience, add the specific responsibilities, "
            f"tools, or outcomes you actually worked with.")


def _transferable_sources(match: dict) -> list[dict]:
    # The stored evidence items carry relation/strength; the candidate source
    # skill name is recovered from the stored explanation produced by the
    # matcher's fixed template ("... but has <skill> (<REL> strength ...").
    # If the template is absent (e.g. RL-refined wording), fall back to a
    # neutral label instead of guessing a skill name.
    import re
    sources = []
    skill_from_text = None
    expl = match.get("explanation") or ""
    mt = re.search(r"but has (.+?) \(", expl)
    if mt:
        skill_from_text = mt.group(1).strip()
    for e in (match.get("evidence") or []):
        rel = e.get("relation") or ("transferable" if match.get("transferable_match") else None)
        if rel:
            sources.append({"skill": skill_from_text or "related skill",
                            "relation": rel, "strength": e.get("strength"),
                            "evidence_text": e.get("text", "")})
    return sources


def build_gap_report(requirements: list[dict], matches: list[dict]) -> dict:
    """Build the gap report purely from stored requirement + match rows."""
    by_req = {r.get("id"): r for r in requirements}
    by_match = {m.get("requirement_id"): m for m in matches}

    # OR-group handling: a MISSING member of an OR group is not a real gap
    # when a sibling member is satisfied (reuses the extractor's AND/OR logic).
    or_groups: dict[str, list[str]] = {}
    for r in requirements:
        if (r.get("operator") or "AND").upper() == "OR" and r.get("logic_group"):
            or_groups.setdefault(r["logic_group"], []).append(r["id"])
    or_covered: set[str] = set()
    for _gid, members in or_groups.items():
        satisfied = any((by_match.get(mid) or {}).get("status") in ("FULLY_SATISFIED", "PARTIALLY_SATISFIED")
                        for mid in members)
        if satisfied:
            or_covered.update(m for m in members
                              if (by_match.get(m) or {}).get("status") in ("MISSING", "INSUFFICIENT_EVIDENCE"))

    critical_gaps, preferred_gaps = [], []
    transferable_skills, insufficient_evidence, covered = [], [], []

    for req in requirements:
        req_id = req.get("id")
        m = by_match.get(req_id)
        if not m:
            continue  # requirement without a match result: skip, never invent
        status = m.get("status", "MISSING")
        mandatory = bool(req.get("mandatory", True))
        evidence = m.get("evidence") or []
        category = gap_category_for(req, status)

        if status == "FULLY_SATISFIED" or req_id in or_covered:
            covered.append({
                "requirement_id": req_id,
                "requirement_text": req.get("raw_text", ""),
                "normalized_requirement": req.get("normalized_requirement", ""),
                "requirement_type": req.get("category", "OTHER"),
                "mandatory": bool(req.get("mandatory", True)),
                "status": status if req_id not in or_covered else m.get("status", "MISSING"),
                "covered_by_or_group": req_id in or_covered,
                "evidence_confidence": _evidence_confidence(evidence),
            })
            continue

        years_text = _years_gap_text(req, m)
        base_expl = m.get("explanation", "")
        gap_expl = f"{base_expl} {years_text}" if years_text and years_text not in base_expl else (years_text or base_expl)

        item = {
            "requirement_id": req_id,
            "requirement_text": req.get("raw_text", ""),
            "normalized_requirement": req.get("normalized_requirement", ""),
            "requirement_type": req.get("category", "OTHER"),
            "mandatory": bool(req.get("mandatory", True)),
            "severity": "critical" if mandatory else "preferred",
            "status": status,
            "gap_category": category,
            "evidence": [{"text": e.get("text", ""), "section": e.get("section", "Other"),
                          "confidence": e.get("confidence")} for e in evidence],
            "evidence_confidence": _evidence_confidence(evidence),
            "gap_explanation": gap_expl,
            "suggestion": _suggestion_for(req, status, category),
            "required_years": req.get("minimum_years"),
            "estimated_years": m.get("estimated_years"),
        }

        if status == "TRANSFERABLE":
            item["transferable_sources"] = _transferable_sources(m)
            item["honesty_note"] = ("Related experience does not demonstrate direct experience "
                                    f"with {req.get('normalized_requirement', 'this requirement')}.")
            transferable_skills.append(item)
            # A mandatory transferable requirement is still an unmet requirement:
            # also surface it as a gap (same object, no duplication of facts).
            (critical_gaps if mandatory else preferred_gaps).append({**item, "listed_as": "gap+transferable"})
        elif status == "INSUFFICIENT_EVIDENCE":
            insufficient_evidence.append(item)
            (critical_gaps if mandatory else preferred_gaps).append({**item, "listed_as": "gap+insufficient-evidence"})
        else:
            (critical_gaps if mandatory else preferred_gaps).append(item)

    total = len(requirements)
    n_covered = len(covered)
    coverage = round(n_covered / total * 100, 1) if total else 0.0
    return {
        "critical_gaps": critical_gaps,
        "preferred_gaps": preferred_gaps,
        "transferable_skills": transferable_skills,
        "insufficient_evidence": insufficient_evidence,
        "covered_requirements": covered,
        "honesty_note": HONESTY_NOTE,
        "summary": {
            "total_requirements": total,
            "covered_count": n_covered,
            "critical_gap_count": len(critical_gaps),
            "preferred_gap_count": len(preferred_gaps),
            "transferable_count": len(transferable_skills),
            "insufficient_evidence_count": len(insufficient_evidence),
            "coverage_percentage": coverage,
            "overall_message": (f"Your resume covers {n_covered} of {total} requirements for this role."
                                if total else "No requirements were extracted for this role."),
        },
    }
