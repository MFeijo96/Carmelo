import json
from pathlib import Path

from home_financial_backend.main import app

SNAPSHOT = Path(__file__).resolve().parents[1] / "openapi.json"


def test_committed_openapi_snapshot_matches_the_running_api() -> None:
    current = json.loads(json.dumps(app.openapi(), sort_keys=True, ensure_ascii=False))
    committed = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    assert committed == current, (
        "backend/openapi.json is stale; regenerate it and review the contract change "
        "(see backend/README.md)."
    )
