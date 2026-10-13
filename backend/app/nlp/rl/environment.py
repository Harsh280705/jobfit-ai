"""Training environment: requirement-level contextual bandit.

Each step presents one requirement state; the agent picks a matching action;
the environment returns the reward against the annotated expected status and
terminates (single-step episodes, gamma = 0). This matches the problem
structure: requirement decisions are i.i.d. — there is no sequential
next-state — so Q-learning here reduces to reward regression with
exploration, which is exactly reproducible and CPU-friendly on 65 cases.

Two data sources:
1. REAL cases from data/evaluation/cases.json (via the existing pipeline).
2. SYNTHETIC states (clearly marked) sampled from documented per-status
   feature prototypes + Gaussian noise, used ONLY to balance classes during
   training because the seed set is heavily skewed toward FULLY_SATISFIED
   (many duplicated Python rows). Synthetic states never enter evaluation.
"""
from __future__ import annotations
import random


# Documented synthetic prototypes: [is_mand, has_yrs, req_norm, has_direct,
# has_trans, trans_max, semantic, est_norm, exp_gap, ev_count, ev_conf,
# contra, is_edu, edu_sat, is_or, base_conf, base_pos]
_SYNTHETIC_PROTOTYPES: dict[str, list[float]] = {
    "FULLY_SATISFIED":      [1, 0, 0.0, 1, 0, 0.0, 0.8, 0.3, 0.0, 0.33, 0.9, 0, 0, 0, 0, 0.9, 1],
    "PARTIALLY_SATISFIED":  [1, 1, 0.3, 1, 0, 0.0, 0.7, 0.1, -0.2, 0.33, 0.8, 0, 0, 0, 0, 0.8, 0],
    "TRANSFERABLE":         [1, 0, 0.0, 0, 1, 0.8, 0.5, 0.0, 0.0, 0.33, 0.75, 0, 0, 0, 0, 0.65, 0],
    "MISSING":              [1, 0, 0.0, 0, 0, 0.0, 0.1, 0.0, 0.0, 0.0, 0.0, 0, 0, 0, 0, 0.85, 0],
    "INSUFFICIENT_EVIDENCE":[1, 1, 0.3, 1, 0, 0.0, 0.55, 0.0, -0.3, 0.33, 0.7, 0, 0, 0, 0, 0.55, 0],
    "CONTRADICTORY":        [1, 0, 0.0, 1, 0, 0.0, 0.7, 0.1, -0.5, 0.33, 0.8, 1, 0, 0, 0, 0.7, 1],
}


def synthetic_states_for(status: str, n: int, noise: float = 0.05,
                         rng: random.Random | None = None) -> list[list[float]]:
    rng = rng or random.Random(0)
    proto = _SYNTHETIC_PROTOTYPES[status]
    out = []
    for _ in range(n):
        vec = [min(1.0, max(0.0 if i != 8 else -1.0, v + rng.gauss(0, noise)))
               for i, v in enumerate(proto)]
        # exp_gap (index 8) lives in [-1, 1]
        vec[8] = max(-1.0, min(1.0, vec[8]))
        out.append([round(float(v), 4) for v in vec])
    return out


class RequirementMatchEnv:
    """Contextual-bandit environment over (state, expected_action, mandatory)."""

    def __init__(self, states: list[list[float]], expected: list[int],
                 mandatory: list[bool] | None = None):
        assert len(states) == len(expected)
        self.states = states
        self.expected = expected
        self.mandatory = mandatory or [True] * len(states)
        self._idx = 0
        self._order: list[int] = list(range(len(states)))

    def __len__(self) -> int:
        return len(self.states)

    def shuffle(self, rng: random.Random) -> None:
        rng.shuffle(self._order)

    def reset(self, idx: int) -> list[float]:
        self._idx = idx
        return self.states[self._order[idx]]

    def step(self, action: int, config) -> tuple[float, bool, dict]:
        from app.nlp.rl.config import ACTION_TO_STATUS
        from app.nlp.rl.reward import compute_reward
        pos = self._order[self._idx]
        predicted = ACTION_TO_STATUS[int(action)]
        expected = ACTION_TO_STATUS[int(self.expected[pos])]
        reward = compute_reward(predicted, expected, self.mandatory[pos], config)
        return reward, True, {"predicted": predicted, "expected": expected}
