import pytest

from home_financial_backend.infrastructure.bootstrap import create_repositories
from home_financial_backend.settings import Settings


def test_firestore_mode_fails_without_emulator_host(monkeypatch) -> None:
    monkeypatch.delenv("FIRESTORE_EMULATOR_HOST", raising=False)
    settings = Settings(
        persistence_mode="firestore-emulator",
        firebase_project_id="demo-home-financial",
        firestore_emulator_host=None,
    )

    with pytest.raises(RuntimeError, match="refusing cloud access"):
        create_repositories(settings)


def test_firestore_mode_rejects_non_loopback_emulator_hosts() -> None:
    settings = Settings(
        persistence_mode="firestore-emulator",
        firebase_project_id="demo-home-financial",
        firestore_emulator_host="firestore.example.net:8080",
    )

    with pytest.raises(RuntimeError, match="loopback host"):
        create_repositories(settings)
