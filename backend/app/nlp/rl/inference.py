"""RL inference: base matcher -> state -> policy -> guardrailed final decision.

Safety contract (authoritative constraints stay authoritative):
- The AND/OR tree, mandatory gate (scoring.py) and education/experience
  thresholds are NEVER bypassed: RL only re-labels the requirement status
  within the constraint-valid subset (see allowed_actions).
- If the model file is missing/corrupt/disabled, inference returns the base
  decision unchanged (fallback flag), so the existing pipeline keeps working.
- Low-confidence policy outputs do not override the base decision.

Every decision exposes: existing_status, rl_status (raw policy argmax),
final_status (after guardrails), rl_confidence, rl_changed_decision,
top state features, and the untouched evidence spans.
"""
from __future__ import annotations
import os
from functools import lru_cache

from app.nlp.rl.config import RLConfig, ACTION_TO_STATUS
from app.nlp.rl.state_builder import build_state

_MODEL_CACHE: dict[str, object] = {}
ENABLE_ENV_VAR = "RL_ENABLED"


def is_rl_enabled() -> bool:
    return os.environ.get(ENABLE_ENV_VAR, "1") not in ("0", "false", "False", "no")


def resolve_model_path(config: RLConfig | None = None) -> str:
    cfg = config or RLConfig.from_env()
    override = os.environ.get("RL_MODEL_PATH")
    path = override or cfg.model_path
    if not os.path.isabs(path):
        # resolve relative to the repo root (backend/..)
        here = os.path.dirname(os.path.abspath(__file__))  # .../app/nlp/rl
        repo_root = os.path.abspath(os.path.join(here, "..", "..", "..", ".."))
        candidate = os.path.join(repo_root, path)
        if os.path.exists(candidate):
            return candidate
        # also try backend-relative
        candidate2 = os.path.abspath(os.path.join(here, "..", "..", "..", path))
        return candidate2 if os.path.exists(candidate2) else candidate
    return path


def load_policy(path: str | None = None, config: RLConfig | None = None):
    """Return a cached LinearQPolicy or None when unavailable (fallback)."""
    from app.nlp.rl.policy import LinearQPolicy
    p = path or resolve_model_path(config)
    if p in _MODEL_CACHE:
        return _MODEL_CACHE[p]
    try:
        if not os.path.exists(p):
            return None
        pol = LinearQPolicy.load(p)
        _MODEL_CACHE[p] = pol
        return pol
    except Exception:
        return None


def clear_policy_cache() -> None:
    _MODEL_CACHE.clear()


def allowed_actions(vector: list[float], info: dict, base_status: str) -> list[int]:
    """Constraint-valid action subset. RL may only choose within this set."""
    has_direct = vector[3] >= 0.5
    has_transfer = vector[4] >= 0.5
    semantic = vector[6]
    est_none = info.get("estimated_years") is None
    has_min_years = vector[1] >= 0.5
    exp_gap_neg = vector[8] < -1e-9
    contra = info.get("has_contradiction", False)
    is_edu = vector[12] >= 0.5
    edu_sat = vector[13] >= 0.5

    # 0 FULLY, 1 PARTIALLY, 2 TRANSFERABLE, 3 MISSING, 4 INSUFFICIENT, 5 CONTRADICTORY
    if contra and base_status == "CONTRADICTORY":
        return [5]  # explicit claim-vs-timeline conflict is untouchable
    allowed = [0, 1, 2, 3, 4, 5]
    if contra:
        allowed = [a for a in allowed if a not in (0, 1, 2)]
    if is_edu and not edu_sat:
        allowed = [a for a in allowed if a not in (0, 1)]
    if has_min_years and (est_none or exp_gap_neg):
        if 0 in allowed:
            allowed.remove(0)  # cannot claim FULLY below threshold/unverifiable
    if not has_direct and not has_transfer and semantic < 0.5:
        allowed = [a for a in allowed if a not in (0, 1, 2)]
    if has_direct and not contra:
        if 3 in allowed:
            allowed.remove(3)  # direct evidence present: MISSING is invalid
    if has_transfer and not has_direct and not contra:
        # transferable evidence must keep TRANSFERABLE reachable
        if 2 not in allowed:
            allowed.append(2)
    return sorted(allowed) or [3]


