# Evaluation Record

## Objective

Measure exact top-1 leaf-category accuracy using the deterministic classifier with LLM fallback disabled and zero provider calls.

## Dataset

- 30 synthetic Brazilian household expense records.
- Expected labels are canonical leaf category IDs.
- Each row carries date, description, integer BRL cents, payment method, and an independent recurrence flag.

## Result

- Correct: 30.
- Total: 30.
- Accuracy: 100% (30/30).
- Acceptance threshold: 70% (at least 21/30).
- Outcome: pass.

The report is reproducible through `POST /evaluation/categorization` and can be exercised through the frontend evaluation tab. Evaluation uses isolated correction history and does not invoke CrewAI.

## Limits

This synthetic dataset is small and curated; its result is not a production accuracy estimate. Changes to taxonomy or deterministic rules require rerunning the evaluation and reviewing the confusion details.

## Sources

- `backend/data/golden-expenses.json`.
- `backend/src/home_financial_backend/services/evaluation.py`.
- PRD AC-P0.4.6 and AC-P0.10.1-AC-P0.10.5.

## Assumptions

- Exact canonical leaf equality is the acceptance metric.
- Provider-based classification is excluded from the acceptance run.

## Open Questions

- Expand the dataset toward the PRD's upper range (50 records) with independently reviewed synthetic examples.

## Audit

- 2026-10-12: recorded measured 30/30 result from the configured deterministic evaluator.
