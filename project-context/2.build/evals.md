# Evaluation Record

## Objective

Measure exact top-1 leaf-category accuracy using the deterministic classifier with LLM fallback disabled and zero provider calls.

## Dataset

- 50 synthetic Brazilian household expense records (`home-financial-golden-v2`).
- Expected labels are canonical leaf category IDs.
- Each row carries date, description, integer BRL cents, payment method, and an independent recurrence flag.

## Result

- Correct: 50.
- Total: 50.
- Accuracy: 100% (50/50).
- Acceptance threshold: 70% (at least 35/50).
- Outcome: pass.

The report is reproducible through `POST /evaluation/categorization` and the frontend evaluation tab. The browser run reported 14 category-level confusion entries and completed in 5 ms according to the API event log. Evaluation uses isolated correction history, and the service constructs the classifier with fallback disabled.

## Limits

This synthetic dataset is curated and includes descriptions that align with deterministic rules; its result is not a production accuracy estimate or independent label review. Changes to taxonomy or deterministic rules require rerunning the evaluation and reviewing the confusion details.

## Evaluation Checks Implemented

- The fixture now has 50 canonical leaf labels across all payment methods and both recurrence states; it uses synthetic data only.
- Automated tests cover repeatable metrics, confusion totals, exact 70% pass and below-threshold fail, invalid/parent category labels, unavailable dataset versions, and disabled classifier fallback.
- The live frontend evaluation passed with fallback/provider disabled. Provider fallback behavior remains covered separately by mocked adapter tests.
- No LLM judge was added. Insight safety and grounding continue to use schema/source checks and human review; cost remains tracking-only until an operator sets a budget.

## Remaining Evaluation Work

- Obtain independent human review of the expected labels and broaden the input distribution beyond rule-aligned examples before treating accuracy as representative.
- Re-run under CI with the Firestore Emulator only where persistence behavior is under test; the acceptance evaluator itself remains deterministic and LLM-free.
- Cost has no pass/fail threshold yet; continue recording available usage metadata without inventing a budget.

## Sources

- `backend/data/golden-expenses.json`.
- `backend/src/home_financial_backend/services/evaluation.py`.
- PRD AC-P0.4.6 and AC-P0.10.1-AC-P0.10.5.

## Assumptions

- Exact canonical leaf equality is the acceptance metric.
- Provider-based classification is excluded from the acceptance run.

## Open Questions

- Obtain independent label review and an operator-approved cost ceiling if cost becomes a release gate.

## Audit

- 2026-10-12: recorded historical measured 30/30 result from the configured deterministic evaluator.
- 2026-10-23: expanded the fixture to v2/50 records; deterministic acceptance measured 50/50, 100%, under 30 seconds. Added boundary, repeatability, invalid-label/version, and fallback-disabled regression tests.
