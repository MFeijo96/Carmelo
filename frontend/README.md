# Home Financial Frontend

## Run

Requires Node.js 22.22+ and npm. From the repository root:

```sh
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173/. The server binds only to loopback. If that port is occupied, use `npm run dev -- --port 5174 --strictPort` and open port 5174 instead.

For this workspace session, Node was downloaded and checksum-verified in `/tmp/node-v22.22.0-linux-x64`. Until Node is installed normally, run `export PATH="/tmp/node-v22.22.0-linux-x64/bin:$PATH"` in your terminal before npm commands. The temporary runtime is not a repository dependency and may disappear on reboot.

## Use

Enter a fictitious expense date, description, BRL value (for example `123,45`), category, and payment method. Recurrence is optional. Select **Registrar e analisar**; the form locks during the simulated run and Results displays the monthly snapshot. Select a completed history row to revisit its result. Invalid inputs and run failures preserve the form for retry.

All expenses and results are in memory. Refresh clears the session. No bank, database, LLM, backend service, or browser storage is connected. This is an educational prototype, not financial advice or the complete PRD MVP.

## Checks

```sh
npm test
npm run build
npm audit
```

The build runs strict TypeScript checking and emits `dist/`. `npm run preview` serves the build locally.

## Spec Sync

The [functional spec](../project-context/2.build/frontend-funcional-spec.md) defines Inputs, Run, Results, History, and the post-commit checklist. After each frontend commit, record its SHA and reconcile behavior, types, tests, and deferred work. See the [build record](../project-context/2.build/frontend.md) for verification and integration handoff.

## Sources

- [PRD](../project-context/1.define/prd.md), [SAD](../project-context/1.define/sad.md), and the requested frontend prototype.

## Assumptions

- Synthetic local demo, single route, manual input only; production arithmetic will move behind the backend service contract.

## Open Questions

- API mapping, full taxonomy, CSV import, correction, export/deletion, persistence, and security review are deferred.

## Audit

- 2026-10-09; frontend.eng; document-frontend-setup. Tools: apply_patch, npm tests/build/audit, browser verification. Runtime: crewai (not invoked). Model: GitHub Copilot; temperature/max_tokens not exposed. Prompt Trace omitted for this local synthetic prototype.