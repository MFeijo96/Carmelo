# Local Setup Record

## Scope

Credential-free local setup for the synthetic-data Home Financial MVP. The browser and API must remain loopback-only; the unauthenticated API is not suitable for real financial data or LAN/public exposure.

## Prerequisites

- Python 3.11 or later.
- Node.js and npm compatible with the committed frontend lockfile.
- Optional Firestore Emulator mode: Firebase CLI, Java 21 or later, the backend `firestore` extra, and a loopback emulator host.

## Environment

From `backend/`, install the API and development tooling from the committed lock with `uv sync --extra dev`, then copy `.env.example` to `.env`. The example lists `APP_ENV`, `PERSISTENCE_MODE`, `FIREBASE_PROJECT_ID`, `FIRESTORE_EMULATOR_HOST`, and OpenAI model/key/timeout settings; the example key is empty. OpenAI is optional.

For emulator use, install `uv sync --extra dev --extra firestore` and set both `PERSISTENCE_MODE=firestore-emulator` and `FIRESTORE_EMULATOR_HOST=127.0.0.1:8080`; configure `FIREBASE_PROJECT_ID` as well. Missing emulator configuration fails closed. Do not configure Cloud Firestore/ADC for this MVP.

## Run

- Backend: from `backend/`, run `uv run home-financial-api`; it binds to `127.0.0.1:8000`.
- Frontend: from `frontend/`, run `npm ci` then `npm run dev`; Vite binds to `127.0.0.1:5173`.
- API docs: open `/docs` or `/openapi.json` on the local API.

In-memory data is lost when the API process restarts. Use synthetic data only.

## Verification

- Backend: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy src` from `backend/`.
- Frontend: `npm test`, `npm run build`, and `npm audit` from `frontend/`.
- Emulator: start `npx firebase-tools emulators:start --only firestore --project demo-home-financial` from the workspace root, then run `FIRESTORE_EMULATOR_HOST=127.0.0.1:8080 FIREBASE_PROJECT_ID=demo-home-financial uv run pytest` from `backend/`. Without the host, emulator tests skip.
- API contract: `backend/openapi.json` must match the running API; see `backend/README.md` to regenerate it.

## Sources

- `backend/README.md` and `frontend/README.md`.
- `backend/.env.example` and `backend/pyproject.toml`.
- `project-context/1.define/sad.md` deployment and persistence decisions.

## Assumptions

- Python and Node installations are managed outside this repository.
- The default runtime uses in-memory repositories and does not require provider credentials.

## Open Questions

- Python dependency locking is provided by `backend/uv.lock`; the five CrewAI-pinned ChromaDB advisories are recorded as accepted risk in `security.md`.
- Emulator verification passed on 2026-10-12 with a user-space JRE; CI must provision Java itself.

## Audit

- 2026-10-12: setup instructions reconciled with current loopback entry points and emulator fail-closed settings.
