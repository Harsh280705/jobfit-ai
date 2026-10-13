"""Reward function for the requirement-level matching policy.

Design notes (see docs/RESEARCH.md):
- False positives (predicting FULLY/PARTIALLY when the candidate does not
  meet the requirement) are penalized most (-3 default) because accepting an
  unqualified candidate is more harmful than being conservative.
- Correct mandatory decisions get a bonus (+2) since the mandatory gate
  drives overall eligibility.
- Wrong TRANSFERABLE / CONTRADICTORY decisions get their own weights
  because they have distinct failure costs (upskilling misdirection /
  trust damage from missed contradictions).
- These values are documented starting points, NOT claimed optima.
"""
from __future__ import annotations
from app.nlp.rl.config import RLConfig, POSITIVE_STATUSES


def is_positive(status: str) -> bool:
    return status in POSITIVE_STATUSES


def compute_reward(
    predicted: str,
    expected: str,
    mandatory: bool = True,
    config: RLConfig | None = None,
) -> float:
    cfg = config or RLConfig()
    r = cfg.reward
    if predicted == expected:
        if mandatory and expected in POSITIVE_STATUSES:
            return r.correct_mandatory_satisfied
        if mandatory and expected not in POSITIVE_STATUSES:
            # correctly identifying a mandatory gap (MISSING/CONTRADICTORY/...)
            return r.correct_mandatory_missing
        return r.correct
    # --- incorrect decisions ---
    if predicted == "TRANSFERABLE" or expected == "TRANSFERABLE":
        # claimed transferability that does not hold (either direction)
        if predicted != expected:
            # only apply the transferable-specific penalty when a
            # transferable claim is involved on either side
            if "TRANSFERABLE" in (predicted, expected):
                # contradiction mistakes keep their own (larger-context) weight
                if "CONTRADICTORY" not in (predicted, expected):
                    return r.wrong_transferable
    if predicted == "CONTRADICTORY" or expected == "CONTRADICTORY":
        return r.wrong_contradiction
    pred_pos, exp_pos = is_positive(predicted), is_positive(expected)
    if pred_pos and not exp_pos:
        return r.false_positive
    if not pred_pos and exp_pos:
        return r.false_negative
    return r.wrong_other


def reward_breakdown(predicted: str, expected: str, mandatory: bool = True,
                     config: RLConfig | None = None) -> dict:
    value = compute_reward(predicted, expected, mandatory, config)
    kind = "correct" if predicted == expected else (
        "false_positive" if (is_positive(predicted) and not is_positive(expected))
        else "false_negative" if (not is_positive(predicted) and is_positive(expected))
        else "wrong_category")
    return {"reward": value, "kind": kind, "predicted": predicted,
            "expected": expected, "mandatory": mandatory}
