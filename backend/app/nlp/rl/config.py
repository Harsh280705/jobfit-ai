"""RL configuration: algorithm hyper-parameters + reward weights.

All values are starting points (see docs/RESEARCH.md). They are NOT claimed
to be optimal — they are configurable via env vars, the training CLI, or a
JSON config file saved alongside the model.
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field, asdict


@dataclass
class RewardConfig:
    correct: float = 1.0
    correct_mandatory_satisfied: float = 2.0
    correct_mandatory_missing: float = 2.0
    false_positive: float = -3.0
    false_negative: float = -1.0
    wrong_transferable: float = -2.0
    wrong_contradiction: float = -2.0
    # Any other incorrect decision (e.g. PARTIALLY vs FULLY confusion,
    # INSUFFICIENT vs MISSING confusion) falls back to this.
    wrong_other: float = -1.0


@dataclass
class RLConfig:
    seed: int = 42
    learning_rate: float = 0.1
    discount_gamma: float = 0.0  # single-step requirement decisions are terminal
    epsilon_start: float = 0.3
    epsilon_end: float = 0.05
    epsilon_decay_episodes: int = 800
    episodes: int = 2000
    test_size: float = 0.3
    synthetic_per_class: int = 40
    synthetic_noise: float = 0.05
    transferable_threshold: float = 0.55
    semantic_threshold: float = 0.62
    # If the policy's softmax confidence is below this, keep the base decision.
    min_confidence_to_override: float = 0.55
    model_path: str = "backend/app/nlp/rl/models/rl_policy.json"
    reward: RewardConfig = field(default_factory=RewardConfig)

    @classmethod
    def from_env(cls) -> "RLConfig":
        cfg = cls()
        get = os.environ.get
        cfg.seed = int(get("RL_SEED", cfg.seed))
        cfg.learning_rate = float(get("RL_LR", cfg.learning_rate))
        cfg.discount_gamma = float(get("RL_GAMMA", cfg.discount_gamma))
        cfg.epsilon_start = float(get("RL_EPS_START", cfg.epsilon_start))
        cfg.epsilon_end = float(get("RL_EPS_END", cfg.epsilon_end))
        cfg.episodes = int(get("RL_EPISODES", cfg.episodes))
        cfg.test_size = float(get("RL_TEST_SIZE", cfg.test_size))
        cfg.synthetic_per_class = int(get("RL_SYNTH_PER_CLASS", cfg.synthetic_per_class))
        # Reward overrides
        r = cfg.reward
        r.correct = float(get("RL_R_CORRECT", r.correct))
        r.correct_mandatory_satisfied = float(get("RL_R_MAND_SAT", r.correct_mandatory_satisfied))
        r.correct_mandatory_missing = float(get("RL_R_MAND_MISS", r.correct_mandatory_missing))
        r.false_positive = float(get("RL_R_FP", r.false_positive))
        r.false_negative = float(get("RL_R_FN", r.false_negative))
        r.wrong_transferable = float(get("RL_R_TRANSFER", r.wrong_transferable))
        r.wrong_contradiction = float(get("RL_R_CONTRA", r.wrong_contradiction))
        r.wrong_other = float(get("RL_R_OTHER", r.wrong_other))
        cfg.min_confidence_to_override = float(get("RL_MIN_OVERRIDE_CONF", cfg.min_confidence_to_override))
        return cfg

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "RLConfig":
        reward_d = d.pop("reward", {}) if isinstance(d, dict) else {}
        cfg = cls(**{k: v for k, v in (d or {}).items() if k in cls.__dataclass_fields__ and k != "reward"})
        if reward_d:
            cfg.reward = RewardConfig(**{k: v for k, v in reward_d.items() if k in RewardConfig.__dataclass_fields__})
        return cfg


DEFAULT_CONFIG = RLConfig()

# Canonical action <-> status mapping. Mirrors the six statuses produced by
# app/nlp/matcher/engine.py so the agent chooses among the SAME categories
# the existing matcher produces (no unrelated categories).
ACTION_NAMES: list[str] = [
    "FULLY_SATISFIED",      # 0
    "PARTIALLY_SATISFIED",  # 1
    "TRANSFERABLE",         # 2
    "MISSING",              # 3
    "INSUFFICIENT_EVIDENCE",  # 4
    "CONTRADICTORY",        # 5
]
STATUS_TO_ACTION: dict[str, int] = {name: i for i, name in enumerate(ACTION_NAMES)}
ACTION_TO_STATUS: dict[int, str] = {i: name for i, name in enumerate(ACTION_NAMES)}

# Statuses that count as a "positive" (candidate meets the requirement) for
# binary precision/recall/F1 and for false-positive/false-negative accounting.
POSITIVE_STATUSES = {"FULLY_SATISFIED", "PARTIALLY_SATISFIED"}
