# Integration Record

## Scope

The React application integrates with the local FastAPI API. The browser does not access Firestore or an LLM provider directly. All requests use the configured loopback API base URL; the default is `http://127.0.0.1:8000`.

## Contract

FastAPI OpenAPI at `/openapi.json` is the machine-readable contract, committed as `backend/openapi.json`. A backend test fails when it drifts from the running API, and a frontend test fails when any client call targets an operation absent from it. JSON endpoints return `data`, `errors`, and `meta` with `request_id` and `schema_version`. CSV import sends raw UTF-8 CSV with `Content-Type: text/csv`; CSV export is a file response with schema/household/date metadata headers.

The frontend uses `/households/demo`, `/categories`, `/expenses`, `/imports/csv`, `/dashboard/monthly`, `/insights/monthly`, `/exports/expenses.csv`, `/exports/archive.json`, `/households/{id}/demo-data`, and `/evaluation/categorization`. Category corrections and taxonomy changes use the documented PATCH/POST routes.

## Flows

- Manual expense creation followed by dashboard and best-effort insights.
- CSV upload with imported/rejected counts and row-level errors.
- Monthly expense review, active-leaf correction, and category create/rename/merge.
- CSV/JSON download, confirmed demo-data deletion, and deterministic evaluation report.

## Verification

- Frontend API and component tests cover request mapping, error envelopes, imported-row reporting, correction, taxonomy operations, exports, deletion confirmation, and evaluation display.
- A local synthetic browser smoke test previously verified expense-to-dashboard-to-insight behavior.
- The live evaluation tab returned 30/30 exact matches and displayed the category confusion entries.
- Current automated checks: 42 frontend tests and build pass; backend suite has 40 passing tests and 3 emulator tests skipped without `FIRESTORE_EMULATOR_HOST` (43 pass with the emulator).

## Known Gaps

No independent integration-persona sign-off is recorded. An HTTP smoke run against the Firestore Emulator confirmed CSV import (valid row imported, invalid row rejected with field errors), exact dashboard totals, export, and deletion. The browser UI itself has not been exercised against emulator mode.

## Sources

- `project-context/1.define/prd.md` P0.2-P0.10.
- `project-context/1.define/sad.md` API and deployment architecture.
- `backend/src/home_financial_backend/api/routes.py` and `frontend/src/services/household.ts`.

## Assumptions

- The single seeded demo household is the only frontend workspace.
- API schemas remain the source of truth; browser values do not replace deterministic backend calculations.

## Open Questions

- Re-run the browser flows against emulator mode before any hosted use.
- A separate engineer review of the shared contract has not been recorded.

## Audit

- AAMAD_TARGET_RUNTIME: crewai.
- 2026-10-12: implemented and tested local API workflows; no production integration or external service credentials used.
