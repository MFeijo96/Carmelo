# Home Financial: Frontend Functional Specification

## Scope

One React/TypeScript/Vite route (`/`) for a local, synthetic-data expense workflow in pt-BR. The frontend calls FastAPI for expenses, categories, CSV import, dashboard, insights, correction, exports, deletion, and evaluation. It does not calculate authoritative totals or invoke an LLM directly. The backend uses in-memory persistence by default; Firestore Emulator is an optional backend mode.

## Inputs

- Required: valid calendar date, trimmed description (1-120 characters), positive BRL amount (maximum R$ 999.999,99), payment method (`dinheiro`, `debito`, `credito`), and either an active leaf category or the `Automatica` categorization mode.
- Amount uses Brazilian notation: `1234,56` or `1.234,56`; at most two decimal places. Convert to integer cents, never floating-point currency arithmetic.
- Optional recurring checkbox, initially unchecked, independent of payment method.
- Categories load from `GET /categories`; manual values are backend category IDs and only active leaves are selectable. A separate `Automatica` option has an empty frontend value and is sent as `category_id: null`; it is never created or stored as a taxonomy category. Existing manual defaults are unchanged. The seeded taxonomy includes Mercado and Restaurantes below Alimentação, Assinaturas below Lazer, and standalone top-level leaves.
- Submit validates before starting. Invalid entries do not create requests. Preserve inputs after failures. Clear description/amount after success; retain date/category/payment/recurrence for repeated entry. Reset restores every field to its initial default.
- A visible local-demo notice requests fictitious data. The management area has separate tabs for CSV import, expense review, categories, data portability/deletion, and evaluation. Login is not represented.
- Trace: PRD AC-P0.3.1/.2/.3/.5; SAD AD-01/AD-06.

## Run

- Lightweight reducer FSM: `idle -> running -> done`; `done -> running` for another submission and `running -> idle` on failure. Reset returns to `idle`, clears the selected result/error/retry snapshot, and retains completed UI history.
- `started` records a client request ID before `startRun` resolves. The submit handler freezes the submitted input; completion carries this request ID separately from the backend expense ID. Duplicate starts while running and completions for another request ID are ignored.
- `startRun` validates then posts `POST /expenses`; it reads `GET /dashboard/monthly?month=YYYY-MM` and the month's pending-review count. It never calls `POST /insights/monthly` or waits for insight generation. `getRunStatus` resolves from the result associated with the created expense ID; the backend has no run-status polling endpoint.
- In `Automatica` mode, category selection is delegated to the existing backend classification precedence and review/fallback behavior, not forced to the provider. Results use the persisted expense's returned `category_id`; history keeps the original submitted selection separately. Provider classification remains conditional on unresolved ambiguity and sufficient safe context.
- A successful create is cached in-session by client request ID until the dashboard read succeeds. Retry reuses that created expense rather than issuing a duplicate POST. Reset/new submission gets a new request ID. An unavailable review count does not fail the saved expense/dashboard operation; the UI uses deterministic summary text without requesting an insight.
- Workflow controls are Run (`Executar`) and an icon-only Reset (`Redefinir`, accessible name and tooltip). Both controls and fields are disabled while requests run; Reset is not cancellation. A shared status map drives banner, running button, empty state, inline error, and completed Results/History labels.
- Backend JSON errors use the shared `data` / `errors` / `meta` envelope. The first pt-BR backend error message is displayed inline. `VITE_API_BASE_URL` can override the default `http://127.0.0.1:8000`.
- The banner displays a real client-local `Atualizado em` timestamp. It updates on mount, Run/Retry, service responses, validation/service errors, and Reset; it never reuses a backend result timestamp as a ticking clock.
- Trace: SAD non-streaming interaction and deterministic service boundary.

## Household Operations

