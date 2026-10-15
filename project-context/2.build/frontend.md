# Home Financial: Frontend Build Record

## Implementation

- Functional contract: `project-context/2.build/frontend-funcional-spec.md`.
- `frontend/`: React 19, TypeScript, Vite, Tailwind 4, Lucide icons. One route, `/`, with pt-BR manual expense entry, results/history, CSV import, expense review/correction, category management, exports/deletion, and evaluation.
- `src/workflow.ts`: backend category IDs, integer-cent input validation, reducer FSM, and BRL/month formatting.
- `src/services/runs.ts`: default service loads categories and calls `POST /expenses`, `GET /dashboard/monthly`, and best-effort `POST /insights/monthly`. `createRunService` remains a fixture for UI state tests only.
- `src/services/household.ts` and `src/WorkspaceTools.tsx`: typed API operations for CSV import, paginated expense filters/correction, category create/rename/merge, CSV/JSON export, confirmed data deletion, and golden evaluation.
- `src/App.tsx`: dynamically loads active leaf categories, validates inputs, keeps Run/Reset/Retry and history UX, and renders backend totals, expense, insight, and source summary.
- A top live banner displays `Crew: idle/running/done/error`, with gray/blue/green/red indicators. Error is a presentation of service/validation errors; the FSM remains idle/running/done.
- `Atualizado em` is a client timestamp updated on mount, Run/Retry, service responses, errors, and Reset.
- History has unique client request IDs and submitted input snapshots. A pending successful POST is reused on same-request retry if the dashboard request fails, preventing a duplicate expense.
- Reset clears the form/result/error/retry context but does not delete the backend expense. Refresh clears UI history; API memory data remains until the server restarts.

## Traceability And Deferrals

| Source | Implemented slice / limit |
| --- | --- |
| PRD AC-P0.2 | CSV file upload displays accepted/rejected counts and row-level errors. |
| PRD AC-P0.3.1/.2/.3/.5, P0.7 | Manual form uses backend expense creation; results show deterministic totals, category/payment breakdowns, and recurring amount. |
| PRD AC-P0.5/P0.6 | Expense category correction and custom category create/rename/merge use backend APIs. |
| PRD P0.8/P0.9/P0.10, SAD AD-03 | Insight sources, CSV/JSON export, confirmed deletion, and exact-label evaluation report are available. |
| SAD AD-01, AD-06 | React/TypeScript/Vite, loopback-only local demo, fictitious-data notice. |

Authentication, complete WCAG evaluation, emulator-backed frontend smoke tests, and production security review remain out of this local-only slice. The frontend never connects directly to Firestore or CrewAI.

## Verification

- `npm test`: 42 tests pass across component, workflow, API-service, and OpenAPI contract tests, including the household management interactions.
- `npm run build`: strict TypeScript check and Vite production build pass.
- `npm audit`: zero vulnerabilities in the last audit; frontend integration adds no packages.
- Live browser check against `127.0.0.1:8000`: submitted synthetic Mercado expense returned backend total R$ 123,45, one expense, category/payment breakdown, backend pt-BR insight, and source summary.
- Live browser evaluation: backend golden report displayed 30/30 correct, 100%, and all ten category confusion entries.
- Backend suite: 40 passed and 3 emulator tests skipped without `FIRESTORE_EMULATOR_HOST`; 43 passed with the Firestore Emulator running.

## Spec Sync

After each frontend commit, update `frontend-funcional-spec.md` with the actual SHA, contract changes, checks, and remaining gaps. No commit was created by this task.

## Open Questions

- An independent integration-persona sign-off has not been recorded; the current frontend and backend use the same documented request/response shapes.
- Browser flows have not been re-run against emulator mode; backend emulator behavior was verified through tests and an HTTP smoke run.
- Authentication and production-grade authorization remain future work; this UI must stay local and use synthetic data.

## Audit

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
