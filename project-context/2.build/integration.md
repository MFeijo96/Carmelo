# Integration Record

## Scope

The React application integrates with the local FastAPI API. The browser does not access Firestore or an LLM provider directly. All requests use the configured loopback API base URL; the default is `http://127.0.0.1:8000`.

## Integration Engineer Work

- Keep frontend service requests and response handling aligned with the FastAPI routes and committed OpenAPI contract.
- Connect the expense workflows end to end: manual entry, CSV import, monthly review and correction, category management, dashboard and insights, exports and deletion, and categorization evaluation.
- Preserve transport-specific behavior, including the shared JSON envelope and raw UTF-8 CSV request body, and keep provider and persistence access behind the backend.
- Verify integration with contract and workflow tests, then record any live smoke checks, failures, and incomplete flows here. Existing verification evidence is listed below; this documentation update did not rerun those checks.
- Keep the MVP local/demo-only. Authentication, public hosting, and production household data are outside this integration scope.

Current status: the listed frontend flows are connected to the local API. Monthly insights are now gated on pending category reviews in both the API and UI; the review workspace exposes an explicit generate action once review is complete. Emulator-mode browser coverage and independent QA/security sign-off remain open.

## End-to-End Integration Plan

Execute this plan in order, updating the flow evidence and open gaps below as each gate is completed. It covers the remaining verification and any contract/UI gaps found; it does not authorize out-of-scope production integrations.

1. **Confirm contracts and runtime boundaries.** Compare every frontend service operation with `backend/openapi.json` and its FastAPI route, including request fields, response envelopes, errors, pagination, and CSV transport. Keep the browser connected only to FastAPI; keep persistence and provider credentials server-side.
2. **Trace expense input through storage.** Exercise manual entry and CSV import with valid, invalid, and mixed rows. Verify field-level errors, accepted/rejected counts, persisted records, category resolution, and that structurally invalid files do not partially write.
3. **Close the human review loop for classification.** Verify classifier decisions below the PRD `0.70` confidence threshold and unresolved cases appear in the review list with their reason/source. Where low-confidence items or user corrections exist, require the user to review/correct them before presenting monthly insights as final. Confirm corrections are visibly distinguished, persisted as overrides, used by later classifications, and reflected in dashboard and insight inputs. Do not label the confidence score as a probability.
4. **Verify deterministic monthly results and optional insights.** Check totals, category/payment breakdowns, recurrence, and comparisons against source expenses without relying on model output. When enabled, call OpenAI only through the backend provider abstraction for unresolved classification or insight writing; send only the SAD allow-listed alias-safe projection and precomputed summaries. Verify schema/source/safety checks and deterministic fallback when credentials are absent, output is invalid, or the provider times out.
5. **Verify taxonomy, portability, and destructive actions.** Test category create/rename/merge and reassignment against active-leaf rules. Round-trip CSV using the documented schema; inspect JSON archive scope and metadata. Require explicit UI confirmation before deletion and verify deletion removes household-owned records without affecting other data.
6. **Run the complete integration gate.** Run frontend tests/build, backend route/service tests, OpenAPI drift checks, golden evaluation with the LLM disabled, and emulator-backed persistence/export/deletion tests. Then smoke-test the browser against both in-memory and Firestore Emulator modes using synthetic data; capture failures, evidence, and remaining gaps here. Request QA and security review rather than recording their sign-off on their behalf.

### External Integration Scope And Gates

- **Required:** the frontend-to-FastAPI HTTP API, using the committed OpenAPI contract and the configured loopback base URL for the local/demo MVP.
- **Optional MVP provider:** OpenAI, called only from the backend through the provider abstraction for the specified LLM tasks. It must remain usable without credentials through deterministic fallbacks; secrets and raw merchant/payee values must never reach the browser or provider payload.
- **Persistence:** in-memory and Firestore Emulator modes are within current integration verification. Cloud Firestore/ADC is not part of this plan until emulator persistence, export, and deletion gates pass and IAM/security review approves the change.
- **Explicitly out of scope:** bank/Open Finance/Pix APIs, authentication and password-recovery email, external household invitations, and public hosting. Do not add credentials or call these services for this MVP.

