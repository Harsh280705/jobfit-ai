# Matching Logic

## Order of evaluation (per requirement)

1. **Direct evidence**: canonical skill equality (aliases resolved).
2. **Threshold validation**: `minimum_years` vs timeline-backed estimate.
3. **Transferable**: configured ontology relation + strength ≥ threshold
   (e.g. PyTorch↔TensorFlow 0.85), combined with category compatibility.
4. **Contradiction**: explicit year claim exceeds timeline evidence by ≥2y.
5. **Status assignment** with confidence + explanation + evidence spans.

## Statuses

- `FULLY_SATISFIED` — direct evidence meets all constraints.
- `PARTIALLY_SATISFIED` — direct evidence but threshold shortfall
  (e.g. 1.8y vs 3y Python).
- `TRANSFERABLE` — no direct evidence; strong related skill
  (never auto-converted to a direct match; scores 0.4).
- `MISSING` — no evidence.
- `INSUFFICIENT_EVIDENCE` — vague/semantic-only signal (e.g. "cloud
  deployments" for Kubernetes); never inferred as a match.
- `CONTRADICTORY` — claim conflicts with timeline.

## Examples

- `3+ years Python` + 1.5y evidence → `PARTIALLY_SATISFIED`.
- `PyTorch` + TensorFlow evidence → `TRANSFERABLE` (strength 0.85).
- `Python AND SQL`, SQL absent → group not fully satisfied.
- `Python OR Java`, Python present → group satisfied.
- Education uses rank ordering (PhD > Master's > Bachelor's).

## Scoring

```
mandatory 40% · preferred 15% · experience 20% ·
skill 15% · transferability 5% · confidence 5%
```

**Mandatory gate**: any `MISSING`/`CONTRADICTORY` mandatory requirement caps
overall at 59%; partial-only mandatory caps at 79%. All weights and thresholds
are env-configurable.
