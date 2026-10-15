# QA Record

## Scope

Build-phase verification of deterministic backend services, API routes, CrewAI boundaries, frontend workflows, and the golden category evaluation. Results below are automated checks from the current workspace, not a claim of an independent QA persona approval.

## Test Results

- Backend: 40 passed and 3 skipped without an emulator; 43 passed and 0 skipped with the Firestore Emulator running.
- Frontend: 42 passed across six test files.
- Frontend TypeScript and production build: passed.
- Backend Ruff lint/format and `mypy src` (31 files): passed.
- Frontend `npm audit`: zero vulnerabilities.
- AAMAD validation: passed with no validation issues.
- Python dependency audit: five advisories remain in `chromadb==1.5.9` (CrewAI-pinned, no fix published); assessed as unreachable and recorded as accepted risk in `security.md`.
- Secret scans: Gitleaks 8.30.1 and `detect-secrets` found nothing.

## Acceptance Coverage

- Expense validation, CSV row handling, active-leaf category rules, correction precedence, and exact monthly arithmetic are covered by backend tests.
- Insight source membership, unsafe/ungrounded output rejection, pt-BR validation, timeout fallback, and deterministic fallback are covered.
- The persisted merchant alias projection is covered for stability, hints/recurrence, exclusion of raw values from provider prompts, export exclusion, and deletion. OpenAPI drift is guarded in both the backend and frontend suites (mutation-checked).
- Emulator-backed runs cover CSV import-to-dashboard, persistence, export, deletion, and alias handling.
- Frontend component coverage includes import reports, expense correction, category create/rename/merge, evaluation output, exports, and deletion confirmation.
- Golden evaluation uses 30 synthetic records, runs with deterministic classification and no provider, and measures 30/30 exact matches.

## Outstanding Gates

- Independent security review and a full WCAG review remain outstanding.
- No full desktop/mobile browser regression was run after the final changes; earlier spot checks showed no horizontal overflow.
- The emulator runs used a user-space Temurin 21 JRE and Firestore Emulator 1.22.0; CI should provision these itself.

## Sources

- `backend/tests/` and `frontend/src/` test suites.
- `project-context/1.define/prd.md` acceptance criteria and `project-context/1.define/sad.md` quality scenarios.
- `project-context/2.build/backend.md` and `project-context/2.build/frontend.md`.

## Assumptions

- Emulator skips are not counted as passing integration gates.
- Golden evaluation accuracy is tied to the committed synthetic dataset and current deterministic rules.

## Open Questions

- Run the emulator tests in CI, and re-audit the ChromaDB advisories when a fix is published.
- Obtain independent QA and security review before any cloud or hosted deployment.

## Audit

- AAMAD_TARGET_RUNTIME: crewai.
- 2026-10-12: automated test and static-check results recorded from the local workspace; no persona approval is implied.
