# Home Financial Frontend

## Run

Requires Node.js 22.22+ and npm. From the repository root:

```sh
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173/. The server binds only to loopback. If that port is occupied, use `npm run dev -- --port 5174 --strictPort` and open port 5174 instead.

Start the backend in a second terminal from the repository root:

```sh
backend/.venv/bin/home-financial-api
```

The frontend calls the API at `http://127.0.0.1:8000` by default. Set `VITE_API_BASE_URL` to another local API address when needed. Open the backend contract at http://127.0.0.1:8000/docs.

For this workspace session, Node was downloaded and checksum-verified in `/tmp/node-v22.22.0-linux-x64`. Until Node is installed normally, run `export PATH="/tmp/node-v22.22.0-linux-x64/bin:$PATH"` in your terminal before npm commands. The temporary runtime is not a repository dependency and may disappear on reboot.

## Use

Enter a fictitious expense date, description, BRL value (for example `123,45`), active leaf category or **Automatica**, payment method, and optional recurrence. Categories load from the backend. **Executar** posts the expense, then reads the deterministic monthly dashboard and review status. Insights are generated only through **Gerar insights do mês** in the **Despesas** tab. The API, not the browser, owns classification and financial totals.

The top banner shows **Crew: idle**, **Crew: running**, **Crew: done**, or **Crew: error**. `Atualizado em` advances on client workflow and service responses. Backend validation errors appear inline. **Tentar novamente** retries the original input; if the expense was created but its dashboard request failed, the client reuses that record instead of posting a duplicate.

Results show backend monthly totals, category/payment breakdowns, recurring amount and the saved expense. On opening or refreshing the page, saved expenses are reloaded from the backend and the latest is selected; restored results use current monthly totals, not historical snapshots. No financial history is stored in localStorage or cookies. Loading errors offer a retry instead of suggesting the data was deleted. Backend records remain until the API process restarts in default memory mode; Firestore Emulator data has its own runtime lifecycle. Reset clears the current form/results but does not delete backend data.

The **Gestão da casa** tabs provide CSV import with row errors, monthly expense review and category correction, custom category create/rename/merge, CSV/JSON export, confirmed demo-data deletion, and the deterministic golden evaluation report. Deleting demo data also clears the visible browser run history.

Use fictitious data only. Firestore Emulator mode is optional and documented below. There is no login or bank connection; this local demo is not suitable for real household data or financial advice.

## Checks

```sh
npm test
npm run build
npm audit
```
The build runs strict TypeScript checking and emits `dist/`. `npm run preview` serves the build locally.
The frontend client tests mock the API envelope; backend route behavior is exercised in `backend/tests/test_api_routes.py`.

## Spec Sync
The [functional spec](../project-context/2.build/frontend-funcional-spec.md) defines Inputs, Run, Results, History, and the post-commit checklist. After each frontend commit, record its SHA and reconcile behavior, types, tests, and deferred work. See the [build record](../project-context/2.build/frontend.md) for verification and integration handoff.

## Sources
- [PRD](../project-context/1.define/prd.md), [SAD](../project-context/1.define/sad.md), and the requested frontend prototype.

## Assumptions

- The existing manual-entry workflow is retained, but run operations now call the local FastAPI service.
- Backend persistence uses in-memory storage by default; Firestore Emulator is an optional backend mode.

## Open Questions

- Emulator-backed browser verification and independent security review remain outstanding. The local demo is unauthenticated and must use synthetic data only.

## Audit

- 2026-10-09; frontend.eng; document-frontend-setup. Tools: apply_patch, npm tests/build/audit, browser verification. Runtime: crewai (not invoked). Model: GitHub Copilot; temperature/max_tokens not exposed. Prompt Trace omitted for this local synthetic prototype.
- 2026-10-09; frontend.eng; sync-run-controls. Updated fixed mock behavior, Run/Reset/Retry, status text, and observability deferrals; no commit created.
- 2026-10-09; frontend.eng; sync-status-banner. Documented the shared labels/colors, derived error display, and real client update timestamp; no commit created.
- 2026-10-12; integration.eng; connect-fastapi. Replaced fixed default results with expense/dashboard/insight API responses, loaded active-leaf categories, and retained the run FSM/retry/history UX. No commit created.