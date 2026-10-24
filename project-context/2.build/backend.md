# Home Financial: Backend Build Record

## Scope Baseline

- MVP runtime: Python 3.11+, FastAPI, and CrewAI.
- Deployment: local/demo only, bound to `127.0.0.1`; synthetic data only. The unauthenticated API is not suitable for real household data or public/LAN exposure.
- One shared demo household; no login, household selector, member identity, invitations, or role enforcement.
- Deterministic Python services own validation, classification precedence, persistence, financial arithmetic, export/deletion, and evaluation. CrewAI is reserved for unresolved classification ambiguity and writing insights from precomputed summaries.
- Persistence begins with in-memory repositories, then the Firestore Emulator. Cloud Firestore and ADC remain gated on emulator persistence/export/deletion tests and security review.
- Target provider: GitHub Copilot through its official Python SDK behind a CrewAI-compatible adapter (SAD AD-05). Remove the application's OpenAI and Ollama/Llama provider paths; CrewAI remains the orchestration runtime. Provider access is optional, credentials remain server-side, and prompts use only the SAD allow-listed alias-safe projection.
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
- Runtime output models reject extra fields and enforce the SAD schemas. The official `github-copilot-sdk==1.0.23` now supplies model responses through a custom CrewAI `BaseLLM`; application OpenAI and Ollama/Llama provider paths/settings have been removed. SDK construction, runtime startup and model generation are deferred until a task actually needs them; application startup makes no provider request.
- The API exposes the documented household, expense/import, category, monthly dashboard/insight, CSV/JSON export, deletion, and categorization-evaluation routes. Evaluation uses the committed golden dataset by default and accepts `EVALUATION_DATASET_PATH` as an override.

## Copilot SDK Migration Plan

Status: implemented on 2026-10-19 by backend.eng, with offline SDK/CrewAI integration tests and a real local runtime startup/status/shutdown check. Subsequent operator setup confirmed SDK authentication and account model availability; local Copilot access is enabled with `claude-haiku-4.5`. Real model generation remains unverified because no credit-consuming generation was performed. The sequence below records the migration scope and acceptance criteria; it does not assert generation acceptance or independent security approval.

### Architecture And Invariants

- Required path: deterministic services -> selected CrewAI task -> custom CrewAI-compatible LLM adapter -> official GitHub Copilot Python SDK -> GitHub Copilot. Do not use a Copilot OpenAI-compatible endpoint, LiteLLM routing, or an Ollama/Llama fallback.
- Preserve sequential execution, `memory=false`, `allow_delegation=false`, classifier `max_iter=1`, insight `max_iter<=2`, and bounded request/retry controls. CrewAI remains the only orchestrator.
- Each generation request creates an isolated Copilot session with `mode="empty"`, no tools, and no memory. Return response text to CrewAI for existing Pydantic output validation; do not make experimental SDK structured output the application contract.
- Preserve deterministic classification precedence, financial calculations, alias-safe prompt projection, grounding/safety checks, and fallback behavior. Golden acceptance evaluation continues with LLM disabled and zero provider calls.
- Preserve HTTP routes, response envelopes, OpenAPI compatibility, frontend integration, and persistence boundaries. Local/demo, synthetic-data, loopback-only and cloud-security gates remain unchanged.

### Implementation Sequence

