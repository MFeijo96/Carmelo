# Home Financial: Frontend Build Record

## Implementation

- Functional contract: `project-context/2.build/frontend-funcional-spec.md`.
- `frontend/`: React 19, TypeScript, Vite, Tailwind 4, Lucide icons. One route, `/`, with pt-BR manual expense entry, results/history, CSV import, expense review/correction, category management, exports/deletion, and evaluation.
- `src/workflow.ts`: backend category IDs, integer-cent input validation, reducer FSM, and BRL/month formatting.
- The new-expense category selector includes `Automatica`: validation accepts the empty mode value and the API sends `category_id: null`. The returned persisted category is shown in results while history preserves the submitted mode. This is not a stored category; backend rules/history/provider precedence and review flags remain authoritative. Manual defaults are unchanged.
- `src/services/runs.ts`: default service loads categories, calls `POST /expenses`, and reads `GET /dashboard/monthly` plus the month's pending-review count. Expense submission never requests monthly insights. `createRunService` remains a fixture for UI state tests only.
- `src/services/household.ts` and `src/WorkspaceTools.tsx`: typed API operations for CSV import, paginated expense filters/correction, category create/rename/merge, CSV/JSON export, confirmed data deletion, and golden evaluation.
- Monthly insight generation is manual-only via `Gerar insights do mês` in the Despesas tab, retaining review/loading/empty-month guards; saving an expense shows the deterministic totals summary without waiting for insight generation.
- `src/App.tsx`: dynamically loads active leaf categories, validates inputs, keeps Run/Reset/Retry and history UX, and renders backend totals, expense, insight, and source summary.
- A top live banner displays `Crew: idle/running/done/error`, with gray/blue/green/red indicators. Error is a presentation of service/validation errors; the FSM remains idle/running/done.
- `Atualizado em` is a client timestamp updated on mount, Run/Retry, service responses, errors, and Reset.
- History has unique client request IDs and submitted input snapshots. A pending successful POST is reused on same-request retry if the dashboard request fails, preventing a duplicate expense.
- Reset clears the form/result/error/retry context but does not delete backend expenses. Refresh now reloads saved expenses through paginated `GET /expenses` plus current monthly dashboards, restores newest-first history and selects the latest saved record. Current-session submissions take precedence over delayed restored copies; backend deletion invalidates pending restoration. Loading and retryable errors are explicit. No browser-persisted financial copy or automatic insight generation is introduced; backend persistence controls record lifetime.

## Traceability And Deferrals

| Source | Implemented slice / limit |
| --- | --- |
| PRD AC-P0.2 | CSV file upload displays accepted/rejected counts and row-level errors. |
| PRD AC-P0.3.1/.2/.3/.5, P0.7 | Manual form uses backend expense creation; results show deterministic totals, category/payment breakdowns, and recurring amount. |
| PRD AC-P0.5/P0.6 | Expense category correction and custom category create/rename/merge use backend APIs. |
| PRD P0.8/P0.9/P0.10, SAD AD-03 | Insight sources, CSV/JSON export, confirmed deletion, and exact-label evaluation report are available. |
| SAD AD-01, AD-06 | React/TypeScript/Vite, loopback-only local demo, fictitious-data notice. |

Authentication, complete WCAG evaluation, full emulator-backed frontend smoke coverage, and production security review remain out of this local-only slice. Read-only history recovery was checked in the browser against the active Firestore Emulator API. The frontend never connects directly to Firestore or CrewAI.

## Verification

- `npm test`: 57 tests pass across component, workflow, API-service, and OpenAPI contract tests, including remount recovery, paginated history, retryable load errors and preservation of newer session results.
- `npm run build`: strict TypeScript check and Vite production build pass.
- `npm audit`: zero vulnerabilities in the last audit; frontend integration adds no packages.
- Live browser check against `127.0.0.1:8000`: submitted synthetic Mercado expense returned backend total R$ 123,45, one expense, category/payment breakdown, backend pt-BR insight, and source summary.
- Live browser evaluation: backend golden report displayed 30/30 correct, 100%, and all ten category confusion entries.
- Backend suite: 40 passed and 3 emulator tests skipped without `FIRESTORE_EMULATOR_HOST`; 43 passed with the Firestore Emulator running.

## Spec Sync

After each frontend commit, update `frontend-funcional-spec.md` with the actual SHA, contract changes, checks, and remaining gaps. No commit was created by this task.

## Open Questions

- An independent integration-persona sign-off has not been recorded; the current frontend and backend use the same documented request/response shapes.
- Consecutive browser reloads restore both existing expenses against emulator mode; full emulator-backed browser workflow coverage remains pending.
- Authentication and production-grade authorization remain future work; this UI must stay local and use synthetic data.

## Audit

- 2026-10-19; persona: frontend.eng; action: restore-persisted-expense-history. Confirmed records were still in the backend; recovered history and monthly results on mount instead of starting empty after refresh. Existing suites cover remount, pagination, empty/error states and delayed-response merging; OpenAPI guard covers the restoration requests. Verification: 57 tests, build and diagnostics pass, plus two existing records restored through consecutive real browser reloads. No expense mutation, provider request, browser persistence, dependency or commit added.
- 2026-10-19; persona: frontend.eng; action: expose-automatic-categorization. Added Automatica without a taxonomy write; covered input validation, both manual/null API payloads and backend category display in existing suites. Verification: 53 frontend tests and production build pass; touched files have no diagnostics. No backend changes, provider calls, dependencies or commit added; insight generation remains manual-only.
- 2026-10-19; persona: frontend.eng; action: make-insights-manual-only. Removed automatic insight generation from the expense run service and updated service/contract regressions; the existing button test now asserts zero generation calls before its click. Verification: 50 frontend tests and production build pass; no editor diagnostics in the run service/tests; existing frontend responds at `127.0.0.1:5173`. No backend safety changes, model calls, dependencies or commit added.
- 2026-10-19; persona: frontend.eng; action: align-provider-messages-with-copilot. Updated authentication, usage-limit, timeout, validation, safety and provider-error messages in both insight views to name GitHub Copilot. Safety rejection explicitly refers to application checks; backend rules, contracts and deterministic fallback are unchanged. Updated the existing assertions; 20 focused component tests pass, no diagnostics in touched files, and no OpenAI references remain under `frontend/src`. No dependencies, provider calls or commit added.
- 2026-10-12; persona: integration.eng; action: connect-local-fastapi.
- API calls use the existing loopback FastAPI service; no API key or personal data is stored in the browser.
- No new npm dependencies, commit, or branch created. Browser integration data was synthetic and cleared after verification.

## Sources

- `project-context/1.define/prd.md`: P0.1-P0.10 and responsive/localization requirements.
- `project-context/1.define/sad.md`: frontend/backend boundary and API contract.
- `project-context/2.build/frontend-funcional-spec.md` and `backend/src/home_financial_backend/api/routes.py`.

## Assumptions

- The browser targets the single local demo household returned by `GET /households/demo`.
- Monthly review defaults to the current month, exposes category/confidence/payment/source/review filters, and paginates in 100-expense pages.
- Export filenames are local browser downloads; the API remains the source of exported content.
