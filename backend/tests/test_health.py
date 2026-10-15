from fastapi.testclient import TestClient

from home_financial_backend.main import app

client = TestClient(app)


def test_health_uses_the_shared_response_envelope() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "status": "ok",
            "provider_configured": False,
            "persistence_mode": "memory",
        },
        "errors": [],
        "meta": {
            "request_id": response.headers["X-Request-ID"],
            "schema_version": "1.0",
        },
    }
