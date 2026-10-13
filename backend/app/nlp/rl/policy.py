"""Lightweight linear Q-policy (no deep RL, no torch dependency).

Why this algorithm:
- The seed set has ~65 requirement-level cases; a deep network would be
  unjustified and would overfit. A linear Q-function Q(s,a) = w_a·s + b_a
  (7x17 = ~120 parameters incl. bias) is proportionate, CPU-friendly,
  deterministic under a fixed seed, and inspectable (weights show which
  features drive each action).
- Decisions are single-step (contextual bandit, gamma=0), so TD-learning
  reduces to supervised reward regression with epsilon-greedy exploration.

Training update (terminal step): w_a += lr * (r - Q(s,a)) * s.
Inference: argmax Q with softmax confidence; guardrails in inference.py
restrict the argmax to constraint-valid actions.
Only numpy is required.
"""
from __future__ import annotations
import json
import os
import numpy as np

from app.nlp.rl.config import ACTION_NAMES, STATUS_TO_ACTION
from app.nlp.rl.state_builder import STATE_FEATURES, STATE_DIM


class LinearQPolicy:
    def __init__(self, state_dim: int = STATE_DIM, n_actions: int = 6,
                 seed: int = 42):
        rng = np.random.default_rng(seed)
        self.weights = rng.normal(0, 0.01, size=(n_actions, state_dim))
        self.bias = np.zeros((n_actions,))
        self.state_dim = state_dim
        self.n_actions = n_actions
        self.seed = seed

    # --- core ---
    def q_values(self, state: list[float] | np.ndarray) -> np.ndarray:
        s = np.asarray(state, dtype=float)
        return self.weights @ s + self.bias

    def predict(self, state: list[float] | np.ndarray,
                allowed: list[int] | None = None,
                temperature: float = 1.0) -> tuple[int, float, list[float]]:
        q = self.q_values(state)
        mask = np.full(self.n_actions, -1e9)
        idx = allowed if allowed is not None else list(range(self.n_actions))
        for a in idx:
            mask[a] = q[a]
        # softmax over masked Q for a calibrated-ish confidence
        z = (mask - mask.max()) / max(temperature, 1e-6)
        exp = np.exp(np.clip(z, -50, 0))
        probs = exp / exp.sum()
        action = int(np.argmax(mask))
        return action, float(probs[action]), [float(p) for p in probs]

    def update(self, state: list[float] | np.ndarray, action: int,
               reward: float, lr: float) -> float:
        s = np.asarray(state, dtype=float)
        q = float(self.weights[action] @ s + self.bias[action])
        td = float(reward) - q
        self.weights[action] += lr * td * s
        self.bias[action] += lr * td
        return td

    # --- persistence (small JSON, no large artifacts) ---
    def to_dict(self, config_dict: dict | None = None,
                train_metadata: dict | None = None) -> dict:
        return {
            "format": "linear-q-v1",
            "state_features": STATE_FEATURES,
            "actions": ACTION_NAMES,
            "weights": self.weights.tolist(),
            "bias": self.bias.tolist(),
            "seed": self.seed,
            "config": config_dict or {},
            "train_metadata": train_metadata or {},
        }

    def save(self, path: str, config_dict: dict | None = None,
             train_metadata: dict | None = None) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(config_dict, train_metadata), f, indent=2)
        return path

    @classmethod
    def load(cls, path: str) -> "LinearQPolicy":
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        feats = d.get("state_features", STATE_FEATURES)
        if feats != STATE_FEATURES:
            raise ValueError(
                f"RL model feature mismatch: expected {STATE_FEATURES}, got {feats}")
        pol = cls(state_dim=len(feats), n_actions=len(d.get("actions", ACTION_NAMES)),
                  seed=int(d.get("seed", 42)))
        pol.weights = np.array(d["weights"], dtype=float)
        pol.bias = np.array(d["bias"], dtype=float)
        return pol

    def feature_contributions(self, state: list[float] | np.ndarray,
                              action: int, top_k: int = 4) -> list[dict]:
        s = np.asarray(state, dtype=float)
        contrib = self.weights[action] * s
        order = np.argsort(np.abs(contrib))[::-1][:top_k]
        return [{"feature": STATE_FEATURES[i], "value": round(float(s[i]), 3),
                 "contribution": round(float(contrib[i]), 4)} for i in order]

    @staticmethod
    def status_to_action(status: str) -> int:
        return STATUS_TO_ACTION[status]

    @staticmethod
    def action_to_status(action: int) -> str:
        return ACTION_NAMES[int(action)]
