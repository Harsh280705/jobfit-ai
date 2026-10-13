"""Unit + integration tests for the RL decision layer.

The deterministic matcher is never modified here — these tests pin its
behavior (fallback path) and verify the RL layer only refines decisions
inside the constraint-valid space.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.nlp.rl.config import RLConfig, ACTION_NAMES, STATUS_TO_ACTION, ACTION_TO_STATUS
from app.nlp.rl.state_builder import STATE_FEATURES, STATE_DIM, build_state
from app.nlp.rl.reward import compute_reward
from app.nlp.rl.policy import LinearQPolicy
from app.nlp.rl.inference import (
    allowed_actions, decide_requirement, load_policy, clear_policy_cache,
)
from app.nlp.matcher.engine import match_requirement


def _req(norm, **kw):
    base = {"id": "req_rl", "raw_text": norm, "normalized_requirement": norm,
            "category": "SKILL", "mandatory": True, "preference": "MANDATORY",
            "operator": "AND", "minimum_years": None, "maximum_years": None,
            "confidence": 0.9, "logic_group": None}
    base.update(kw)
    return base


def _skill(fact, section="Experience"):
    return {"fact": fact, "source_text": f"Worked with {fact} daily",
            "source_section": section, "confidence": 0.9}


# --- state construction ---
def test_state_dim_and_ranges():
    r = _req("Python")
    base = match_requirement(r, [_skill("Python")], [], "Python backend work")
    st = build_state(r, [_skill("Python")], [], "Python backend work", base)
    assert len(st["vector"]) == STATE_DIM == len(STATE_FEATURES)
    for i, v in enumerate(st["vector"]):
        if i == 8:  # exp_gap in [-1, 1]
            assert -1.0 <= v <= 1.0
        else:
            assert 0.0 <= v <= 1.0, (STATE_FEATURES[i], v)
    assert st["info"]["n_direct"] == 1


def test_state_uses_only_pipeline_features():
    r = _req("PyTorch")
    base = match_requirement(r, [_skill("TensorFlow")], [], "TensorFlow work")
    st = build_state(r, [_skill("TensorFlow")], [], "TensorFlow work", base)
    assert st["vector"][3] == 0.0  # no direct
    assert st["vector"][4] == 1.0  # transferable evidence
    assert st["vector"][5] >= 0.55


# --- action mapping ---
def test_action_space_matches_matcher_statuses():
    assert len(ACTION_NAMES) == 6
    for name in ("FULLY_SATISFIED", "PARTIALLY_SATISFIED", "TRANSFERABLE",
                 "MISSING", "INSUFFICIENT_EVIDENCE", "CONTRADICTORY"):
        assert name in STATUS_TO_ACTION
        assert ACTION_TO_STATUS[STATUS_TO_ACTION[name]] == name


# --- reward ---
def test_reward_values():
    cfg = RLConfig()
    assert compute_reward("FULLY_SATISFIED", "FULLY_SATISFIED", True, cfg) == 2.0
    assert compute_reward("MISSING", "MISSING", True, cfg) == 2.0
    assert compute_reward("MISSING", "MISSING", False, cfg) == 1.0
    # false positive: predict pass, actually missing
    assert compute_reward("FULLY_SATISFIED", "MISSING", True, cfg) == -3.0
    # false negative
    assert compute_reward("MISSING", "FULLY_SATISFIED", True, cfg) == -1.0
    # wrong transferable
    assert compute_reward("TRANSFERABLE", "MISSING", True, cfg) == -2.0
    # wrong contradiction
    assert compute_reward("MISSING", "CONTRADICTORY", True, cfg) == -2.0


def test_reward_configurable():
    cfg = RLConfig()
    cfg.reward.false_positive = -10.0
    assert compute_reward("FULLY_SATISFIED", "MISSING", True, cfg) == -10.0


# --- policy basics ---
def test_policy_predict_and_persist(tmp_path):
    p = LinearQPolicy(seed=0)
    vec = [0.0] * STATE_DIM
    a, conf, probs = p.predict(vec)
    assert 0 <= a < 6 and 0.0 <= conf <= 1.0 and abs(sum(probs) - 1.0) < 1e-6
    path = str(tmp_path / "pol.json")
    p.save(path, config_dict={"seed": 0}, train_metadata={"t": 1})
    q = LinearQPolicy.load(path)
    a2, _, _ = q.predict(vec)
    assert a2 == a


def test_policy_deterministic_seed():
    p1, p2 = LinearQPolicy(seed=123), LinearQPolicy(seed=123)
    v = [0.5] * STATE_DIM
    assert p1.predict(v)[0] == p2.predict(v)[0]


# --- fallback ---
def test_load_policy_missing_returns_none(tmp_path):
    clear_policy_cache()
    assert load_policy(str(tmp_path / "nope.json")) is None
    clear_policy_cache()


def test_fallback_returns_base_unchanged():
    r = _req("Python")
    skills = [_skill("Python")]
    base = match_requirement(r, skills, [], "Python work")
    out = decide_requirement(r, skills, [], "Python work", base, policy=None)
    assert out["status"] == base["status"]
    assert out["rl_used"] is False and out["rl_fallback"] is True
    assert out["rl_changed_decision"] is False


# --- guardrails ---
def test_mandatory_missing_cannot_become_pass():
    r = _req("Python")  # mandatory, no evidence anywhere
    base = match_requirement(r, [_skill("Java")], [], "Java Spring work")
    assert base["status"] == "MISSING"
    st = build_state(r, [_skill("Java")], [], "Java Spring work", base)
    allowed = allowed_actions(st["vector"], st["info"], base["status"])
    assert 0 not in allowed and 1 not in allowed and 2 not in allowed


def test_contradiction_protection():
    exps = [{"company": "X", "role": "SWE", "start_date": "Jan 2023", "end_date": "Jan 2024",
             "technologies": ["Python"], "description": "Python work"}]
    text = "Python developer with 10 years of experience. Software Engineer Jan 2023 - Jan 2024 Python work."
    r = _req("Python")
    base = match_requirement(r, [_skill("Python")], exps, text)
    assert base["status"] == "CONTRADICTORY"
    st = build_state(r, [_skill("Python")], exps, text, base)
    assert allowed_actions(st["vector"], st["info"], base["status"]) == [5]
    # even a policy voting FULLY must be vetoed
    pol = LinearQPolicy(seed=0)
    out = decide_requirement(r, [_skill("Python")], exps, text, base, pol,
                             RLConfig(min_confidence_to_override=0.0))
    assert out["final_status"] == "CONTRADICTORY"


def test_education_protection():
    r = _req("Master's", category="EDUCATION",
             normalized_requirement="Master's", raw_text="Master's degree")
    base = match_requirement(r, [], [], "Bachelor's in Computer Science, VIT, 2020 - 2024.")
    assert base["status"] == "MISSING"
    st = build_state(r, [], [], "Bachelor's in Computer Science, VIT, 2020 - 2024.", base)
    allowed = allowed_actions(st["vector"], st["info"], base["status"])
    assert 0 not in allowed and 1 not in allowed


def test_experience_threshold_protection():
    exps = [{"company": "Zoho", "role": "SWE", "start_date": "Jan 2024", "end_date": "Jan 2025",
             "technologies": ["Python"], "description": "Python APIs"}]
    r = _req("Python", minimum_years=3)
    base = match_requirement(r, [_skill("Python")], exps, "Python Jan 2024 Jan 2025")
    assert base["status"] == "PARTIALLY_SATISFIED"
    st = build_state(r, [_skill("Python")], exps, "Python Jan 2024 Jan 2025", base)
    assert 0 not in allowed_actions(st["vector"], st["info"], base["status"])


def test_and_or_semantics_preserved():
    # RL only relabels status; the requirement's operator/logic_group are untouched.
    r = _req("Python", operator="OR", logic_group="grp_abc")
    base = match_requirement(r, [_skill("Python")], [], "Python work")
    pol = LinearQPolicy(seed=1)
    out = decide_requirement(r, [_skill("Python")], [], "Python work", base, pol)
    assert r["operator"] == "OR" and r["logic_group"] == "grp_abc"
    assert out["final_status"] in STATUS_TO_ACTION


def test_direct_evidence_blocks_missing():
    r = _req("Python")
    base = match_requirement(r, [_skill("Python")], [], "Python backend work")
    st = build_state(r, [_skill("Python")], [], "Python backend work", base)
    assert 3 not in allowed_actions(st["vector"], st["info"], base["status"])


# --- integration: disabled vs enabled ---
def test_rl_disabled_keeps_existing_behavior(monkeypatch):
    monkeypatch.setenv("RL_ENABLED", "0")
    try:
        r = _req("PyTorch")
        base = match_requirement(r, [_skill("TensorFlow")], [], "TensorFlow work")
        out = decide_requirement(r, [_skill("TensorFlow")], [], "TensorFlow work",
                                 base, LinearQPolicy(seed=0))
        assert out["status"] == base["status"] and out["rl_used"] is False
    finally:
        monkeypatch.delenv("RL_ENABLED", raising=False)


def test_rl_enabled_path_marks_usage():
    import os
    old = os.environ.get("RL_ENABLED")
    os.environ["RL_ENABLED"] = "1"
    try:
        r = _req("Python")
        base = match_requirement(r, [_skill("Python")], [], "Python backend work")
        out = decide_requirement(r, [_skill("Python")], [], "Python backend work",
                                 base, LinearQPolicy(seed=0))
        assert out["rl_used"] is True
        assert out["existing_status"] == base["status"]
        assert "rl_confidence" in out and "rl_changed_decision" in out
        assert out["final_status"] == out["status"]
    finally:
        if old is None:
            del os.environ["RL_ENABLED"]
        else:
            os.environ["RL_ENABLED"] = old


def test_pipeline_helper_falls_back_without_model(tmp_path, monkeypatch):
    from app.services.analysis import _maybe_apply_rl
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setenv("RL_MODEL_PATH", str(tmp_path / "absent.json"))
    clear_policy_cache()
    reqs = [_req("Python")]
    base = [match_requirement(reqs[0], [_skill("Python")], [], "Python work")]
    out = _maybe_apply_rl(reqs, base, [_skill("Python")], [], "Python work",
                          {"transferable": 0.55, "semantic": 0.62}, settings)
    assert out == base  # byte-identical fallback
    clear_policy_cache()