- CSV is uploaded as a raw UTF-8 request body with `Content-Type: text/csv`; the UI displays imported/rejected counts and row-level validation errors.
- Expense review filters by month, category, minimum confidence, payment method, source, and review-needed status. Results use 100-row pages with total count and previous/next controls; category selection calls `PATCH /expenses/{expense_id}/category`.
- Monthly insight generation calls `POST /insights/monthly` only after clicking `Gerar insights do mês` in the Despesas tab. Loading the tab, saving/importing expenses and correcting categories do not generate insights. The button remains disabled while busy, while checking reviews, when reviews are pending, or when the month has no expenses.
- Category settings create leaves under top-level groups, rename custom leaves, and merge custom leaves into an active leaf. Standard categories are not offered for rename or merge.
- CSV and JSON exports download backend-generated content. Deletion targets the demo household only and requires browser confirmation; successful deletion clears visible run history.
- Evaluation calls the deterministic backend endpoint and displays correct/total, accuracy, pass/fail, and confusion-entry count.
- Trace: PRD AC-P0.2/P0.5/P0.6/P0.9/P0.10; SAD API and deterministic service boundaries.

## Results

- Before completion, show an explicit empty/pending state, never fabricated totals.
- On expense completion, display backend monthly totals, expense count, recurring total, category/payment breakdowns, the saved expense, and a deterministic summary of those totals. Provider insights and their returned supporting sources are displayed separately after manual generation in the Despesas tab.
- Totals and breakdowns are authoritative deterministic backend calculations. Insight output can be provider-generated or a deterministic backend fallback; the browser never sends data directly to a provider.
- Completed submissions retain their current-page result snapshots. On page load/refresh, the frontend reconstructs saved-expense results using persisted fields and the backend's current monthly dashboards, not historical point-in-time totals. Reset hides results but does not delete backend records. In memory mode, records remain until the API process restarts; refresh alone never deletes records.
- Trace: PRD AC-P0.3/P0.7/P0.8; SAD AD-03/AD-06.

## History

- Saved expenses are recovered from paginated `GET /expenses` reads on mount, ordered newest-created first, with one dashboard query per distinct month. The most recent saved expense is selected initially; the browser reconstructs pending-review counts from the retrieved expense flags. Recovery performs no POST or insight generation.
- Newly completed current-page submissions retain their submitted input and take priority over delayed restored copies of the same expense. Recovered entries use the persisted description/category, amount and month, including records imported through CSV. Reset does not reselect a restored row; successful demo-data deletion clears history and invalidates outstanding restoration.
- Loading and retryable load-error states distinguish unavailable data from an empty database. Remount/refresh retrieves the backend history again; no financial records are copied into localStorage, cookies, or other browser persistence. The backend persistence mode controls record lifetime.
- No failed or pending run is listed as completed. Selecting a history row does not submit again or modify the form.
- Trace: SAD demo workspace constraints. This is UI run history, not PRD category-correction history.

## Acceptance Checks

- Unit tests: BRL parsing/validation, FSM stale transitions, failure/retry/reset, API request fields/envelopes, dashboard result mapping, active-leaf filtering, backend error propagation, and retry without duplicate POST.
- Component tests: expense run/history plus CSV report, review-filter query mapping, expense correction, category create/rename/merge, evaluation display, export actions, and confirmation before deletion.
- Basic accessibility includes native labeled controls, semantic headings, visible focus, and keyboard navigation. Full WCAG/screen-reader audits are deferred.
- Run `npm test`, `npm run build`, and `npm audit` in `frontend/`. Backend integration requires a loopback API and synthetic records; emulator persistence remains a separate backend gate.
- Artifact self-check: Inputs, Run, Results, History, Spec Sync, Sources, Assumptions, Open Questions, Audit headings exist.

## Spec Sync

Update this checklist after **each commit** affecting the frontend. No commit is created by this task.

- [ ] Record commit SHA/date and changed files below.
- [ ] Reconcile Inputs, API category IDs, validation rules, locale, and defaults.
- [ ] Reconcile Run/Reset/Retry, API calls, FSM, and resilience behavior.
- [ ] Reconcile status presentation and client timestamp triggers.
- [ ] Reconcile backend Results, source summaries, recovered expense history, and current-session snapshots.
- [ ] Update PRD/SAD traceability and explicitly mark remaining deferrals.
- [ ] Run scoped tests/build/audit and record outcomes and known gaps.
- [ ] Update `frontend.md` and `frontend/README.md` when behavior/setup changes.

