"""Overall fit scoring: weighted dimensions + mandatory gate."""
from __future__ import annotations

STATUS_SCORE = {
    "FULLY_SATISFIED": 1.0,
    "PARTIALLY_SATISFIED": 0.55,
    "TRANSFERABLE": 0.4,
    "INSUFFICIENT_EVIDENCE": 0.2,
    "CONTRADICTORY": 0.25,
    "MISSING": 0.0,
}


def compute_scores(matches: list[dict], requirements: list[dict], weights: dict | None = None) -> dict:
    w = weights or {}
    wm = w.get("mandatory", 0.40); wp = w.get("preferred", 0.15)
    we = w.get("experience", 0.20); ws = w.get("skill", 0.15)
    wt = w.get("transferability", 0.05); wc = w.get("confidence", 0.05)

    by_id = {r.get("id"): r for r in requirements}
    mand = [m for m in matches if by_id.get(m["requirement_id"], {}).get("mandatory")]
    pref = [m for m in matches if not by_id.get(m["requirement_id"], {}).get("mandatory")]

    def avg(ms: list[dict]) -> float:
        return sum(STATUS_SCORE.get(m["status"], 0) for m in ms) / len(ms) if ms else 0.0

    mand_cov, pref_cov = avg(mand), avg(pref)
    exp_reqs = [m for m in matches if by_id.get(m["requirement_id"], {}).get("minimum_years")]
    exp_fit = avg(exp_reqs) if exp_reqs else mand_cov
    skill_fit = sum(1 for m in matches if m.get("direct_match")) / len(matches) if matches else 0.0
    transf = sum(1 for m in matches if m.get("transferable_match")) / len(matches) if matches else 0.0
    conf = sum(m.get("confidence", 0) for m in matches) / len(matches) if matches else 0.0

    overall = wm * mand_cov + wp * pref_cov + we * exp_fit + ws * skill_fit + wt * transf + wc * conf
    # Mandatory gate: missing core mandatory requirement caps the score
    mand_missing = sum(1 for m in mand if m["status"] in ("MISSING", "CONTRADICTORY"))
    mand_partial = sum(1 for m in mand if m["status"] in ("PARTIALLY_SATISFIED", "INSUFFICIENT_EVIDENCE", "TRANSFERABLE"))
    mand_sat = sum(1 for m in mand if m["status"] == "FULLY_SATISFIED")
    if mand and mand_missing:
        overall = min(overall, 0.59)
        eligibility = "NOT ELIGIBLE FOR ALL MANDATORY REQUIREMENTS"
    elif mand and mand_partial:
        overall = min(overall, 0.79)
        eligibility = "PARTIAL FIT — mandatory gaps remain"
    elif mand:
        eligibility = "STRONG FIT — all mandatory requirements satisfied"
    else:
        eligibility = "NO MANDATORY REQUIREMENTS DEFINED"

    return {
        "overall": round(overall * 100, 1),
        "mandatory_coverage": round(mand_cov * 100, 1),
        "preferred_coverage": round(pref_cov * 100, 1),
        "experience_fit": round(exp_fit * 100, 1),
        "skill_fit": round(skill_fit * 100, 1),
        "transferability": round(transf * 100, 1),
        "evidence_confidence": round(conf * 100, 1),
        "eligibility": eligibility,
        "mandatory_total": len(mand),
        "mandatory_satisfied": mand_sat,
        "mandatory_partial": mand_partial,
        "mandatory_missing": mand_missing,
    }
