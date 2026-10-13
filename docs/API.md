# API Overview

Base: `/api/v1`. OpenAPI at `/docs` (FastAPI auto-generated).

## Documents

- `POST /documents/upload` (multipart `file` + `document_type`) → `{id, …}`
- `GET /documents/{id}` → metadata + extracted text
- `DELETE /documents/{id}`

## Resumes / Jobs

- `POST /resumes` `{document_id? | text}` → `{id, raw_text}`
- `GET /resumes/{id}`
- `POST /jobs` `{document_id? | title, text?}` → `{id, title, raw_text}`
- `GET /jobs/{id}`

## Analyses (async)

- `POST /analyses` `{resume_id, job_description_id}` → `{analysis_id, status: QUEUED}`
- `GET /analyses` → recent list with overall scores
- `GET /analyses/{id}` → `{status, progress, timings, score, requirements, matches}`
  (each match additively carries `existing_status, rl_status, final_status,
  rl_confidence, rl_changed_decision, rl_used`; absent/False on pre-RL rows —
  old consumers are unaffected)
- `DELETE /analyses/{id}`
- `GET /analyses/{id}/requirements`
- `GET /analyses/{id}/requirements/{req_id}` → requirement + match detail
- `GET /analyses/{id}/matches`
- `POST /analyses/{id}/gap-analysis` → Resume Gap Analysis derived strictly
  from the stored requirement matches (no re-matching): `{critical_gaps,
  preferred_gaps, transferable_skills, insufficient_evidence,
  covered_requirements, honesty_note, summary}` with
  `summary = {total_requirements, covered_count, critical_gap_count,
  preferred_gap_count, transferable_count, insufficient_evidence_count,
  coverage_percentage, overall_message}`. 409 unless the analysis is
  COMPLETED. Suggestions are conditional ("If you have genuine …") and never
  fabricate candidate experience.

## Evaluation

- `POST /evaluation/run` → `{dataset, n_cases, results: {keyword, tfidf, semantic, proposed[, rl]}, ablation, fine_grained, held_out, rl: {used, split}}`
  (`rl` comparison appears only when a trained model file is present)
- `GET /evaluation/results` → dataset preview

## Health

- `GET /health`, `GET /ready`

## Example

```bash
curl -X POST localhost:8000/api/v1/resumes -H 'Content-Type: application/json' -d '{"text":"Python backend…"}'
curl -X POST localhost:8000/api/v1/jobs -H 'Content-Type: application/json' -d '{"title":"ML Engineer","text":"3+ years Python required…"}'
curl -X POST localhost:8000/api/v1/analyses -H 'Content-Type: application/json' -d '{"resume_id":"<r>","job_description_id":"<j>"}'
curl localhost:8000/api/v1/analyses/<analysis_id>
```