| Commit / date | Spec changes | Checks / gaps |
| --- | --- | --- |
| Uncommitted / 2026-10-09 | Initial frontend slice | 24 tests, TypeScript/Vite build, zero audit advisories, browser checks passed. |
| Uncommitted / 2026-10-09 | Fixed prototype Run/Reset/Retry and status banner | 27 tests, build, and desktop/mobile geometry passed. |
| Uncommitted / 2026-10-12 | Connected active categories, expense creation, monthly dashboard, and insight APIs | 30 tests and production build passed; live browser submission showed backend totals, category/payment breakdown, and source-backed insight. Emulator persistence remains a backend setting; memory mode resets when API restarts. |
| Uncommitted / 2026-10-12 | Added CSV import, review/correction, category management, export/delete, and evaluation tabs | 41 frontend tests, production build, and npm audit passed; live evaluation returned 30/30; emulator-backed browser flow remains unverified. |
| Uncommitted / 2026-10-12 | Added an OpenAPI contract test | 42 frontend tests pass; the UI may only call operations in `backend/openapi.json`. |

## Sources

- `project-context/1.define/prd.md`: P0.1, P0.3, P0.7, P0.8; pt-BR, BRL, synthetic local workspace.
- `project-context/1.define/sad.md`: AD-01, AD-03, AD-06; React/TypeScript/Vite, server-owned arithmetic, loopback-only demo.
- `backend/src/home_financial_backend/api/routes.py` and `backend/README.md`.

## Assumptions

- The existing manual-entry/run-history experience is retained; API result IDs are backend expense IDs while client request IDs keep session history unique.
- User-story files are absent; PRD IDs are traceability anchors, not a claim that all Build gates have passed.
- The frontend uses the SAD React/TypeScript choice despite root config listing Python as primary.
- The browser keeps rendered history in memory and reloads saved expenses from the backend after refresh; backend persistence mode controls expense lifetime.

## Open Questions

- The read-only history-refresh browser flow was verified against the active emulator-backed API with two persisted expenses. Other emulator-backed browser workflows, independent integration sign-off, authentication, full WCAG evaluation, and production security review remain outstanding.

## Audit

- 2026-10-19; persona: frontend.eng; action: restore-persisted-expense-history. Replaced refresh-cleared history behavior with paginated backend recovery, current authoritative monthly summaries, safe merging, loading/error/retry UI and stale-load invalidation after deletion. Confirmed two backend records remained and both reappeared through consecutive browser reloads without writes or insight generation. Verification: 57 frontend tests, TypeScript/Vite build and touched-file diagnostics pass. No backend data, persistence mode, dependencies, browser storage or commit changed.
- 2026-10-19; persona: frontend.eng; action: expose-automatic-categorization. Added the Automatica selector mode, nullable category serialization and display of the backend-resolved category. Preserved manual choices, input retention/retry and manual-only insight generation. Verification: 53 frontend tests, TypeScript/Vite build and touched-file diagnostics pass. No taxonomy record, backend rule, provider request, dependency or commit added.
- 2026-10-19; persona: frontend.eng; action: make-insights-manual-only. Removed automatic monthly insight requests from expense submission; preserved the explicit generation button, pending-review checks and idempotent retry behavior. Verification: 50 frontend tests and TypeScript/Vite build pass; local frontend HTTP check returns 200. No provider calls, API/schema changes, dependencies or commit added.
- Runtime: `crewai` is configured for the backend; the frontend never invokes it directly.
- No real financial data, secrets, browser storage, or commit were used/created in this integration slice.
- 2026-10-12; action: connect-local-fastapi-and-household-workflows. The UI uses the documented API contract for all local MVP operations; 41 frontend tests and production build passed. No separate persona sign-off is claimed.
