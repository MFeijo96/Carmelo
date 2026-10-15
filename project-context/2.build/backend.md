# Home Financial: Backend Build Record

## Scope Baseline

- MVP runtime: Python 3.11+, FastAPI, and CrewAI.
- Deployment: local/demo only, bound to `127.0.0.1`; synthetic data only. The unauthenticated API is not suitable for real household data or public/LAN exposure.
- One shared demo household; no login, household selector, member identity, invitations, or role enforcement.
- Deterministic Python services own validation, classification precedence, persistence, financial arithmetic, export/deletion, and evaluation. CrewAI is reserved for unresolved classification ambiguity and writing insights from precomputed summaries.
- Persistence begins with in-memory repositories, then the Firestore Emulator. Cloud Firestore and ADC remain gated on emulator persistence/export/deletion tests and security review.
- Provider access is optional. Secrets stay server-side in environment variables. Provider prompts must use only the SAD allow-listed alias-safe projection.
- This scope is traced to the PRD and SAD. Future authentication, bank integrations, regulated advice, and public hosting remain out of MVP.

## API Contract Draft

The frontend integration uses this contract baseline. FastAPI publishes the machine-readable schema at `/openapi.json`; request/response shapes and the raw CSV transport are exercised by route and frontend service tests. No separate persona sign-off is recorded. The response envelope is:

```json
{
  "data": {},
  "errors": [],
  "meta": {
    "request_id": "string",
    "schema_version": "1.0"
  }
}
```

Each error can include a machine-readable `code`, pt-BR `message`, `field`, CSV `row`, and supplied `value`. The implemented API routes are:

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Return non-secret readiness and persistence mode |
| GET | `/households/demo` | Return the single demo workspace |
| POST | `/imports/csv` | Validate/import valid rows and report row errors |
| POST | `/expenses` | Create a manual expense |
| GET | `/expenses` | List/filter expenses |
| PATCH | `/expenses/{expense_id}/category` | Correct an expense category |
| GET | `/categories` | List household taxonomy |
| POST | `/categories` | Create a household leaf category |
| PATCH | `/categories/{category_id}` | Rename/update a household leaf |
| POST | `/categories/merge` | Merge household leaves and reassign expenses |
| GET | `/dashboard/monthly` | Return deterministic monthly totals/breakdowns |
| POST | `/insights/monthly` | Generate grounded insight cards or deterministic fallback |
| GET | `/exports/expenses.csv` | Export expenses using the import schema |
| GET | `/exports/archive.json` | Export the household archive |
| DELETE | `/households/{household_id}/demo-data` | Delete household-owned demo data, retaining the empty household |
| POST | `/evaluation/categorization` | Run deterministic golden-dataset evaluation |

The frontend now uses the manual expense, category, dashboard, insight, CSV import, expense review/correction, category management, export/delete, and evaluation routes. CSV is sent as a raw UTF-8 body with `Content-Type: text/csv`; JSON endpoints use the shared envelope. Expense review requests the selected month and optional review flag, with a page size of 100.

## Scaffold

- `backend/` contains a setuptools/Python project with FastAPI, CrewAI, Pydantic Settings, PyYAML, Uvicorn, pytest, and Ruff dependencies.
- The API has request IDs, local frontend CORS origins, shared success/error envelopes, and a non-secret health readiness response.
- The API entry point fixes the bind address to `127.0.0.1:8000`.
- CrewAI agent/task definitions are externalized under `src/home_financial_backend/config/`. Separate factories build a sequential, memory-disabled crew for the selected task; an LLM object is injected only when configured.
- Runtime output models reject extra fields and enforce the SAD schemas. The optional OpenAI LLM uses configured model, temperature, token, and timeout settings. No provider request occurs during startup.
- The API exposes the documented household, expense/import, category, monthly dashboard/insight, CSV/JSON export, deletion, and categorization-evaluation routes. Evaluation uses the committed golden dataset by default and accepts `EVALUATION_DATASET_PATH` as an override.

## Domain And Repository Baseline