| Step | Planned work | Acceptance evidence |
| --- | --- | --- |
| 1. SDK compatibility and configuration | Verify the official Python SDK's supported release, Python/CrewAI compatibility, CLI/runtime prerequisites, authentication and session APIs. Add the SDK and update the lockfile; remove direct application dependencies/configuration specific to OpenAI and Ollama. Replace legacy settings with `COPILOT_MODEL`, optional automation-only `COPILOT_GITHUB_TOKEN`, and provider-neutral timeout/enablement controls. | Reproducible dependency installation and settings tests; no application provider path reads `OPENAI_*` or `OLLAMA_*`. Do not remove transitive dependencies required by CrewAI merely because of their names. |
| 2. CrewAI-compatible adapter | Replace provider construction with the Copilot adapter; bridge CrewAI calls to the SDK lifecycle without blocking the API event loop. Bound calls, close/disconnect request sessions on success, error, timeout and cancellation, and shut down any owned client/runtime resources. Keep provider requests out of application startup. | Fake-SDK adapter tests demonstrate model selection, isolated sessions, text return, bounded failures and resource cleanup without network access. |
| 3. Service integration and fallback | Inject the adapter into the existing classification/insight tasks. Support authenticated local Copilot CLI usage without requiring an automation token. Translate absent authentication, unsupported model/policy, exhausted allowance, timeout and invalid response into the established failure path. | Classification falls back to `outros` with review required; insights return deterministic summaries; dashboard arithmetic remains available. Tests cover both local identity and explicit server-side token configuration. |
| 4. Privacy and usage metadata | Reuse the allow-listed prompt builders and output validators. Keep raw merchants, original descriptions, mappings, credentials and session identifiers out of provider payloads, public responses and logs. Replace OpenAI USD-price assumptions with available Copilot usage/credit metadata; represent unavailable metrics as unknown, never invented or zero-cost. | Payload/privacy and output-validation regressions pass; usage tests distinguish reported metrics from unavailable values and do not assume a fixed per-request credit cost. |
| 5. Setup, regression and handoff | Update backend setup documentation and environment example for Copilot SDK/runtime, CLI authentication, optional automation token, supported model selection and fallback-only operation. Remove OpenAI/Ollama setup instructions from the active backend flow; record actual supported controls and defaults. | Backend tests, lint/format/type checks, unchanged OpenAPI snapshot and AAMAD validation pass. An explicitly authorized synthetic-data Copilot smoke test validates the real SDK path; otherwise record live integration as unverified. |

### Verification Gates

1. Run focused adapter/settings tests using SDK fakes before service integration. Cover disabled mode, local CLI identity without token, explicit token, isolated sessions, no tools/memory, timeout, cancellation, authentication/model failures, malformed output and cleanup. Unit tests and default CI must not require Copilot credentials, network access, or paid usage.
2. Run existing runtime-boundary, CrewAI scaffold, merchant-privacy, expense-service, API/OpenAPI and usage tests after integration. Add regressions to the existing suites where practical. Verify zero provider calls for deterministic evaluation and startup, and unchanged frontend-facing contracts.
3. Run `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src`, and `aamad validate`. Emulator-dependent tests require the existing local emulator setup; missing prerequisites must be reported, not counted as a passing gate.
4. Run a real Copilot smoke test only with operator authorization for account usage and synthetic alias-safe inputs. Record the SDK/runtime versions, selected model, actual supported generation controls, elapsed time, response validation and available usage metadata without secrets or sensitive prompts. Verify successful classification and insights plus deterministic fallback when access fails; target monthly insight latency remains under 20 seconds per SAD.

Completion means the application no longer selects OpenAI or Ollama/Llama, the Copilot adapter satisfies these gates, and documentation reflects verified behavior. No completion or independent integration/security approval is asserted by this planning update.

### Implementation And Verification Record

