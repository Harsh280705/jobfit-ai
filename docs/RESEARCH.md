# Research Methodology

## Problem

How can requirement-level and constraint-aware NLP reduce false-positive
candidate–job matches compared with keyword and embedding-based approaches?

## Hypothesis

Requirement decomposition + constraint evaluation + evidence matching +
transferable-skill reasoning reduces false-positive job-fit classifications vs
pure keyword overlap and semantic similarity.

## Design (measurable claims only)

- Requirement-level classification accuracy improves.
- False-positive rate on mandatory requirements drops.
- Explanations are evidence-grounded (every decision carries spans + reason).

## Experiment

Same annotated dataset (`data/evaluation/cases.json`, 26 unique cases across
exact/alias/partial/missing/transferable/OR/AND/education/dates/contradiction;
deduplicated — earlier 65-row version contained 39 repeats of one ETL case):

- Baseline A: keyword overlap
- Baseline B: TF-IDF cosine
- Baseline C: sentence-embedding cosine
- Proposed: requirement decomposition + constraint evaluation + evidence
  matching + experience reasoning + transferability + explainability

Metrics per method: accuracy, precision, recall, F1, false-positive rate,
false-negative rate + confusion counts. Run via `POST /evaluation/run`,
`python scripts/run_evaluation.py`, or the Research dashboard (CSV/JSON export).

## Baseline decision thresholds (fixed, documented, not tuned per dataset)

- Keyword: token overlap ≥ 0.50 → positive
- TF-IDF: cosine ≥ 0.30 → positive
- Semantic: cosine ≥ 0.62 (or ≥ 0.30 when falling back to TF-IDF without ST models)

Seed results (recomputed live; see `data/evaluation/results.json`, synthetic
26-case set): keyword over-matches some groups yet under-recalls
(P=0.750 R=0.462 F1=0.571 FPR=0.154), embedding cutoffs under-match short
requirement snippets (TF-IDF/semantic F1=0.000 without ST models), while the
existing matcher balances both via constraint evaluation (P=0.786 R=0.846
F1=0.815 FPR=0.231 acc=0.808). The RL policy scores slightly lower on this
small synthetic set (P=0.733 R=0.846 F1=0.786 FPR=0.308 acc=0.769; held-out
8 cases: existing and RL tie at F1=0.667) — reported honestly per the rule
below. Fine-grained: transferable 0.667 for both; missing-requirement 0.000
(existing) vs 0.571 (RL).

## Limitations

Synthetic seed data does not represent real-world performance; all figures are
computed live from the dataset — never fabricated.

## Reinforcement Learning-Based Matching Policy (experiment)

**Question**: can a learned requirement-level decision policy that jointly
weighs the existing matcher's signals reduce matching errors compared with
the hand-written decision order?

- **State**: 17 normalized features from the existing pipeline only
  (`app/nlp/rl/state_builder.py` documents each one).
- **Actions**: the same six requirement statuses the matcher produces.
- **Reward**: +1 correct, +2 correct mandatory decisions, −3 false positive,
  −1 false negative, −2 wrong transferable/contradiction (configurable
  starting points, not optima; see `app/nlp/rl/reward.py`).
- **Algorithm**: epsilon-greedy linear Q-learning framed as a contextual
bandit (single-step episodes, gamma=0). Chosen because 26 skewed cases
cannot justify deep RL; the model is ~120 parameters, numpy-only,
  seeded and CPU-friendly.
- **Training**: `python scripts/train_rl_matcher.py` — stratified
  train/test split recorded in the model metadata; synthetic prototype
  states balance minority classes for training only and are never
  evaluated.
- **Inference**: guardrailed policy (`app/nlp/rl/inference.py`); constraints
  (mandatory gate, AND/OR, education, experience, contradiction) stay
  authoritative; fallback to the base matcher when the model is absent.
- **Methodology**: `python scripts/run_evaluation.py` (or
  `POST /evaluation/run`, or the Research dashboard) compares keyword /
  TF-IDF / semantic / existing / RL with accuracy, precision, recall, F1,
  FPR, FNR, confusion counts, ablation (how many decisions changed, how
  many changes were correct/incorrect, FP/FN deltas) and fine-grained
  accuracies (mandatory, transferable, missing) on the full set and the
  held-out split. Train and test rows never overlap.
- **Honesty rule**: if RL scores lower than the existing matcher, that is
  reported as-is; reward values and thresholds are not re-tuned per dataset
  to force a win. The RL layer is described as an experimentally evaluated
  learned decision policy — not as guaranteed intelligence or novelty.
