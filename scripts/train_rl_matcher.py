"""Train the RL requirement-matching policy.

Usage:
    python scripts/train_rl_matcher.py [--episodes 2000] [--seed 42]
                                       [--out backend/app/nlp/rl/models/rl_policy.json]

1. Loads data/evaluation/cases.json (labels = expected_status).
2. Builds RL states through the EXISTING pipeline (no invented features).
3. Stratified train/test split by seed (held-out indices saved in metadata).
4. Trains epsilon-greedy linear Q-learning (CPU, deterministic).
5. Saves policy JSON + prints training statistics.

The saved model is small JSON (no large artifacts to commit).
"""
from __future__ import annotations
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


def load_cases() -> list[dict]:
    path = os.path.join(os.path.dirname(__file__), "..", "data", "evaluation", "cases.json")
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    # normalize both key styles: {"requirement","resume"} and {"requirement_text","resume_text"}
    out = []
    for c in raw:
        out.append({
            "requirement_text": c.get("requirement_text", c.get("requirement", "")),
            "resume_text": c.get("resume_text", c.get("resume", "")),
            "expected_status": c.get("expected_status", "MISSING"),
            "reason": c.get("reason", ""),
            "category": c.get("category", "general"),
        })
    return out


def main() -> None:
    from app.nlp.rl.config import RLConfig
    from app.nlp.rl.trainer import train

    ap = argparse.ArgumentParser(description="Train RL requirement-matching policy")
    ap.add_argument("--episodes", type=int, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--lr", type=float, default=None)
    ap.add_argument("--out", type=str, default=None)
    ap.add_argument("--test-size", type=float, default=None)
    ap.add_argument("--synthetic-per-class", type=int, default=None)
    args = ap.parse_args()

    cfg = RLConfig.from_env()
    if args.episodes is not None:
        cfg.episodes = args.episodes
    if args.seed is not None:
        cfg.seed = args.seed
    if args.lr is not None:
        cfg.learning_rate = args.lr
    if args.test_size is not None:
        cfg.test_size = args.test_size
    if args.synthetic_per_class is not None:
        cfg.synthetic_per_class = args.synthetic_per_class
    out = args.out or os.environ.get("RL_MODEL_PATH") or cfg.model_path
    if not os.path.isabs(out):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        out = os.path.join(repo_root, out)

    cases = load_cases()
    print(f"loaded {len(cases)} cases from data/evaluation/cases.json")

    def progress(ep: int, total: int, mean_r: float) -> None:
        print(f"  episode {ep}/{total}  mean_reward={mean_r:.3f}")

    policy, metadata = train(cfg, cases, progress_cb=progress)
    policy.save(out, config_dict=cfg.to_dict(), train_metadata=metadata)

    print("\n--- training statistics ---")
    print(f"algorithm:            {metadata['algorithm']}")
    print(f"episodes:             {metadata['episodes']}")
    print(f"seed:                 {metadata['seed']}")
    print(f"real train cases:     {metadata['n_train_real']}")
    print(f"synthetic train rows: {metadata['n_synthetic']} (training only, documented)")
    print(f"held-out test idx:    {len(metadata['test_indices'])} cases")
    print(f"label distribution:   {metadata['label_counts']}")
    print(f"mean train reward:    {metadata['mean_train_reward']}")
    print(f"greedy train acc:     {metadata['greedy_train_accuracy']}")
    print(f"reward config:        correct={cfg.reward.correct} mand_sat={cfg.reward.correct_mandatory_satisfied} "
          f"mand_miss={cfg.reward.correct_mandatory_missing} fp={cfg.reward.false_positive} "
          f"fn={cfg.reward.false_negative} transfer={cfg.reward.wrong_transferable} "
          f"contra={cfg.reward.wrong_contradiction} other={cfg.reward.wrong_other}")
    print(f"saved model:          {out}")
    print(f"test indices:         {metadata['test_indices']}")


if __name__ == "__main__":
    main()
