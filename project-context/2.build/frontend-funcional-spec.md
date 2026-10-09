# Home Financial: Frontend Functional Specification

## Scope

One React/TypeScript/Vite route (`/`) for a local, synthetic-data expense workflow in pt-BR. This is a frontend prototype, not the complete PRD MVP. No backend, database, credentials, LLM, or network-based financial services are used. The stub owns demo arithmetic; production totals must come from deterministic backend services.

## Inputs

- Required: valid calendar date, trimmed description (1-120 characters), positive BRL amount (maximum R$ 999.999,99), active demo category, and payment method (`dinheiro`, `debito`, `credito`).
- Amount uses Brazilian notation: `1234,56` or `1.234,56`; at most two decimal places. Convert to integer cents, never floating-point currency arithmetic.
- Optional recurring checkbox, initially unchecked, independent of payment method.
- Categories: Alimentacao, Moradia, Transporte, Saude, Educacao, Comunicacao, Lazer, Outros. These are a demo subset, not the full editable taxonomy.
- Submit validates before starting. Invalid entries do not create runs. Preserve inputs after failures. Clear description/amount after success; retain date/category/payment/recurrence for repeated entry.
- A visible local-demo notice requests fictitious data. CSV ingestion, merchant context, taxonomy editing, category correction, export/deletion, and login are deferred, not represented as working controls.
- Trace: PRD AC-P0.3.1, .2, .3, .5; SAD AD-01, AD-06.

## Run

- Lightweight reducer FSM: `idle -> running -> done`; `done -> running` for another submission and `running -> idle` on failure. The reducer also supports `reset -> idle` outside running; this internal event has no UI control in this slice.
- `started` records a client request ID before `startRun` resolves. The submit handler freezes the submitted input; completion carries this request ID separately from the service result ID. Duplicate starts while running and completions for another request ID are ignored.
- Disable input/submit while running; announce status via a live region. Submit exactly once, then poll every 400 ms with a 10-second overall timeout. Stop polling on unmount. Failure shows an actionable message and allows retry without losing fields.
- `startRun(input): Promise<{ runId: string }>` validates and snapshots input. `getRunStatus(runId): Promise<RunStatus>` returns a discriminated `running | done` response; unknown IDs reject.
- Stub latency is 1.2 seconds, entirely in memory. IDs are unique; polling is idempotent. Results include only previously completed expenses in the submitted month plus the new expense. There are no backend endpoint assumptions; integration must map this UI contract to the eventual API.
- Trace: SAD non-streaming interaction and deterministic service boundary.

## Results

- Before completion, show an explicit empty/pending state, never fabricated totals.
- On completion, display the selected month, exact BRL total, expense count, recurring total, category and payment breakdowns, submitted expense, and a neutral deterministic summary.
- Mark outputs as simulated and educational, not financial advice or an AI-generated result. Classification is user-selected in this slice, not inferred; no accuracy claims.
- Viewing an earlier run shows its immutable monthly snapshot; later runs do not rewrite it. Results are not authoritative or persisted.
- Trace: PRD P0.7/P0.8, SAD AD-03. This slice does not satisfy full dashboard/insight acceptance gates.

## History

- Newest completed runs first, with timestamp, description, amount, month, and an accessible results action.
- History is shared only within the current mounted browser session; refresh clears all input/run/result data. No localStorage, cookies, analytics, or identity history.
- No failed or pending run is listed as completed. Selecting history does not submit again or modify the form. A new completion becomes the selected result.
- Trace: SAD demo workspace constraints. This is run history, not PRD category-correction history.

## Acceptance Checks

- Unit tests: BRL parsing/validation, illegal FSM transitions, stale completion IDs, failure/retry, isolated input snapshots, running/done service responses, idempotent polling, unknown IDs, exact monthly/category/payment/recurrence totals, month isolation.
- Component integration tests: valid form -> disabled running state -> results/history, invalid input, failure/retry, history selection, unmount cleanup.
- `npm test`, `npm run build`, and `npm audit` in `frontend/`; browser check at desktop and mobile widths for labels, focus, overflow, results, and history.
- Artifact self-check: Inputs, Run, Results, History, Spec Sync, Sources, Assumptions, Open Questions, Audit headings exist. Run `aamad validate` if the CLI is available.

## Spec Sync

Update this checklist after **each commit** affecting the frontend. No commit is created by this task.

- [ ] Record commit SHA/date and changed files below.
- [ ] Reconcile Inputs, validation rules, locale, and field defaults with code.
- [ ] Reconcile Run transitions, retries, timeout, polling, and service types.
- [ ] Reconcile Results snapshots, cents arithmetic, and History lifetime.
- [ ] Update PRD/SAD traceability and explicitly mark remaining deferrals.
- [ ] Run scoped tests/build/audit and record outcomes and known gaps.
- [ ] Update `frontend.md` and `frontend/README.md` when behavior/setup changes.

| Commit / date | Spec changes | Checks / gaps |
| --- | --- | --- |
| Uncommitted / 2026-10-09 | Initial frontend slice | 24 tests, TypeScript/Vite build, zero audit advisories, headings and desktop/mobile browser checks passed. Full AAMAD Build gates pending missing artifacts; see frontend.md. |

## Sources

- `project-context/1.define/prd.md`: P0.1, P0.3, P0.7, P0.8; pt-BR, BRL, synthetic local workspace.
- `project-context/1.define/sad.md`: AD-01, AD-03, AD-06; React/TypeScript/Vite, service-owned arithmetic, loopback-only demo.
- `aamad.config.yml`; `.github/agents/frontend-eng.agent.md`; user request for single route, stub services, FSM, and commit-time Spec Sync.

## Assumptions

- User explicitly requests this small form/results slice, rather than the persona's generic chat interface. No chat or research workflow is introduced.
- User-story files are absent; PRD acceptance IDs serve as traceability anchors, not a claim that full Build gates have passed.
- React/TypeScript follows the SAD despite config listing Python as primary with no secondary languages.

## Open Questions

- Confirm the complete active-leaf taxonomy and API run contract during integration.
- CSV, correction history, export/deletion, authenticated access, and production security require separate slices.

## Audit

- Timestamp: 2026-10-09; persona: frontend.eng; action: create-functional-spec.
- Runtime: crewai (no override observed); frontend stubs never invoke it.
- Tools: workspace reads/searches, apply_patch, terminal setup/test/build/audit, browser checks. Model identity: GitHub Copilot; temperature/max_tokens not exposed by editor.
- Prompt Trace omitted: synthetic local prototype, not a production-facing release. No secrets or real financial data used.