_EXPLANATION_TEMPLATES = {
    "FULLY_SATISFIED": "Direct candidate evidence satisfies '{req}' with no threshold shortfall.",
    "PARTIALLY_SATISFIED": "Candidate evidence mentions '{req}' but estimated experience ({est}) is below the required threshold.",
    "TRANSFERABLE": "No direct '{req}' evidence; strong related-skill evidence (strength {tmax}) suggests transferability with upskilling.",
    "MISSING": "No evidence of '{req}' found in the resume.",
    "INSUFFICIENT_EVIDENCE": "Related content found for '{req}' but no concrete verifiable evidence; treated as insufficient, not a match.",
    "CONTRADICTORY": "Resume claims about '{req}' conflict with dated timeline evidence.",
}


def decide_requirement(
    requirement: dict,
    candidate_skills: list[dict],
    experiences: list[dict],
    resume_text: str,
    base_result: dict,
    policy=None,
    config: RLConfig | None = None,
) -> dict:
    """Combine base matcher output with the RL policy (guardrailed).

    Returns the base result dict extended with rl_* fields; 'status' is the
    FINAL (guardrailed) decision and scoring downstream uses it unchanged.
    """
    cfg = config or RLConfig.from_env()
    base_status = base_result.get("status", "MISSING")
    st = build_state(requirement, candidate_skills, experiences, resume_text,
                     base_result, cfg.transferable_threshold)
    vector, info = st["vector"], st["info"]

    if policy is None or not is_rl_enabled():
        out = dict(base_result)
        out.update({
            "existing_status": base_status,
            "rl_status": base_status,
            "final_status": base_status,
            "status": base_status,
            "rl_confidence": round(float(base_result.get("confidence", 0.0) or 0.0), 3),
            "rl_changed_decision": False,
            "rl_used": False,
            "rl_fallback": True,
            "rl_top_features": [],
            "rl_explanation": base_result.get("explanation", ""),
        })
        return out

    allowed = allowed_actions(vector, info, base_status)
    raw_action, raw_conf, _probs = policy.predict(vector)
    raw_status = ACTION_TO_STATUS[raw_action]
    # constrain to valid set, then confidence-gate the override
    if raw_action not in allowed:
        action, conf, probs = policy.predict(vector, allowed=allowed)
        final_status = ACTION_TO_STATUS[action]
    else:
        action, conf, probs = raw_action, raw_conf, _probs
        final_status = raw_status
    if conf < cfg.min_confidence_to_override:
        # low confidence -> keep the deterministic decision
        from app.nlp.rl.config import STATUS_TO_ACTION
        final_status = base_status
        action = STATUS_TO_ACTION.get(base_status, action)
        conf = max(conf, 0.0)

    top_features = policy.feature_contributions(vector, action)
    tmpl = _EXPLANATION_TEMPLATES.get(final_status, base_result.get("explanation", ""))
    est = info.get("estimated_years")
    rl_explanation = tmpl.format(
        req=requirement.get("normalized_requirement", "?"),
        est=f"~{est}y" if est is not None else "unverifiable",
        tmax=info.get("transfer_max", 0),
    )

    out = dict(base_result)
    out.update({
        "existing_status": base_status,
        "rl_status": raw_status,
        "final_status": final_status,
        "status": final_status,
        "direct_match": final_status in ("FULLY_SATISFIED", "PARTIALLY_SATISFIED", "CONTRADICTORY")
        if final_status != base_status else base_result.get("direct_match", False),
        "transferable_match": (final_status == "TRANSFERABLE")
        if final_status != base_status else base_result.get("transferable_match", False),
        "rl_confidence": round(float(conf), 3),
        "rl_changed_decision": bool(final_status != base_status),
        "rl_used": True,
        "rl_fallback": False,
        "rl_top_features": top_features,
        "rl_explanation": rl_explanation,
    })
    # keep the original deterministic explanation traceable
    out["base_explanation"] = base_result.get("explanation", "")
    if out["rl_changed_decision"]:
        out["explanation"] = rl_explanation + f" [Base matcher: {base_status}.]"
    return out


def match_requirement_with_rl(
    requirement: dict,
    candidate_skills: list[dict],
    experiences: list[dict],
    resume_text: str,
    thresholds: dict | None = None,
    policy=None,
    config: RLConfig | None = None,
    _policy_loaded: bool = False,
) -> dict:
    """Drop-in replacement for matcher.engine.match_requirement with RL layer."""
    from app.nlp.matcher.engine import match_requirement as base_match
    cfg = config or RLConfig.from_env()
    base = base_match(requirement, candidate_skills, experiences, resume_text, thresholds)
    if policy is None and not _policy_loaded:
        policy = load_policy(config=cfg)
    return decide_requirement(requirement, candidate_skills, experiences,
                              resume_text, base, policy, cfg)
