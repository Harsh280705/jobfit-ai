# NLP Pipeline

```
document → text extraction → section segmentation → entity extraction
→ normalization → requirement decomposition → embedding
→ evidence retrieval → constraint evaluation → matching → explanation
```

1. **Text extraction** (`nlp/parsers/documents.py`): PyMuPDF → DOCX → text.
   Common representation `{document_id, document_type, text, pages, sections, metadata}`.
2. **Section segmentation**: heading regex over a fixed vocabulary
   (Skills/Experience/Education/Projects/…); robust to missing headings.
3. **Resume entity extraction** (`nlp/extractors/resume.py`): contact regexes,
   skill mentions with ±60-char evidence spans, dated experience blocks,
   degree patterns, certifications, projects. Every fact keeps `source_text`,
   `source_section`, `confidence`.
4. **Requirement decomposition** (`nlp/extractors/requirements.py`): sentence
   segmentation (spaCy when available, deterministic fallback), skill spotting via
   ontology aliases, mandatory/preferred cues, `N+ years` thresholds, education
   detection, OR-group detection (`A or B`), expression-tree builder.
5. **Normalization** (`nlp/ontology/skills.py`): `Postgres→PostgreSQL`,
   `K8s→Kubernetes`, etc.; categories; typed relationships
   (ALIAS/SAME_FAMILY/RELATED/TRANSFERABLE/DEPENDENCY/SUPERSET/SUBSET).
6. **Embeddings** (`nlp/embeddings/similarity.py`): sentence-transformers when
   installed (CPU), otherwise TF-IDF/token-overlap fallback. Used only as a
   secondary signal — never the sole decision.
7. **Experience engine** (`nlp/matcher/experience.py`): month-resolution interval
   merging (no double counting), per-skill estimates with confidence,
   claim-vs-timeline contradiction detection. Missing dates →
   `INSUFFICIENT_EVIDENCE`, never fabricated years.
8. **Matching** (`nlp/matcher/engine.py`): direct → threshold/dates →
   transferable → contradiction → status, always with evidence + explanation.
9. **Optional LLM** (`nlp/llm/ollama.py`): Ollama parses ambiguous requirements
   into validated Pydantic JSON; fully optional, deterministic pipeline otherwise.

## Reinforcement Learning-Based Matching Policy (experimental)

An additive decision layer (`nlp/rl/`), not a replacement: the base matcher
above still produces every decision, and the RL policy only re-labels the
requirement status inside a constraint-valid subset.

1. **Why RL**: requirement outcomes depend on interacting signals (direct
   evidence × thresholds × transferability × contradictions). A learned
   policy can weigh these jointly; it is evaluated as an experiment, and the
   system reports honestly when it does not improve on the base matcher.
2. **State** (`rl/state_builder.py`, 17 normalized features, all from the
   existing pipeline): mandatory flag, years-required flag + normalized years,
   direct-match flag, transferable flag + max strength, semantic score,
   estimated-years norm, experience gap in [-1,1], evidence-count norm, mean
   evidence confidence, contradiction flag, education flag + satisfied flag,
   OR-group flag, base confidence, base-is-positive.
3. **Actions** (same six categories the matcher produces): `FULLY_SATISFIED`,
   `PARTIALLY_SATISFIED`, `TRANSFERABLE`, `MISSING`, `INSUFFICIENT_EVIDENCE`,
   `CONTRADICTORY`.
4. **Reward** (`rl/reward.py`, configurable): +1 correct, +2 correct mandatory
   satisfied/missing, −3 false positive, −1 false negative, −2 wrong
   transferable, −2 wrong contradiction. Starting points, not optima.
5. **Training** (`scripts/train_rl_matcher.py`): epsilon-greedy linear
   Q-learning (contextual bandit, gamma=0; ~120 params, numpy only, seeded,
   CPU). Real states come from `data/evaluation/cases.json` via the existing
   pipeline under a stratified train/test split; minority classes are
   balanced with clearly-marked synthetic prototype states used for training
   only. Model saved as small JSON to `backend/app/nlp/rl/models/`.
6. **Inference** (`rl/inference.py`): base decision → state → policy argmax
   with softmax confidence → guardrails → final status. Guardrails forbid:
   overriding `CONTRADICTORY`, upgrading unmet education, claiming `FULLY`
   below/unverifiable thresholds, positive labels with no evidence, and
   `MISSING` when direct evidence exists. Low-confidence outputs keep the
   base decision; missing model/disabled flag falls back silently.
7. **Evaluation**: `scripts/run_evaluation.py` and `POST /evaluation/run`
   report keyword / TF-IDF / semantic / existing / RL with accuracy,
   precision, recall, F1, FPR, FNR, confusion counts, ablation
   (changed/correct/incorrect, FP/FN deltas) and fine-grained accuracies,
   on both the full set and the held-out split.
8. **Limitations**: 65 heavily-skewed seed cases (50 FULLY_SATISFIED, many
   duplicated Python rows); linear policy; synthetic balancing is an
   acknowledged bias source; no claim of general superiority — see
   `docs/RESEARCH.md` for measured numbers.
