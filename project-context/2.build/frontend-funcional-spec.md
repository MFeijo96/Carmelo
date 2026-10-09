# Home Financial: Frontend Functional Specification

## Scope

One React/TypeScript/Vite route (`/`) for a local, synthetic-data expense workflow in pt-BR. This is a frontend prototype, not the complete PRD MVP. No backend, database, credentials, LLM, or network-based financial services are used. Per the updated user requirements, services return fixed mock payloads rather than calculating results from inputs. Production totals must come from deterministic backend services.

## Inputs

- Required: valid calendar date, trimmed description (1-120 characters), positive BRL amount (maximum R$ 999.999,99), active demo category, and payment method (`dinheiro`, `debito`, `credito`).
- Amount uses Brazilian notation: `1234,56` or `1.234,56`; at most two decimal places. Convert to integer cents, never floating-point currency arithmetic.
- Optional recurring checkbox, initially unchecked, independent of payment method.
- Categories: Alimentacao, Moradia, Transporte, Saude, Educacao, Comunicacao, Lazer, Outros. These are a demo subset, not the full editable taxonomy.
- Submit validates before starting. Invalid entries do not create runs. Preserve inputs after failures. Clear description/amount after success; retain date/category/payment/recurrence for repeated entry. Reset restores every field to its initial default.
- A visible local-demo notice requests fictitious data. CSV ingestion, merchant context, taxonomy editing, category correction, export/deletion, and login are deferred, not represented as working controls.
- Trace: PRD AC-P0.3.1, .2, .3, .5; SAD AD-01, AD-06.

## Run

- Lightweight reducer FSM: `idle -> running -> done`; `done -> running` for another submission and `running -> idle` on failure. Reset returns to `idle`, clears the selected result/error/retry snapshot, and retains completed history.
- `started` records a client request ID before `startRun` resolves. The submit handler freezes the submitted input; completion carries this request ID separately from the service result ID. Duplicate starts while running and completions for another request ID are ignored.
- Workflow controls are Run (`Executar`) and an icon-only Reset (`Redefinir`, accessible name and tooltip). Both controls and the fields are disabled during running; Reset is not cancellation. While running, the disabled Run button uses the shared `Crew: running` label.
- The first row of main content is a live status banner: `Crew: idle`, `Crew: running`, `Crew: done`, or `Crew: error`. Gray/blue/green/red indicators respectively accompany the text; state is never communicated by color alone. Error is derived from validation/service errors, not a fourth FSM state.
- The banner displays `Atualizado em` with a real client-local HH:mm:ss timestamp and a semantic time element containing the ISO instant and a full date/time tooltip. Initialize on mount; update on Run/Retry, start acknowledgement, each status response, validation/service error, and Reset. Do not reuse the fixed mock completion timestamp or tick an unrelated clock when no update arrives.
- One shared label/color mapping supplies the banner, running button, running empty-state heading, inline error prefix, and completed Results/History labels. Action labels (Executar, Redefinir, Tentar novamente) remain commands. Completed history rows continue to say `Crew: done` when the current workflow has been reset to idle.
- On service error, show an inline message and replace Run with Retry (`Tentar novamente`). Retry restores and resubmits the original failed input snapshot, even if the form was edited after failure. Reset dismisses the error and returns to normal Run mode. Invalid form values show validation feedback with Run still available, not Retry.
- Submit exactly once, then poll every 400 ms. Basic effect cleanup stops scheduled polling on unmount. No streaming, tool-call details, costs, pause, cancel, retry-diff, automatic retries, timeout, or AbortController layer; advanced resilience is deferred until observability.
- `startRun(input): Promise<{ runId: string }>` validates input and always returns `{ runId: 'demo-run' }`. `getRunStatus(runId): Promise<RunStatus>` returns fixed `running` then fixed `done` payloads; unknown or not-yet-started IDs reject.
- Stub latency is 1.2 seconds, entirely in memory. It supports one active run, consistent with disabled controls. Each done response is a fresh copy of the same fixture; result values do not depend on inputs or prior runs. Client request IDs uniquely identify history entries despite the fixed service ID. There are no backend endpoint assumptions.
- Trace: SAD non-streaming interaction and deterministic service boundary.

## Results

- Before completion, show an explicit empty/pending state, never fabricated totals.
- On completion, display the fixed October 2026 fixture: R$ 123,45, one non-recurring Alimentacao expense paid with debito, and a neutral example summary. The example record is labeled demonstrative, not the submitted expense.
- Explicitly disclose that result values are fixed and independent of submitted values, not financial advice or an AI-generated result. No classification/accuracy claims.
- Viewing an earlier run shows its immutable fixture snapshot; later runs do not rewrite it. Reset hides Results until another run or history selection. Results are not authoritative or persisted.
- Trace: PRD P0.7/P0.8, SAD AD-03. This slice does not satisfy full dashboard/insight acceptance gates.

## History