- Configuration: `COPILOT_ENABLED=false` by default; enabling requires an explicit `COPILOT_MODEL`. `COPILOT_GITHUB_TOKEN` is optional, secret-valued and excluded from settings/adapter serialization and repr. `LLM_TIMEOUT_SECONDS=15` is provider-neutral and validated (>0, <=120); no unsupported temperature/output-token settings are forwarded.
- Authentication/runtime: managed stdio uses runtime v1.0.100, provisioned by the pinned SDK. `COPILOT_CLI_PATH` can select a compatible executable. An optional `COPILOT_CLI_URL` connects only to a loopback CLI already authenticated by the operator; it is mutually exclusive with the path override. This supports local CLI identity without extracting credentials when `empty` mode prevents keychain probing. Explicit tokens are passed server-side and disable logged-in-user fallback; external runtimes remain operator-owned.
- Lifecycle: isolated `mode="empty"` sessions disable tools, memory, skills, configuration discovery, host git operations, session store, telemetry and infinite-session compaction. The adapter returns text for CrewAI validation, disconnects/deletes request sessions, and stops owned clients. Cleanup is bounded separately to at most 3s, including forced shutdown after graceful stop failure.
- Bounds/failures: each classification task has at most one SDK generation; insights have at most two, with a shared task deadline. SDK failure blocks subsequent SDK generations in that task and retains a sanitized cause across CrewAI internal retries. Authentication, timeout, quota and invalid-output failures preserve existing fallback statuses. The CSV route runs synchronous services in the thread pool so provider calls cannot block the API event loop.
- Usage/contracts: optional SDK token counts are retained; unavailable metrics remain `null`. Native `copilot_nano_aiu` is logged when reported, without conversion into USD or an assumed fixed AI Credits charge. `estimated_cost_usd` stays `null`. Routes, response schemas and the existing OpenAPI snapshot remain unchanged by this migration.
- Verification: 81 backend tests pass, with 3 Firestore Emulator tests skipped because the emulator is not running. The new 26-case SDK suite uses signature-checked SDK fakes and real CrewAI classification/insight execution, including authentication, model, quota, timeout, cancellation, bounded retries, cleanup, optional usage and privacy tests. No paid model generation was made. Ruff lint, mypy (33 source files), Pylance syntax/diagnostics and formatting of the 10 touched Python files pass.
- Remaining gates: the global format check reports a preexisting formatting difference in `services/expenses.py`, preserved because it is outside this migration. Firestore Emulator regressions and authenticated Copilot generation remain unverified in this run. The actual backend environment dependency audit reports 20 advisory entries (including duplicates) across `chromadb==1.5.9`, `mcp==1.28.1`, `pip==24.0` and `setuptools==79.0.1`; no advisory was reported for the added Copilot SDK. These are not independent security approval or a clean full-environment audit.

## Domain And Repository Baseline

- Pydantic domain records cover household, category, expense, import run/errors, classification decision, insight card/run, evaluation run, merchant context, and the internal LLM data map.
- Money is represented as positive integer BRL cents; payment method and recurrence are separate fields. Persisted expenses require a category ID and source.
- API request/result schemas are defined for manual expense input, category changes, expense/category lists, import results, monthly requests, insight results, and evaluation.
- Protocols and in-memory/Firestore Emulator adapters cover household, category, expense, classification-decision, import-run, insight-run, evaluation-run, and merchant-context access. Writes are household-scoped and expense categories must be active leaves.
- The seeded demo workspace has one household and the twelve PRD top-level categories, plus `Mercado`, `Restaurantes`, and `Assinaturas` as specified child leaves and `Entretenimento` under `Lazer`. New expense storage starts empty.
- The FastAPI app selects memory or Firestore Emulator repositories from `PERSISTENCE_MODE`, then constructs expense/classification/CSV and other services on application state.
- Manual expense creation, category correction history, Portuguese CSV parsing/validation, deterministic monthly aggregation, exports/deletion, and classification are implemented as services. CSV row errors preserve valid rows; malformed structure rejects before writes. Global correction frequency is used only to break a household-frequency tie.
- CrewAI classification receives only a stable fictitious merchant alias, a business-context description, category hints, aggregate recurrence count, and active-leaf labels paired with per-call opaque option tokens; the adapter maps the selected token back to a category ID locally. Insight tasks receive deterministic aggregate summaries, the same allow-listed merchant projection for merchants in the selected month, and opaque source-group tokens. `MerchantContextService` owns the reversible alias map (`merchant_contexts`, `llm_data_maps`), which is backend-only, excluded from exports, and removed by demo-data deletion. Provider output is schema/source/safety checked; invalid, ungrounded, unsafe, or failed calls use deterministic fallback.
- Golden evaluation loads a committed 50-record synthetic JSON dataset v2 (or path override), runs with LLM fallback disabled and isolated correction history, calculates exact-label accuracy/confusion, and stores the report. The measured result is 50/50 (100%); regression tests cover threshold boundaries, repeatability, invalid labels/versions, and fallback isolation.
- Firestore collections are top-level and household-filtered. Emulator mode requires the optional Firestore SDK extra, `FIRESTORE_EMULATOR_HOST`, and `FIREBASE_PROJECT_ID`; it rejects non-loopback hosts and cannot silently fall back to cloud access (verified: startup raises without the host). The emulator gate passed on 2026-10-12 against Firestore Emulator 1.22.0: CSV import-to-dashboard, repository persistence, CSV/JSON export, deletion, and merchant alias persistence/exclusion/deletion tests all pass, and an HTTP smoke run in emulator mode confirmed valid rows import while an invalid row is rejected.
- In-memory persistence remains the default. Cloud Firestore/ADC remains disabled until an independent security review approves it.
- `backend/openapi.json` is the committed contract snapshot. A backend test fails on drift from the running API and a frontend test fails when the UI calls an operation absent from it; both were mutation-checked.

