# Home Financial: Frontend Build Record

## Implementation

- Functional contract: `project-context/2.build/frontend-funcional-spec.md` (requested spelling retained).
- `frontend/`: React 19, TypeScript, Vite, Tailwind 4, Lucide icons. One route, `/`; pt-BR manual expense form, run status, results, and session history.
- `src/workflow.ts`: discriminated service contracts, integer-cent validation, reducer FSM, BRL/month formatting.
- `src/services/runs.ts`: `startRun`/`getRunStatus` exports plus an isolated service factory for tests. Fixed start ID (`demo-run`), running payload, and immutable October 2026 result fixture; simulated latency only, no input-derived arithmetic or backend endpoints.
- `src/App.tsx`: validates inputs, starts exactly once, polls every 400 ms, stops scheduled polling on unmount, preserves inputs on failure, and focuses Results on completion/history selection. Run/Reset are the normal controls; errors replace Run with explicit same-input Retry. Reset clears form/result/error/retry context to idle while retaining history.
- A top live banner displays `Crew: idle/running/done/error`, with gray/blue/green/red indicators. Error is a presentation of existing validation/service errors; the FSM remains idle/running/done. Shared status wording appears in the running button/empty state, inline errors, and completed Results/History labels.
- `Atualizado em` is the real client timestamp of mount, Run/Retry, service start acknowledgement/status response, error, or Reset. It has an ISO time attribute and localized date/time tooltip; no independent clock or mock completion timestamp is used.
- History has unique client request IDs and original submitted inputs, separate from the fixed mock result.
- CSS uses a restrained light financial-workbench palette with green and terracotta accents, serif headings, responsive grid, native labeled controls, visible focus, live status, and reduced-motion support. No external font/image requests.

## Traceability and Deferrals

| Source | Implemented slice / limit |
| --- | --- |
| PRD AC-P0.3.1/.2/.3/.5 | Manual fields, BRL cents, input validation, cash/debit/credit and separate recurrence; no persisted expense creation. |
| PRD AC-P0.3.4, P0.7 | Submitted inputs appear in run history; Results uses a clearly labeled fixed fixture per the follow-up user requirement, not input-derived totals or the full dashboard. |
| PRD P0.8 / SAD AD-03 | Neutral deterministic demo summary, not LLM insights or authoritative production totals. |
| SAD AD-01, AD-06 | React/TypeScript/Vite, loopback-only server, fictitious data warning. |

CSV import, complete taxonomy, correction history, confidence scoring, comparisons, LLM grounding, persistence, export/deletion, and authentication remain separate work. Streaming, tool-call details, costs, pause/cancel/retry-diff, advanced accessibility, and resilience are deferred until observability. The existing timeout/AbortController layer was removed to honor that scope; basic polling cleanup remains. No claim that PRD MVP gates are complete. Runtime remains crewai; the frontend does not invoke it or connect to Firestore.

## Verification

Executed on 2026-10-09 using a checksum-verified Node 22.22.0 runtime in `/tmp` because Node was not installed in PATH.

