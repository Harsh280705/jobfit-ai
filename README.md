# JobFit AI — Constraint-Aware Requirement-Level Candidate–Job Matching

Traditional ATS: resume → embedding → similarity → "82% match". Opaque, easy to game,
blind to mandatory-vs-preferred, thresholds, AND/OR logic, and evidence quality.

JobFit AI instead decomposes the job into **atomic requirements**, classifies
**mandatory/preferred + constraints** (AND/OR, years, education), extracts
**evidence-backed candidate facts**, and matches **requirement by requirement**
with traceable explanations. The overall score is secondary and **gated on
mandatory requirements**.

## Problem statement

Single similarity scores hide *why* a candidate fits: they over-credit preferred
skills, ignore year thresholds, conflate related skills with direct evidence, and
produce false positives on mandatory requirements.

## Why this approach

- Requirement-level verdicts (`FULLY_SATISFIED`, `PARTIALLY_SATISFIED`,
  `TRANSFERABLE`, `MISSING`, `INSUFFICIENT_EVIDENCE`, `CONTRADICTORY`) with
  evidence snippets and confidence — never an opaque `0.83`.
- Constraint engine: AND/OR/nested logic trees, experience thresholds from dated
  timelines (no double counting, no fabricated years), education ranking.
- Transferability is explicit and discounted, never silently a direct match.
- Research mode compares against keyword / TF-IDF / semantic baselines with
  measured precision/recall/F1/false-positive rates.

## Architecture

See `docs/ARCHITECTURE.md` (includes Mermaid diagram), `docs/NLP_PIPELINE.md`,
`docs/MATCHING_LOGIC.md`, `docs/RESEARCH.md`, `docs/API.md`.

```
Resume + JD → Document Processing → Resume Extraction + Requirement Extraction
→ Normalization → Constraint/Logic Engine → Matching (direct / experience /
transferable / contradiction) → Explainable Report → React Dashboard
```

## Tech stack

- Frontend: React + Vite + TypeScript + Tailwind + React Router + TanStack Query + Recharts
- Backend: Python + FastAPI + Pydantic v2 + SQLAlchemy 2.x + Alembic + PostgreSQL + pgvector
- Async: Redis + Celery (inline fallback when broker unavailable)
- NLP: spaCy (optional) + sentence-transformers (optional, CPU) + TF-IDF fallback + regex;
  Ollama LLM layer optional and validated with Pydantic

## Setup

```bash
cp .env.example .env        # fill in values; never commit secrets
docker compose up --build   # frontend :5173, backend :8000, postgres, redis, worker
```

Local dev (without Docker):

```bash
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
cd ../frontend && npm install && npm run dev
# worker (optional; analyses fall back to inline without Redis):
cd backend && celery -A app.workers.celery_app.celery worker --loglevel=info
```

## Environment variables

See `.env.example`: `DATABASE_URL`, `REDIS_URL`, `EMBEDDING_MODEL`,
`OLLAMA_BASE_URL`/`OLLAMA_MODEL`/`OLLAMA_ENABLED`, `FILE_STORAGE_PATH`,
`MAX_UPLOAD_SIZE`, `LOG_LEVEL`, scoring weights (`WEIGHT_*`), thresholds.

## Development vs production configuration

- Docker Compose runs **development** servers (Vite dev on `:5173`, uvicorn
  on `:8000` without TLS) — suitable for local demo, not hardened production.
- CORS allows only the explicit origins in `BACKEND_CORS_ORIGINS`
  (default: `http://localhost:5173,http://localhost:3000`). Set it to your
  exact frontend origin(s) for any network-exposed deployment; wildcard
  origins are never used with credentials.
- Change `POSTGRES_PASSWORD` and use a managed secret store before exposing
  the stack. Never commit `.env` (see `SECURITY.md` for reporting issues
  without sharing secrets or real resumes).

## Running locally / Docker

- Full stack: `docker compose up` (or `make up`)
- Backend only: `make backend` · Frontend only: `make frontend` · Worker: `make worker`

