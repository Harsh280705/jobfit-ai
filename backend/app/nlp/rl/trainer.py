"""Trainer: stratified split -> real + synthetic states -> epsilon-greedy Q-learning.

Strict train/test discipline: cases are split by seed BEFORE any training;
the held-out test indices are recorded in the model metadata and reused by
scripts/run_evaluation.py so RL is never evaluated on its own training rows.
"""
from __future__ import annotations
import random
from collections import Counter

from app.nlp.rl.config import RLConfig, STATUS_TO_ACTION
from app.nlp.rl.policy import LinearQPolicy
from app.nlp.rl.environment import RequirementMatchEnv, synthetic_states_for


def stratified_split(n: int, labels: list[str], test_size: float,
                     seed: int) -> tuple[list[int], list[int]]:
    rng = random.Random(seed)
    by_label: dict[str, list[int]] = {}
    for i, lab in enumerate(labels):
        by_label.setdefault(lab, []).append(i)
    train_idx, test_idx = [], []
    for lab, idxs in by_label.items():
        idxs = idxs[:]
        rng.shuffle(idxs)
        n_test = max(1 if len(idxs) > 1 else 0, round(len(idxs) * test_size))
        n_test = min(n_test, len(idxs) - (1 if len(idxs) > 1 else 0))
        test_idx.extend(idxs[:n_test])
        train_idx.extend(idxs[n_test:])
    rng.shuffle(train_idx)
    rng.shuffle(test_idx)
    return sorted(train_idx), sorted(test_idx)


def build_real_states(cases: list[dict], indices: list[int],
                      config: RLConfig) -> tuple[list[list[float]], list[int], list[bool]]:
    """Run each training case through the EXISTING pipeline to get states."""
    from app.nlp.extractors.requirements import extract_requirements
    from app.nlp.extractors.resume import extract_skills, extract_experience
    from app.nlp.matcher.engine import match_requirement
    from app.nlp.parsers.documents import segment_sections
    from app.nlp.rl.state_builder import build_state

    states, expected, mandatory = [], [], []
    for i in indices:
        c = cases[i]
        req_text = c.get("requirement_text") or c.get("requirement", "")
        resume_text = c.get("resume_text") or c.get("resume", "")
        label = c.get("expected_status", "MISSING")
        reqs, _ = extract_requirements(req_text)
        r = reqs[0] if reqs else {
            "id": "tmp", "raw_text": req_text, "normalized_requirement": req_text[:80],
            "category": "SKILL", "mandatory": True, "preference": "MANDATORY",
            "operator": "AND", "minimum_years": None, "maximum_years": None,
            "confidence": 0.7, "logic_group": None}
        secs = segment_sections(resume_text)
        skills = extract_skills(resume_text, secs)
        exps = extract_experience(resume_text, secs)
        base = match_requirement(r, skills, exps, resume_text,
                                 {"transferable": config.transferable_threshold,
                                  "semantic": config.semantic_threshold})
        st = build_state(r, skills, exps, resume_text, base,
                         config.transferable_threshold)
        states.append(st["vector"])
        expected.append(STATUS_TO_ACTION.get(label, 3))
        mandatory.append(bool(r.get("mandatory", True)))
    return states, expected, mandatory


def train(config: RLConfig, cases: list[dict],
          progress_cb=None) -> tuple[LinearQPolicy, dict]:
    rng = random.Random(config.seed)
    labels = [c.get("expected_status", "MISSING") for c in cases]
    train_idx, test_idx = stratified_split(len(cases), labels, config.test_size, config.seed)

    states, expected, mandatory = build_real_states(cases, train_idx, config)

    # Balance classes with clearly-marked synthetic states (never used in eval).
    synth_states, synth_exp, synth_mand = [], [], []
    synth_rng = random.Random(config.seed)
    for status in STATUS_TO_ACTION:
        vecs = synthetic_states_for(status, config.synthetic_per_class,
                                    config.synthetic_noise, synth_rng)
        for v in vecs:
            synth_states.append(v)
            synth_exp.append(STATUS_TO_ACTION[status])
            synth_mand.append(True)
    all_states = states + synth_states
    all_expected = expected + synth_exp
    all_mandatory = mandatory + synth_mand

    env = RequirementMatchEnv(all_states, all_expected, all_mandatory)
    policy = LinearQPolicy(seed=config.seed)
    lr = config.learning_rate

    total_reward = 0.0
    reward_hist: list[float] = []
    for ep in range(config.episodes):
        frac = min(1.0, ep / max(1, config.epsilon_decay_episodes))
        eps = config.epsilon_start + (config.epsilon_end - config.epsilon_start) * frac
        if ep == 0:
            env.shuffle(rng)
        pos = rng.randrange(len(env))
        state = env.reset(pos)
        if rng.random() < eps:
            action = rng.randrange(policy.n_actions)
        else:
            action, _, _ = policy.predict(state)
        reward, done, info = env.step(action, config)
        assert done
        policy.update(state, action, reward, lr)
        total_reward += reward
        reward_hist.append(reward)
        if progress_cb and ep % 500 == 0:
            progress_cb(ep, config.episodes, total_reward / (ep + 1))

    # Training-set accuracy of the greedy policy (diagnostic only).
    correct = 0
    for s, e in zip(all_states, all_expected):
        a, _, _ = policy.predict(s)
        correct += int(a == e)
    label_counts = dict(Counter(labels))
    metadata = {
        "n_cases": len(cases),
        "n_train_real": len(states),
        "n_synthetic": len(synth_states),
        "synthetic": True,
        "synthetic_note": "Gaussian perturbations of documented per-status prototypes; training only.",
        "train_indices": train_idx,
        "test_indices": test_idx,
        "label_counts": label_counts,
        "episodes": config.episodes,
        "mean_train_reward": round(total_reward / max(1, config.episodes), 4),
        "greedy_train_accuracy": round(correct / max(1, len(all_states)), 4),
        "algorithm": "epsilon-greedy linear Q-learning (contextual bandit, gamma=0)",
        "seed": config.seed,
    }
    return policy, metadata