- `npm test`: 27 passing tests in two files, including nine component tests. Covers parsing, invalid inputs, FSM guards, fixed/immutable service responses across different submissions, duplicate prevention, unique history, explicit Retry with the original inputs even after edits, Reset defaults/error/results/history behavior, keyboard navigation/activation, semantic headings, polling cleanup, and banner placement/labels/colors/event timestamps.
- `npm run build`: strict TypeScript check and Vite production build passed.
- `npm audit`: zero vulnerabilities after updating Vitest to the patched 5.x release. Dependency versions are pinned by `frontend/package-lock.json`.
- Editor diagnostics: no errors in App, workflow, or Vite config.
- Current browser DOM-triggered workflow: a R$ 999,99 input returns the fixed R$ 123,45 fixture, status moves running -> done, Reset is disabled during running, then clears fields/results to idle and retains completed history.
- Current geometry checks at widths 1440, 390, 320: no horizontal overflow or clipped controls; Reset target remains 44 pixels. The shared page is hidden, so native Playwright click/Tab checks are inconclusive; component user-event tests cover basic keyboard Tab/Space/Enter navigation and Reset activation. Full real-browser keyboard audit is deferred.
- Status-banner browser check: gray idle, red validation error, blue running, green done computed colors matched the shared mapping; the timestamp advanced from start to completion. Banner was the first main-content row and had no clipping/overflow at 1440, 390, 320. Desktop and mobile screenshots inspected. The browser initially had a suspended Vite connection; refreshing loaded the current app.
- Earlier initial-slice checks confirmed refresh cleanup and empty localStorage/sessionStorage. No browser storage was introduced by this follow-up.
- `.venv/bin/aamad validate`: initially passed before `frontend.md` existed. Final validation activates full-Build gates and fails on missing `qa.md`, with warnings for missing `setup.md`, `backend.md`, `integration.md`, and `evals.md`. These are other personas' artifacts, not frontend code failures; full-Build approval is pending and no placeholder approvals were fabricated.
- Independent required-heading self-check passed for the functional spec, this build record, and frontend README. Framework validation alone does not prove UI behavior.
- Accessibility checks are focused, not a full WCAG audit. Full backend integration, golden-dataset evaluation, and security assessment have not been performed in this frontend-only task.

## Spec Sync

After every frontend commit, update the checklist and commit log in `frontend-funcional-spec.md`. Record the actual SHA, changed contracts, test/build/audit results, and newly introduced gaps. This task makes no commit; the initial log is marked uncommitted. Update this record and `frontend/README.md` when behavior/setup changes.

## Sources

- PRD P0.1/P0.3/P0.7/P0.8 and SAD AD-01/AD-03/AD-06 in `project-context/1.define/`.
- `aamad.config.yml`, `.github/agents/frontend-eng.agent.md`, and the current Home Financial user request.

## Assumptions

- The explicit form/results request supersedes the persona's generic chat-interface wording.
- User stories have not been generated; PRD IDs are the available traceability anchors.
- SAD React/TypeScript selection governs frontend language despite config's Python-primary setting.
- Session history is run history, not persistent classification-correction history. Only the configured demo leaf subset is available.
- Fixed payloads intentionally ignore submitted values, per the follow-up user requirements. The fixed service ID supports one active demo run; client IDs identify distinct completed submissions.

## Open Questions

- Integration must confirm API contracts and replace the stub while keeping production financial calculations server-owned.
- Full taxonomy, CSV, export/deletion, and correction flows need their own specifications and tests.
- Security assessment remains required before Deliver/production use; this local synthetic prototype is not approved for real financial data.

## Audit

- Timestamp: 2026-10-09; persona: frontend.eng; action: implement-and-verify-frontend.
- Resolved runtime: crewai; no `AAMAD_TARGET_RUNTIME` override observed.
- Tools: read/search/list, apply_patch, terminal dependency/test/build/audit/validator commands, editor diagnostics, browser Playwright and screenshots. No backend, git commit, or branch creation.
- Model identity: GitHub Copilot; temperature/max_tokens not exposed. Current deterministic controls: integer-cent input validation, fixed result fixture, isolated service instances, fixed 1200 ms latency, client request correlation IDs, loopback bind, lockfile.
- Prompt Trace omitted because this is a local synthetic-data prototype, not a production-facing output. No real financial data or secrets used.
- Timestamp: 2026-10-09; persona: frontend.eng; action: implement-missing-run-controls. Fixed mocks, Reset, same-input Retry, simple statuses, and basic keyboard tests added; timeout/abort complexity removed per requested deferral. Added @testing-library/user-event for keyboard verification. No commit or branch created.
- Timestamp: 2026-10-09; persona: frontend.eng; action: implement-status-banner. Added shared labels/colors, top status row, real client event timestamp, error overlay, and focused tests. No new dependencies, backend calls, FSM state, commit, or branch.