## Local Setup And Checks

From `backend/`, use Python 3.11+ and `uv sync --extra dev` to install from `uv.lock`; copy `.env.example` only when creating a new `.env`, preserving any existing private settings. Start with `uv run home-financial-api`. Add `--extra firestore` for the emulator adapter. Run `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy src`. The golden dataset is included; provider access and emulator settings are optional. For Copilot, provision the runtime with `uv run python -m copilot download-runtime`, configure an authenticated identity and supported `COPILOT_MODEL`, then enable `COPILOT_ENABLED`. See `backend/README.md` for the optional authenticated loopback CLI connection and automation token path. Old OpenAI/Ollama environment entries are ignored; the existing private `.env` was not edited. The emulator needs the Firebase CLI and Java 21 or later.

## Open Questions

- Copilot live acceptance: SDK 1.0.23/runtime 1.0.100 startup/status/shutdown, local authentication and enabled model availability are verified. The operator's local backend selects `claude-haiku-4.5`; the application's model default remains unset. A successful generation, measured generation latency and actual usage still require an explicitly authorized smoke test; no paid generation was performed.
- Dependency audit follow-up: beyond historical ChromaDB advisories, the current environment includes advisories for MCP and packaging tools. Remediation and independent security reassessment remain separate work; no cloud/hosted deployment is approved by this migration.
- No separate integration-persona sign-off is recorded; compatibility is evidenced by the OpenAPI snapshot guards, route tests, and frontend tests.
- Accepted residual risk: `pip-audit` reports five advisories (PYSEC-2026-311, -3813, -3814, -3815) against `chromadb==1.5.9`, a CrewAI dependency pinned `~=1.5.9`. 1.5.9 is the latest release and no fix version is published. They concern the ChromaDB server (authentication, RBAC, code injection). This application never imports ChromaDB, runs both crews with `memory=False`, and starts no ChromaDB server. Re-audit when CrewAI or ChromaDB publishes a fix. The pytest advisory was resolved by requiring pytest 9.0.3 or later.
- Gitleaks 8.30.1 (checksum-verified) scanned the whole working tree and found no leaks; `detect-secrets` also reported no findings. `npm audit` reported zero frontend vulnerabilities.
- No independent security review has been performed; Cloud Firestore/ADC and any hosted use remain out of scope until one is.

## Audit

### 2026-10-23: QA Evaluation and Browser Flow Follow-up

- Persona: qa-eng; action: implement-qa-evaluation-follow-up. AAMAD_TARGET_RUNTIME: `crewai`.
- Added the `Entretenimento` standard leaf under `Lazer` and corrected the entertainment classification rule to target an active leaf.
- Expanded the versioned synthetic golden dataset to 50 records; added evaluation boundary, repeatability, invalid category/version, and no-fallback checks.
- Verification: backend 92 passed/0 skipped with Firestore Emulator 1.22.0, Ruff lint and mypy passed, frontend 57 passed and build passed, AAMAD passed. Touched-file formatting passed; global format check retains an unrelated existing difference in `services/expenses.py`.
- AMP tracing is enabled only in the ignored local `.env`. CrewAI device login's trace grant returned HTTP 401, then one synthetic trace using `CREWAI_USER_PAT` and a fake local LLM was accepted; no model-provider call was made.
- Browser smoke used in-memory persistence, synthetic data, and disabled provider calls. Emulator, dependency audit, independent security/accessibility review remain open.

### 2026-10-19: Operator Copilot Configuration

