# Home Financial Backend

Local-only FastAPI backend with in-memory demo repositories, deterministic expense workflows,
REST endpoints, and optional CrewAI/GitHub Copilot SDK classification and insight adapters.

## Local setup

From this directory, use Python 3.11+ and `uv`:

```bash
uv sync --extra dev
cp .env.example .env
uv run home-financial-api
```

The API binds to `127.0.0.1:8000`. Check `http://127.0.0.1:8000/health` or open the generated
OpenAPI document at `http://127.0.0.1:8000/docs`. Use synthetic data only. The default memory
adapter loses records when the process restarts.

Implemented routes cover the demo household, CSV/manual expense input, expense/category review,
monthly dashboard and insights, CSV/JSON export, demo-data deletion, and categorization evaluation.
CSV imports use a raw UTF-8 body with `Content-Type: text/csv` or `text/plain`. JSON API responses
use the shared `data` / `errors` / `meta` envelope; CSV download metadata is returned in headers.

`COPILOT_ENABLED=false` is the default: classification uses deterministic rules and insights
use a deterministic summary. When enabled, CrewAI is used only for unresolved classification when a
trusted safe context is present, or for insight writing from aggregate summaries. Provider inputs
never include raw merchant names, original descriptions, source record IDs, or reversible alias
maps. The evaluator uses the committed 30-record golden dataset by default; override it with
`EVALUATION_DATASET_PATH` if needed. The dataset is JSON with a `version` string and a `records` array; each record has an ISO `date`,
`description`, integer `amount_cents`, `payment_method`, `recurring`, and canonical leaf
`expected_category_id` fields. Evaluation is deterministic and does not invoke CrewAI.

## GitHub Copilot

The official `github-copilot-sdk==1.0.23` is pinned in the lockfile. It supplies model responses
through a custom CrewAI `BaseLLM`, not an OpenAI-compatible endpoint. OpenAI and Ollama/Llama
provider settings are no longer read by the application; their old environment entries can be removed.
CrewAI may still require provider libraries transitively.

Provision the SDK's matching runtime before enabling requests:

```bash
uv run python -m copilot download-runtime
```

The pinned SDK currently provisions runtime v1.0.100. A compatible externally installed CLI can
instead be selected with `COPILOT_CLI_PATH`. Authenticate locally using the official Copilot CLI
login flow, or supply `COPILOT_GITHUB_TOKEN` server-side for automation. The adapter passes
`use_logged_in_user=true` without a token; an explicit token disables that fallback. The SDK's
`empty` mode disables keychain probing, so availability of stored CLI identity depends on the
runtime's supported local authentication path. To reuse an already authenticated CLI without
reading/copying its credentials, run `copilot --headless --port 4321` locally and set
`COPILOT_CLI_URL=127.0.0.1:4321`. This SDK connection still uses `mode="empty"`; only loopback
addresses are accepted. Use either `COPILOT_CLI_URL` or `COPILOT_CLI_PATH`, not both. The external
CLI remains operator-owned: request cleanup disconnects the SDK and deletes only its own session,
without stopping the server. Alternatively, supply an explicit automation token or keep provider
access disabled. Never put a token in frontend configuration,
logs, source control, or shell command history.

Set `COPILOT_MODEL` to an identifier supported by the authenticated account and organization policy,
then set `COPILOT_ENABLED=true` and restart the API. No model is assumed by default. Startup
validates configuration but does not start the Copilot runtime, verify authentication, or generate
text; `/health` reports provider configuration, not successful authentication. An enabled provider
without a model fails configuration validation. `LLM_TIMEOUT_SECONDS` defaults to 15 (range: >0 to
120). There is no assumed temperature/max-output-token parity with OpenAI in this SDK integration.

Each generation creates an isolated non-streaming session in `mode="empty"`, with tools, memory,
skills, configuration discovery, session store and infinite-session compaction disabled. CrewAI
retains orchestration and Pydantic output validation. A classification task has at most one SDK
generation; insights have at most two, sharing one task deadline. A failed call prevents further SDK
calls in that task. Sessions are disconnected/deleted and owned clients are stopped after each
request, including errors and cancellation; cleanup has a separate bounded allowance (up to 3s).
The async CSV route offloads synchronous service/CrewAI execution to the thread pool.

Missing runtime/authentication, unsupported models, account-policy/quota failures, timeouts and
invalid responses use deterministic fallbacks. Model responses still undergo source, privacy and
safety checks. Copilot usage is attributed to the operator's account/organization and its AI Credits
policy, not a household identity or a fixed per-request price. Reported token counts are recorded;
missing counts remain `null`. Available native `copilot_nano_aiu` usage is logged without converting
it to USD or inventing a credit charge; the existing `estimated_cost_usd` field stays `null`.

Tests use signature-checked SDK fakes and require no credentials/network or paid generations.
Real generation smoke tests require operator authorization and synthetic alias-safe inputs.

Run checks with:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

The API stays bound to loopback and is not suitable for real household data or public/LAN exposure.

## API contract

`openapi.json` is the committed contract snapshot. A backend test fails when it drifts from the
running API, and a frontend test fails when the UI calls an operation missing from it. After an
intentional API change, regenerate it from this directory and review the diff:

```bash
python -c "import json; from home_financial_backend.main import app; open('openapi.json', 'w', encoding='utf-8').write(json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + '\n')"
```

Static typing is checked with `mypy src`.
## Firestore Emulator

The Firestore adapter is opt-in and never falls back to cloud Firestore. Install its extra from
this directory:

```bash
uv sync --extra dev --extra firestore
```

The emulator requires the Firebase CLI and a supported Java runtime. Start it from the workspace
root with:

```bash
npx --yes firebase-tools emulators:start --only firestore --project demo-home-financial
```

In another terminal, select emulator mode before starting the API:

```bash
PERSISTENCE_MODE=firestore-emulator \
FIREBASE_PROJECT_ID=demo-home-financial \
FIRESTORE_EMULATOR_HOST=127.0.0.1:8080 \
backend/.venv/bin/home-financial-api
```

Run the persistence/export/deletion gate with the emulator active:

```bash
FIRESTORE_EMULATOR_HOST=127.0.0.1:8080 \
FIREBASE_PROJECT_ID=demo-home-financial \
backend/.venv/bin/python -m pytest backend/tests/test_firestore_emulator.py
```

The integration test skips if the SDK extra or emulator host is unavailable. Emulator mode
requires both project ID and loopback emulator host; missing configuration fails startup.