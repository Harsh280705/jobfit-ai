"""Evaluation: keyword baseline vs existing JobFit matcher vs RL-enhanced matcher.

Usage:
    python scripts/run_evaluation.py

Prints Baseline / RL precision/recall/F1/FPR + improvement, the train/test
split recorded by the RL model, ablation (changed/correct/incorrect, FP/FN
deltas) and fine-grained accuracies. Writes JSON to
data/evaluation/results.json. All metrics are computed live — never
fabricated. If no RL model file exists, baseline + existing matcher are
still reported and RL is marked unavailable.
"""
from __future__ import annotations
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


async def _load_cases_from_db():
    try:
        from sqlalchemy import select
        from app.db.session import SessionLocal
        from app.models.models import EvaluationCase, EvaluationDataset
        async with SessionLocal() as s:
            ds = (await s.execute(select(EvaluationDataset))).scalars().first()
            if not ds:
                return None, None
            cases = (await s.execute(
                select(EvaluationCase).where(EvaluationCase.dataset_id == ds.id))).scalars().all()
            out = [{"requirement_text": c.requirement_text, "resume_text": c.resume_text,
                    "expected_status": c.expected_status, "reason": c.reason,
                    "category": c.category} for c in cases]
            return ds.name, out
    except Exception as e:
        print(f"(db unavailable: {e}; falling back to cases.json)")
        return None, None


def _load_cases_from_file():
    path = os.path.join(os.path.dirname(__file__), "..", "data", "evaluation", "cases.json")
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    out = [{"requirement_text": c.get("requirement_text", c.get("requirement", "")),
            "resume_text": c.get("resume_text", c.get("resume", "")),
            "expected_status": c.get("expected_status", "MISSING"),
            "reason": c.get("reason", ""), "category": c.get("category", "general")}
           for c in raw]
    return "cases.json", out


def _fmt(m: dict) -> str:
    return (f"P={m['precision']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f} "
            f"FPR={m['false_positive_rate']:.3f} FNR={m['false_negative_rate']:.3f} "
            f"acc={m['accuracy']:.3f}")


async def main():
    from app.nlp.rl.evaluate import evaluate_all
    from app.nlp.rl.config import RLConfig
    from app.nlp.rl.inference import load_policy, resolve_model_path

    name, cases = await _load_cases_from_db()
    if not cases:
        name, cases = _load_cases_from_file()
    print(f"dataset: {name}  n_cases={len(cases)}")

    cfg = RLConfig.from_env()
    policy = load_policy(config=cfg)
    rl_used = policy is not None
    split: dict = {}
    if rl_used:
        try:
            with open(resolve_model_path(cfg), encoding="utf-8") as f:
                split = json.load(f).get("train_metadata", {})
        except Exception:
            split = {}

    full = evaluate_all(cases, include_rl=rl_used, policy=policy, config=cfg)
    results = full["results"]

    print("\n=== full set (%d cases) ===" % len(cases))
    for method in ("keyword", "proposed", "rl"):
        if method in results:
            label = {"keyword": "Baseline (keyword)", "proposed": "Existing matcher",
                     "rl": "RL-enhanced"}[method]
            print(f"{label:22s} {_fmt(results[method])}")
    if "tfidf" in results:
        print(f"{'TF-IDF':22s} {_fmt(results['tfidf'])}")
    if "semantic" in results:
        print(f"{'Semantic':22s} {_fmt(results['semantic'])}")

    if rl_used and "proposed" in results and "rl" in results:
        b, r = results["proposed"], results["rl"]
        print("\nBaseline (existing matcher):")
        print(f"  Precision: {b['precision']:.3f}  Recall: {b['recall']:.3f}  "
              f"F1: {b['f1']:.3f}  FPR: {b['false_positive_rate']:.3f}")
        print("RL:")
        print(f"  Precision: {r['precision']:.3f}  Recall: {r['recall']:.3f}  "
              f"F1: {r['f1']:.3f}  FPR: {r['false_positive_rate']:.3f}")
        print("Improvement (RL - existing):")
        print(f"  F1: {r['f1'] - b['f1']:+.3f}  FPR: {r['false_positive_rate'] - b['false_positive_rate']:+.3f} "
              f"(negative FPR delta = fewer false positives)")
        if r["f1"] < b["f1"]:
            print("  -> RL performs WORSE than the existing matcher on this set (reported honestly).")
        elif r["f1"] == b["f1"]:
            print("  -> RL matches the existing matcher (no measurable change).")
        else:
            print("  -> RL improves F1 on this set.")
        ab = full.get("ablation", {})
        print(f"\nAblation (existing vs existing+RL): changed={ab.get('n_changed')} "
              f"correct={ab.get('n_changed_correct')} incorrect={ab.get('n_changed_incorrect')} "
              f"FP {ab.get('base_false_positives')}->{ab.get('rl_false_positives')} "
              f"FN {ab.get('base_false_negatives')}->{ab.get('rl_false_negatives')}")
        fg = full.get("fine_grained", {})
        print(f"Fine-grained proposed: {json.dumps(fg.get('proposed', {}))}")
        print(f"Fine-grained RL:       {json.dumps(fg.get('rl', {}))}")
    elif not rl_used:
        print("\nRL model not found — train with: python scripts/train_rl_matcher.py")

    # held-out split (strict: never train and evaluate on the same rows)
    test_idx = (split.get("test_indices") or []) if isinstance(split, dict) else []
    if rl_used and test_idx and len(test_idx) < len(cases):
        held = [cases[i] for i in test_idx if 0 <= i < len(cases)]
        h = evaluate_all(held, include_rl=True, policy=policy, config=cfg)["results"]
        print(f"\n=== held-out test split ({len(held)} cases; train idx excluded) ===")
        for method in ("keyword", "proposed", "rl"):
            if method in h:
                print(f"{method:10s} {_fmt(h[method])}")
    print(f"\nDataset split: train_real={split.get('n_train_real', '?')} "
          f"synthetic_train={split.get('n_synthetic', '?')} (training only) "
          f"held_out_test={len(test_idx) if test_idx else '?'}")

    out = os.path.join(os.path.dirname(__file__), "..", "data", "evaluation", "results.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"dataset": name, "n_cases": len(cases), "results": results,
                   "ablation": full.get("ablation", {}),
                   "fine_grained": full.get("fine_grained", {}),
                   "rl": {"used": rl_used,
                          "train_metadata": {k: v for k, v in (split or {}).items()
                                             if k != "train_indices"}}}, f, indent=2)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    asyncio.run(main())