**Plan completion criteria:** each required user flow has a passing automated test and an end-to-end smoke result; the low-confidence review gate and deletion confirmation are demonstrated; provider fallback/privacy behavior is verified; and all deferred integrations and remaining risks are recorded. Independent QA/security approvals remain owned by those personas.

### Implementation Status

1. **Contracts and boundaries: complete.** Frontend operations remain covered by the OpenAPI contract test; browser access stays behind FastAPI.
2. **Expense input/import: complete.** Existing backend/frontend tests cover manual input, valid and rejected CSV rows, row errors, and persistence. Browser smoke verified a synthetic CSV import.
3. **Human review: complete.** `POST /insights/monthly` returns HTTP 409 while that month has pending review items. Manual entry withholds automatic insight requests when review is pending or the review count cannot be confirmed. The results view links to pending-only review; correction clears the flag and unlocks the review workspace's explicit insight action.
4. **Monthly results/provider behavior: automated coverage complete.** Deterministic totals remain separate from Crew output; provider safety/fallback contracts are covered by backend tests. The live browser used deterministic fallback because no OpenAI key was configured.
5. **Taxonomy/export/deletion: automated coverage complete.** Existing route, service, and component tests cover category operations, exports, confirmation, and deletion. A live deletion smoke was intentionally not performed to preserve workspace data.
6. **Integration gate: partial.** Automated suites, build, lint, type checks, and in-memory browser smoke pass. Emulator-mode browser testing and separate QA/security sign-off remain blocked/open.

## Contract

FastAPI OpenAPI at `/openapi.json` is the machine-readable contract, committed as `backend/openapi.json`. A backend test fails when it drifts from the running API, and a frontend test fails when any client call targets an operation absent from it. JSON endpoints return `data`, `errors`, and `meta` with `request_id` and `schema_version`. CSV import sends raw UTF-8 CSV with `Content-Type: text/csv`; CSV export is a file response with schema/household/date metadata headers.

The frontend uses `/households/demo`, `/categories`, `/expenses`, `/imports/csv`, `/dashboard/monthly`, `/insights/monthly`, `/exports/expenses.csv`, `/exports/archive.json`, `/households/{id}/demo-data`, and `/evaluation/categorization`. Category corrections and taxonomy changes use the documented PATCH/POST routes.

## Flows

- Manual expense creation followed by dashboard and best-effort insights when no review is pending; otherwise insight generation waits for review.
- CSV upload with imported/rejected counts and row-level errors.
- Monthly expense review, active-leaf correction, then explicit insight generation after pending review is cleared; category create/rename/merge.
- CSV/JSON download, confirmed demo-data deletion, and deterministic evaluation report.

## Verification

- Frontend: 48 tests pass; `npm run build` passes TypeScript and Vite production build.
- Backend: 51 tests pass; 3 Firestore Emulator tests skip without `FIRESTORE_EMULATOR_HOST`.
- Backend Ruff lint and mypy pass (33 source files).
- Browser smoke against the local in-memory API imported one synthetic ambiguous CSV expense, confirmed insight generation was disabled while review was pending, corrected its category, and verified the explicit insight action then returned the deterministic summary.
- The live evaluation tab returned 30/30 exact matches and displayed the category confusion entries.
- The live API reported `provider_configured=false`; no external provider credentials or requests were used.

## Known Gaps

No independent integration-persona sign-off is recorded. The current browser smoke used in-memory persistence; emulator-mode browser coverage remains unverified. The three emulator tests were skipped because `FIRESTORE_EMULATOR_HOST` was not configured, and the Firebase CLI is not installed in this environment. The browser smoke's synthetic expense was cleared by restarting the in-memory API. The attempted delete-all action reported zero prior expenses; no existing workspace records were deleted.

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
- 2026-10-15: documented integration-persona scope and current handoff status; no runtime behavior changed and no checks were rerun.
- 2026-10-16: enforced the pending-review gate for monthly insights, added the UI review-to-insights flow, and verified API, frontend, and in-memory browser behavior; no live OpenAI calls or cloud persistence used.
