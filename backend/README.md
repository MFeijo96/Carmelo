# Home Financial Backend

Local-only FastAPI backend with in-memory demo repositories, deterministic expense workflows,
REST endpoints, and optional CrewAI/OpenAI classification and insight adapters.

## Local setup

From this directory, create and activate a Python 3.11+ virtual environment, then run:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cp .env.example .env
home-financial-api
```

The API binds to `127.0.0.1:8000`. Check `http://127.0.0.1:8000/health` or open the generated
OpenAPI document at `http://127.0.0.1:8000/docs`. Use synthetic data only. The default memory
adapter loses records when the process restarts.

Implemented routes cover the demo household, CSV/manual expense input, expense/category review,
monthly dashboard and insights, CSV/JSON export, demo-data deletion, and categorization evaluation.
CSV imports use a raw UTF-8 body with `Content-Type: text/csv` or `text/plain`. JSON API responses
use the shared `data` / `errors` / `meta` envelope; CSV download metadata is returned in headers.

`OPENAI_API_KEY` is optional. Without it, classification uses deterministic rules and insights
use a deterministic summary. With a key, CrewAI is used only for unresolved classification when a
trusted safe context is present, or for insight writing from aggregate summaries. Provider inputs
never include raw merchant names, original descriptions, source record IDs, or reversible alias
maps. The evaluator uses the committed 30-record golden dataset by default; override it with
`EVALUATION_DATASET_PATH` if needed. The dataset is JSON with a `version` string and a `records` array; each record has an ISO `date`,
`description`, integer `amount_cents`, `payment_method`, `recurring`, and canonical leaf
`expected_category_id` fields. Evaluation is deterministic and does not invoke CrewAI.

Run checks with:

```bash
pytest
ruff check .
ruff format --check .
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
python -m pip install -e ".[dev,firestore]"
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