## API overview

Versioned at `/api/v1` (full reference in `docs/API.md`, live OpenAPI at `/docs`):

```
POST /documents/upload · GET/DELETE /documents/{id}
POST /resumes · GET /resumes/{id}
POST /jobs · GET /jobs/{id}
POST /analyses {resume_id, job_description_id} → {analysis_id, QUEUED}
GET /analyses · GET /analyses/{id} (poll to COMPLETED) · DELETE
GET /analyses/{id}/requirements[ /{req_id}] · GET /analyses/{id}/matches
POST /evaluation/run · GET /evaluation/results
GET /health · GET /ready
```

## NLP pipeline / matching methodology

`docs/NLP_PIPELINE.md` and `docs/MATCHING_LOGIC.md`. Key rules: deterministic
matching first, semantic similarity only as a secondary signal; missing dates →
`INSUFFICIENT_EVIDENCE`; claim-vs-timeline gaps → `CONTRADICTORY`; every decision
carries `requirement + evidence + location + direct/related + threshold check +
reason + confidence`.

## Research methodology / dataset / evaluation

`docs/RESEARCH.md`. Dataset: `data/sample_resumes/` (12 synthetic fixtures),
`data/sample_jobs/` (10 synthetic fixtures), `data/evaluation/cases.json`
(26 unique requirement-level annotations incl.
exact/alias/partial/missing/transferable/OR/AND/education/dates/contradiction;
deduplicated from an earlier 65-row version that repeated one case 40×).
Run `python scripts/seed_data.py`, then `python scripts/run_evaluation.py` or
`POST /evaluation/run` / Research dashboard. All metrics are computed live —
never fabricated. Synthetic data limitations are documented, not overstated.

Latest synthetic results (`data/evaluation/results.json`, 26 cases):
keyword F1=0.571, existing matcher F1=0.815 (acc=0.808), RL F1=0.786
(RL slightly below base on this small set — reported honestly; held-out
8 cases tie at F1=0.667). No real-world generalization claimed.

## Database migrations / seed / run / test / eval commands

```bash
cd backend
# NOTE: alembic/versions/ has no revisions yet; dev/Docker startup creates
# tables via Base.metadata.create_all in app/main.py lifespan. `alembic upgrade
# head` is a no-op until an initial revision is generated.
python ../scripts/seed_data.py
python ../scripts/build_skill_ontology.py
python ../scripts/run_evaluation.py
pytest -q
```

## Example end-to-end analysis

Input — resume `Python, TensorFlow, 1.5y ML, Bachelor's`; job `3+y Python,
PyTorch required, 3+y ML, Master's preferred, Python AND SQL`:

```
Python      → PARTIALLY_SATISFIED (1.5y vs 3y; direct evidence shown)
PyTorch     → TRANSFERABLE (TensorFlow relation 0.85; upskilling note)
3+y ML      → PARTIALLY_SATISFIED
Master's    → MISSING (candidate: Bachelor's)
Python+SQL  → NOT FULLY SATISFIED (SQL absent; mandatory gate caps overall ≤59%)
```

UI shows evidence + explanation per row; `GET /analyses/{id}` returns the same.

## Limitations / future work

- Synthetic seed data; needs a larger human-annotated benchmark.
- spaCy model + ST embeddings optional to stay laptop-friendly (CPU, no GPU).
- OCR fallback for scanned PDFs, richer NER, pgvector ANN tuning, auth/rate
  limits hardening, and longitudinal hiring-outcome studies are future work.

## AI safety / trust

Only job-relevant qualifications are scored. No gender/religion/race/caste/
politics/health inference. Resumes are treated as sensitive (size/MIME/path
validation, no full-text logging, no stack traces to the UI).
Public sample resumes and job descriptions under `data/` are synthetic test
fixtures (example.com contacts, placeholder profiles) — do not upload real
personal resumes to public demos or issue reports.