- Newest completed runs first, with the submitted description, amount, month, and an accessible results action. These input snapshots are separate from the fixed result fixture; the mock completion timestamp is not presented as a real submission time.
- History is shared only within the current mounted browser session; refresh clears all input/run/result data. No localStorage, cookies, analytics, or identity history.
- No failed or pending run is listed as completed. Selecting history does not submit again or modify the form. A new completion becomes the selected result.
- Trace: SAD demo workspace constraints. This is run history, not PRD category-correction history.

## Acceptance Checks

- Unit tests: BRL parsing/validation, illegal FSM transitions, stale completion IDs, failure/retry/reset, fixed service payloads across different inputs, isolated result copies, unknown/not-started IDs.
- Component integration tests: valid form -> disabled running state -> fixed results/history, invalid input, explicit same-input Retry, Reset defaults/error/result cleanup, unique history identity, unmount cleanup, keyboard Tab/Space/Enter access with semantic headings, banner placement/labels/colors, and event-driven timestamps across polling/error/retry/reset.
- Basic accessibility includes labeled native controls, semantic headings, visible focus, and keyboard navigation. Full WCAG/screen-reader audits and advanced accessibility/resilience are deferred to observability.
- `npm test`, `npm run build`, and `npm audit` in `frontend/`; browser check at desktop and mobile widths for labels, focus, overflow, results, and history.
- Artifact self-check: Inputs, Run, Results, History, Spec Sync, Sources, Assumptions, Open Questions, Audit headings exist. Run `aamad validate` if the CLI is available.

## Spec Sync

Update this checklist after **each commit** affecting the frontend. No commit is created by this task.

- [ ] Record commit SHA/date and changed files below.
- [ ] Reconcile Inputs, validation rules, locale, and field defaults with code.
- [ ] Reconcile Run/Reset/Retry, states, polling, service types, and resilience deferrals.
- [ ] Reconcile banner labels/colors, derived error presentation, and client timestamp triggers.
- [ ] Reconcile fixed Results fixtures, submitted-input snapshots, and History lifetime.
- [ ] Update PRD/SAD traceability and explicitly mark remaining deferrals.
- [ ] Run scoped tests/build/audit and record outcomes and known gaps.
- [ ] Update `frontend.md` and `frontend/README.md` when behavior/setup changes.

| Commit / date | Spec changes | Checks / gaps |
| --- | --- | --- |
| Uncommitted / 2026-10-09 | Initial frontend slice | 24 tests, TypeScript/Vite build, zero audit advisories, headings and desktop/mobile browser checks passed. Full AAMAD Build gates pending missing artifacts; see frontend.md. |
| Uncommitted / 2026-10-09 | Fixed service payloads, Run/Reset/Retry, simple statuses, basic keyboard checks; resilience deferred | 25 tests and TypeScript/Vite build passed; mounted-app DOM workflow and 1440/390/320 geometry checks passed. Full Build gates remain pending. |
| Uncommitted / 2026-10-09 | Top status banner, shared state wording/colors, client last-updated timestamp | 27 tests and build passed; mounted-app colors/timestamps, screenshots, and 1440/390/320 geometry passed. Full Build gates remain pending; see frontend.md. |

## Sources

- `project-context/1.define/prd.md`: P0.1, P0.3, P0.7, P0.8; pt-BR, BRL, synthetic local workspace.
- `project-context/1.define/sad.md`: AD-01, AD-03, AD-06; React/TypeScript/Vite, service-owned arithmetic, loopback-only demo.
- `aamad.config.yml`; `.github/agents/frontend-eng.agent.md`; user request for single route, stub services, FSM, and commit-time Spec Sync.

## Assumptions

- User explicitly requests this small form/results slice, rather than the persona's generic chat interface. No chat or research workflow is introduced.
- User-story files are absent; PRD acceptance IDs serve as traceability anchors, not a claim that full Build gates have passed.
- React/TypeScript follows the SAD despite config listing Python as primary with no secondary languages.
- The follow-up user requirements deliberately replace input-derived calculations with fixed mock payloads for this frontend-only slice. This does not alter the PRD/SAD production arithmetic requirements.

## Open Questions

- Confirm the complete active-leaf taxonomy and API run contract during integration.
- CSV, correction history, export/deletion, authenticated access, and production security require separate slices.

## Audit

- Timestamp: 2026-10-09; persona: frontend.eng; action: create-functional-spec.
- Runtime: crewai (no override observed); frontend stubs never invoke it.
- Tools: workspace reads/searches, apply_patch, terminal setup/test/build/audit, browser checks. Model identity: GitHub Copilot; temperature/max_tokens not exposed by editor.
- Prompt Trace omitted: synthetic local prototype, not a production-facing release. No secrets or real financial data used.
- Timestamp: 2026-10-09; persona: frontend.eng; action: sync-minimal-run-controls. Added fixed mocks, explicit Reset/same-input Retry, three visible statuses, and keyboard tests; removed timeout/abort layer per requested observability deferral. Same tools/runtime controls as above; no commit created.
- Timestamp: 2026-10-09; persona: frontend.eng; action: implement-status-banner. Added top banner, shared wording/colors, client event timestamps, derived error presentation, and regression checks without changing the three-state FSM or stub payloads. Same tool/runtime disclosure as above; no commit created.