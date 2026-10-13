"""RL-based requirement matching policy (additive layer over the deterministic matcher).

Insertion point: backend/app/nlp/matcher/engine.py::match_requirement
produces the base decision; backend/app/nlp/rl/inference.py optionally
refines it into a final decision. The deterministic matcher, scoring gate
(app/nlp/matcher/scoring.py) and AND/OR tree stay authoritative — see
inference.apply_guardrails. When no trained model is present the system
falls back to the base matcher unchanged.
"""
from app.nlp.rl.config import RLConfig, DEFAULT_CONFIG  # noqa: F401
from app.nlp.rl import state_builder, reward, policy, inference  # noqa: F401

__all__ = ["RLConfig", "DEFAULT_CONFIG", "state_builder", "reward", "policy", "inference"]