- Persona: backend.eng; action: configure-local-copilot. Sources: operator authorization, existing provider/settings contract and live SDK authentication/model metadata.
- Installed official Copilot CLI 1.0.100 after operator approval and completed its device login. The system keychain is unavailable; the operator explicitly approved plaintext credential storage in the CLI's user configuration outside the repository. No credential was copied into project files, diagnostics or this artifact.
- Updated only non-secret local environment controls: `COPILOT_ENABLED=true`, `COPILOT_MODEL=claude-haiku-4.5`, `LLM_TIMEOUT_SECONDS=15`. SDK-managed stdio recognizes the CLI identity; no separate headless server or automation token is required in this environment.
- Verified SDK authentication and the selected model's enabled account policy without generation. Validated settings and adapter construction, then restarted the local API preserving `PERSISTENCE_MODE=firestore-emulator`, project `demo-home-financial` and emulator `127.0.0.1:8080`. `/health` returns `status=ok`, `provider_configured=true` and `persistence_mode=firestore-emulator`.
- Tools: official CLI installation/login, operator confirmation prompts, safe allow-listed environment inspection, SDK auth/model metadata, environment patch, focused configuration checks and HTTP health check. No source code or data deletion, model generation, sampling controls or credit spend; real generation acceptance remains pending. Prompt Trace omitted because no application prompt was submitted.

### 2026-10-19: Copilot SDK Implementation

- Persona: backend.eng; action: implement-copilot-sdk-adapter. AAMAD_TARGET_RUNTIME: `crewai`, from project configuration; CrewAI orchestration is preserved.
- Sources: revised SAD AD-05, runtime/privacy/fallback constraints and EC-013; the migration plan; official Python SDK and authentication/backend setup documentation; installed SDK and CrewAI signatures/runtime evidence.
- Artifacts: provider/settings/usage integration, bounded task scopes, CSV thread-pool boundary, Copilot setup/environment example and locked SDK dependency, focused tests and this build record. No frontend, private `.env`, SAD or unrelated user changes were rewritten; no commit created.
- Tools: targeted file reads/search, Pylance runtime snippets and syntax checks, `apply_patch`, `uv sync`, SDK runtime provisioning, pytest/Ruff/mypy, dependency audit and artifact validation. Model/temperature/max_tokens: no application model generation, no selected default model, no assumed unsupported sampling controls.
- Validation: 81 pass / 3 emulator skips; lint/type checks and touched-file formatting pass; global formatting has the unrelated preexisting expense-service difference. SDK runtime v1.0.100 starts/stops successfully; authentication status is false. The authoritative dependency scan targets `backend/.venv/lib/python3.11/site-packages`; an earlier `uv run --with pip-audit --local` scan covered only the tool overlay and is not evidence of a clean backend environment.
- Prompt Trace: no sensitive prompt/credential data captured; omitted for this local synthetic-data migration. Real provider output, credit usage and latency acceptance remain pending authenticated, operator-authorized smoke tests.

### 2026-10-19: Copilot Migration Planning

- Persona: backend.eng; action: replan-backend-for-copilot-sdk.
- AAMAD_TARGET_RUNTIME: `crewai`, as declared in `aamad.config.yml`; no runtime replacement is planned. An explicit environment override remains subject to the framework resolution rule.
- Source: revised SAD AD-05, QA-03/QA-04, Runtime-Conditional Configuration, Authentication & Secrets, AR-07 and EC-013, plus the user's request to remove OpenAI and Ollama/Llama.
- Change: superseded legacy provider planning with the official Python SDK adapter, bounded session lifecycle, backend-only authentication, privacy/fallback invariants, usage reporting and explicit acceptance gates. Existing completed-work evidence below is historical, not Copilot verification.
- Tool usage: repository document/configuration reads and targeted provider/settings inspection to distinguish implemented behavior from planned behavior; documentation patch and artifact validation. No application model execution, dependency installation, credential access, or provider request.
- Model/temperature/max_tokens: no application LLM executed; select the Copilot model from supported account models during implementation and record only SDK-supported controls. Do not carry forward OpenAI defaults without verification.
- Prompt Trace: omitted because this is a local MVP planning update, not a production-facing or financial-data execution.

### 2026-10-12: Historical Implementation Evidence

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