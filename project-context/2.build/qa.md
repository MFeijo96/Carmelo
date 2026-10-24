# QA Record

## Scope

Build-phase verification of deterministic backend services, API routes, CrewAI boundaries, frontend workflows, and the golden category evaluation. Results below are automated checks from the current workspace, not a claim of an independent QA persona approval.

## Test Results (2026-10-23)

- Backend: 92 passed, 0 skipped with Firestore Emulator 1.22.0 at `127.0.0.1:8080`; without the emulator, the three emulator-specific tests are expected to skip.
- Frontend: 57 tests passed across six files; TypeScript and Vite production build passed using the VS Code bundled Node runtime.
- Backend Ruff lint and `mypy src` (33 source files): passed.
- Backend `ruff format --check .`: reports only the existing formatting difference in `services/expenses.py`; it was left untouched as unrelated worktree state.
- `aamad validate`: passed with no validation issues.
- Frontend `npm audit` using npm CLI 10.9.4: zero vulnerabilities. Python dependency and secret scans were not rerun in this cycle.

## Acceptance Coverage

- Expense validation, CSV row handling, active-leaf category rules, correction precedence, and exact monthly arithmetic are covered by backend tests.
- Insight source membership, unsafe/ungrounded output rejection, pt-BR validation, timeout fallback, and deterministic fallback are covered.
- The persisted merchant alias projection is covered for stability, hints/recurrence, exclusion of raw values from provider prompts, export exclusion, and deletion. OpenAPI drift is guarded in both the backend and frontend suites (mutation-checked).
- Emulator-backed runs cover CSV import-to-dashboard, persistence, export, deletion, and alias handling.
- Frontend component coverage includes import reports, expense correction, category create/rename/merge, evaluation output, exports, and deletion confirmation.
- Golden evaluation uses 50 synthetic records, deterministic classification, and no classifier fallback; the current result is 50/50 exact matches (100%).

## Outstanding Gates

- Independent security review and a full WCAG review remain outstanding.
- Browser smoke passed against the loopback in-memory API with provider calls disabled. No horizontal overflow was observed at 390px and 1440px nominal viewport widths.
- Firestore Emulator integration tests passed using the cached emulator JAR and Java 21. CI should provision the emulator and Java runtime itself; browser workflows against emulator persistence remain unverified.
- AMP trace upload passed on 2026-10-23 using the local Personal Access Token and a fake local LLM. The prompt and output contained synthetic test text only; no model-provider call was made.

## Browser Smoke (2026-10-23)

- Manual synthetic expense produced the expected backend dashboard total and category/payment breakdown.
- An automatic uncategorized expense entered review; insights remained gated until category correction, after which deterministic insight generation succeeded with provider calls disabled.
- `backend/data/qa-mixed-import.csv` imported one valid row and rejected one invalid-date row with a row-level error.
- Category create, rename, and merge succeeded. The evaluation UI reported 50/50 (100%) and 14 confusion entries.
- CSV and JSON export actions reported success. The browser harness did not capture native download events, so downloaded-file contents were not independently inspected in this smoke.
- Confirmed demo-data deletion cleared the three synthetic expenses and visible run history.
- No horizontal overflow was observed at 390px and 1440px nominal viewport widths. This was a focused smoke, not a full WCAG or visual regression audit.

## Sources

- `backend/tests/` and `frontend/src/` test suites.
- `project-context/1.define/prd.md` acceptance criteria and `project-context/1.define/sad.md` quality scenarios.
- `project-context/2.build/backend.md` and `project-context/2.build/frontend.md`.

## Assumptions

- Emulator skips are not counted as passing integration gates.
- Golden evaluation accuracy is tied to the committed synthetic dataset and current deterministic rules; its curated examples are not a production accuracy estimate.

## Open Questions

- Run browser flows against emulator persistence in CI; capture native export contents; rerun Python dependency audits when their tooling is available.
- Obtain independent QA/security review and full accessibility evaluation before any cloud or hosted deployment.

## Audit

- AAMAD_TARGET_RUNTIME: crewai.
- 2026-10-12: automated test and static-check results recorded from the local workspace; no persona approval is implied.
- 2026-10-23: added a planned QA cycle for synchronized test results, synthetic end-to-end flow checks, and desktop/mobile browser smoke; no checks were run and no independent approval is implied.
- 2026-10-23: backend 92 passed/0 skipped with Firestore Emulator, frontend 57 passed/build and npm audit passed, AAMAD passed; exercised in-memory browser flows, confirmed deletion of only this run's synthetic data, and accepted one synthetic AMP trace. Emulator browser, full WCAG, and independent persona gates remain open.