- Pydantic domain records cover household, category, expense, import run/errors, classification decision, insight card/run, evaluation run, merchant context, and the internal LLM data map.
- Money is represented as positive integer BRL cents; payment method and recurrence are separate fields. Persisted expenses require a category ID and source.
- API request/result schemas are defined for manual expense input, category changes, expense/category lists, import results, monthly requests, insight results, and evaluation.
- Protocols and in-memory/Firestore Emulator adapters cover household, category, expense, classification-decision, import-run, insight-run, evaluation-run, and merchant-context access. Writes are household-scoped and expense categories must be active leaves.
- The seeded demo workspace has one household and the twelve PRD top-level categories, plus `Mercado`, `Restaurantes`, and `Assinaturas` as the specified child leaves. New expense storage starts empty.
- The FastAPI app selects memory or Firestore Emulator repositories from `PERSISTENCE_MODE`, then constructs expense/classification/CSV and other services on application state.
- Manual expense creation, category correction history, Portuguese CSV parsing/validation, deterministic monthly aggregation, exports/deletion, and classification are implemented as services. CSV row errors preserve valid rows; malformed structure rejects before writes. Global correction frequency is used only to break a household-frequency tie.
- CrewAI classification receives only a stable fictitious merchant alias, a business-context description, category hints, aggregate recurrence count, and active-leaf labels paired with per-call opaque option tokens; the adapter maps the selected token back to a category ID locally. Insight tasks receive deterministic aggregate summaries, the same allow-listed merchant projection for merchants in the selected month, and opaque source-group tokens. `MerchantContextService` owns the reversible alias map (`merchant_contexts`, `llm_data_maps`), which is backend-only, excluded from exports, and removed by demo-data deletion. Provider output is schema/source/safety checked; invalid, ungrounded, unsafe, or failed calls use deterministic fallback.
- Golden evaluation loads a committed 30-record synthetic JSON dataset (or path override), runs with LLM fallback disabled and isolated correction history, calculates exact-label accuracy/confusion, and stores the report. The measured result is 30/30 (100%).
- Firestore collections are top-level and household-filtered. Emulator mode requires the optional Firestore SDK extra, `FIRESTORE_EMULATOR_HOST`, and `FIREBASE_PROJECT_ID`; it rejects non-loopback hosts and cannot silently fall back to cloud access (verified: startup raises without the host). The emulator gate passed on 2026-10-12 against Firestore Emulator 1.22.0: CSV import-to-dashboard, repository persistence, CSV/JSON export, deletion, and merchant alias persistence/exclusion/deletion tests all pass, and an HTTP smoke run in emulator mode confirmed valid rows import while an invalid row is rejected.
- In-memory persistence remains the default. Cloud Firestore/ADC remains disabled until an independent security review approves it.
- `backend/openapi.json` is the committed contract snapshot. A backend test fails on drift from the running API and a frontend test fails when the UI calls an operation absent from it; both were mutation-checked.

## Local Setup And Checks

From `backend/`, use Python 3.11+ and `uv sync --extra dev` to install from `uv.lock`; copy `.env.example` to `.env`, then start with `uv run home-financial-api`. Add `--extra firestore` for the emulator adapter. Run `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy src`. The golden dataset is included; OpenAI and emulator settings are optional. The emulator needs the Firebase CLI and Java 21 or later.

## Open Questions

- No separate integration-persona sign-off is recorded; compatibility is evidenced by the OpenAPI snapshot guards, route tests, and frontend tests.
- Accepted residual risk: `pip-audit` reports five advisories (PYSEC-2026-311, -3813, -3814, -3815) against `chromadb==1.5.9`, a CrewAI dependency pinned `~=1.5.9`. 1.5.9 is the latest release and no fix version is published. They concern the ChromaDB server (authentication, RBAC, code injection). This application never imports ChromaDB, runs both crews with `memory=False`, and starts no ChromaDB server. Re-audit when CrewAI or ChromaDB publishes a fix. The pytest advisory was resolved by requiring pytest 9.0.3 or later.
- Gitleaks 8.30.1 (checksum-verified) scanned the whole working tree and found no leaks; `detect-secrets` also reported no findings. `npm audit` reported zero frontend vulnerabilities.
- No independent security review has been performed; Cloud Firestore/ADC and any hosted use remain out of scope until one is.

## Audit

- Date: 2026-10-12; persona: backend.eng; action: implement-rest-and-crewai-boundaries.
- AAMAD_TARGET_RUNTIME: crewai, from `aamad.config.yml`; Python 3.11.16 is available in the workspace environment.
- LLM: optional OpenAI; defaults `gpt-4o-mini`, temperature `0.1`, max tokens `800`, timeout `15s`. No API request is made without `OPENAI_API_KEY`.
- Crew controls: sequential process, memory disabled, delegation disabled, classifier `max_iter=1`, insight `max_iter=2`, crew `max_rpm=6`.
- Domain/service validation: tests cover route workflows, shared error envelopes, deterministic arithmetic, classification precedence, CSV behavior, safe-context privacy including opaque classifier option IDs and the persisted merchant alias projection, insight safety/pt-BR/timeout fallback, and configured LLM-free evaluation.
- Verification: 40 backend tests pass and 3 emulator tests skip without `FIRESTORE_EMULATOR_HOST`; with the Firestore Emulator running, 43 pass and none skip. Ruff lint/format and `mypy src` (31 files, with YAML stubs) pass. Golden evaluation measured 30/30. CrewAI 1.15.27 construction emitted upstream deprecation warnings but succeeded.
- Retry control: installed CrewAI 1.15.27's `Crew` signature does not expose the adapter's generic `max_retry_limit` parameter; provider failures are bounded by adapter fallback and deterministic service behavior instead.
- No real financial data or secrets used. No cloud database connection or commit added.

## Sources

- `project-context/1.define/prd.md`: P0.1-P0.10, security constraints, and MVP Definition of Done.
- `project-context/1.define/sad.md`: runtime, repository, API, privacy, emulator, and deployment decisions.
- `backend/README.md`, `backend/src/home_financial_backend/api/routes.py`, and `backend/tests/`.

## Assumptions

- The single seeded demo household is the only workspace in this unauthenticated local MVP.
- API compatibility is evidenced by the OpenAPI snapshot guards, route/service tests, and frontend usage; it is not a substitute for an independent integration sign-off.
- Cloud Firestore and ADC remain disabled until an independent security review approves them.