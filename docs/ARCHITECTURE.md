# Architecture — JobFit AI

Constraint-aware, requirement-level candidate–job matching. Primary output is a
per-requirement explainable verdict; the overall score is secondary and gated on
mandatory requirements.

```mermaid
flowchart TD

A[Resume + Job Description] --> B[Document Processing]

B --> C[Resume Information Extraction]
B --> D[Job Requirement Extraction]

D --> E[Requirement Normalization]
E --> F[Constraint / Logic Engine]

C --> G[Candidate Evidence Store]

G --> H[Matching Engine]
F --> H

H --> I[Direct Match]
H --> J[Experience Validation]
H --> K[Transferable Skill Engine]
H --> L[Contradiction Detection]

I --> M[Final Requirement Status]
J --> M
K --> M
L --> M

M --> N[Explainable Report]
N --> O[React Dashboard]
```

RL decision layer (additive, optional):

```mermaid
flowchart LR
H[Matching Engine] --> B[Base requirement decision]
B --> S[State builder: existing NLP features]
S --> P[RL policy: linear Q]
P --> G[Guardrails: mandatory / contradiction /\n education / experience / AND-OR]
G --> M[Final Requirement Status]
```

`app/nlp/rl/` holds `config.py`, `state_builder.py`, `reward.py`,
`environment.py`, `policy.py`, `trainer.py`, `inference.py`, `evaluate.py`.
The deterministic matcher stays the entry point
(`matcher/engine.py::match_requirement`); `services/analysis.py` applies
`rl/inference.py::decide_requirement` per requirement only when
`RL_ENABLED=true` and a model file exists — otherwise the base decision is
persisted unchanged (fallback). Scoring (`matcher/scoring.py`) consumes the
final status exactly as before, so the mandatory gate is unaffected.

## Layers

- `app/api/v1` — thin HTTP routes (validation, status codes, no NLP logic).
- `app/services` — orchestration (`analysis.py`), storage abstraction.
- `app/nlp` — parsers, extractors, ontology, experience engine, matcher, embeddings, LLM.
- `app/models` / `app/db` — SQLAlchemy 2.x, Alembic, Postgres+pgvector (SQLite fallback for tests).
- `app/workers` — Celery; falls back to inline execution when Redis is down.
- `frontend` — React+Vite+TS dashboard (upload → poll → requirement report → research).

## Async analysis lifecycle

`QUEUED → PROCESSING → COMPLETED | FAILED`, with `progress` and per-stage
`timings` (candidate extraction, requirement extraction, matching, total) persisted
on the `analyses` row. The frontend polls `GET /analyses/{id}`.
