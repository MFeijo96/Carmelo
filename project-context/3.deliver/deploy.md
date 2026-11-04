# Docker Compose Deployment

## Release Readiness

- The existing QA record documents passing backend and frontend verification. Emulator-backed browser verification and independent persona approval remain open.
- The security assessment documents that the MVP is unauthenticated and is not suitable for real financial data or public/LAN exposure.
- This is a local container setup, not a production deployment.

## Deployment Definition

The Compose stack builds and runs two services:

| Service | Container behavior | Host access |
| --- | --- | --- |
| `backend` | Python 3.11, locked dependencies, FastAPI served by Uvicorn | `127.0.0.1:8000` |
| `frontend` | Node 22 production build served by Nginx | `127.0.0.1:5173` |

Both ports are published on host loopback only. The frontend build defaults `VITE_API_BASE_URL` to `http://127.0.0.1:8000`; override it at build time only when the browser can safely reach the selected API. The backend health check gates frontend startup.

### Start and Stop

From the repository root with Docker Engine and Docker Compose v2.24 or newer:

```sh
docker compose up --build
```

Open `http://127.0.0.1:5173/`. The API health endpoint is `http://127.0.0.1:8000/health`, and API documentation is at `http://127.0.0.1:8000/docs`.

Stop the stack with:

```sh
docker compose down
```

Rebuild after source or build-configuration changes with `docker compose up --build`.

## Environment and Access

The backend optionally loads `backend/.env`; this local file is Git-ignored and is not copied into the image. Keep credentials out of build arguments and images. The frontend API address is a build argument (`VITE_API_BASE_URL`) and is not a secret.

Persistence defaults to in-memory storage. Records are lost when the backend process/container restarts or is recreated. The Firestore Emulator is not included in this Compose stack, and cloud Firestore is not supported. Use synthetic data only.

Copilot generation remains disabled by default. Enabling it in Docker requires a separately provisioned SDK runtime and suitable authentication; a host CLI listening on `127.0.0.1` is not reachable from the backend container via that address. No credentials or runtime are built into the image.

There is no authentication or authorization. Do not bind these services to a public or LAN interface, and do not use real financial data. The host bindings are intentionally restricted to loopback.

## Health, Observability, and Rollback

Compose checks `GET /health` on the backend before starting the frontend. Application logs are available through `docker compose logs backend` and `docker compose logs frontend`.

To roll back, stop the stack and build/run the previously reviewed source revision. `docker compose down` removes the containers but does not create a durable data backup; current in-memory data is ephemeral and cannot be recovered after a restart.

## Future Work

- Containerized Firestore Emulator integration and durable data lifecycle.
- A supported, isolated Copilot runtime and authentication flow for container use.
- Any hosted deployment, which remains blocked on authentication/authorization and a new security review.

## Sources

- `project-context/1.define/sad.md` — local-only deployment and deferred hosting decisions.
- `project-context/2.build/setup.md` — local runtime and environment configuration.
- `project-context/2.build/qa.md` — current test results and known validation gaps.
- `project-context/2.build/security.md` — unauthenticated MVP security boundaries.
- `backend/README.md` — backend and Docker Compose usage.
- `compose.yaml`, `backend/Dockerfile`, and `frontend/Dockerfile`.

## Assumptions

- Docker Engine and Docker Compose v2.24 or newer are installed by the operator.
- `AAMAD_TARGET_RUNTIME` is not specified in the checked-in project configuration; the AAMAD adapter registry default is CrewAI. This app's container runtime packages its Python/CrewAI backend and React/Vite frontend.
- Docker daemon/build access was unavailable during authoring, so image builds and container smoke tests remain to be run on a Docker-enabled machine.
- Local `.env` values may contain credentials; they are loaded at runtime only and must not be copied into an image or shared.

## Open Questions

- Should the optional Firestore Emulator become a Compose profile for local persistent integration testing?
- Should Copilot runtime provisioning be part of a separate, explicitly authorized container change?

## Audit

- 2026-11-04; persona: devops-eng; action: define-deploy. Resolved AAMAD runtime: CrewAI default; application services: Python/FastAPI/CrewAI backend and React/Vite frontend. Docker daemon unavailable in authoring environment; runtime image verification is pending. No live deployment performed. Prompt Trace omitted because this is local packaging of the existing synthetic-data MVP and no model inference was invoked.
