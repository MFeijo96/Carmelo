import os
from urllib.parse import urlsplit

from home_financial_backend.infrastructure.memory_repositories import (
    DemoRepositories,
    create_demo_repositories,
)
from home_financial_backend.settings import Settings


def create_repositories(settings: Settings) -> DemoRepositories:
    if settings.persistence_mode == "memory":
        return create_demo_repositories()

    emulator_host = settings.firestore_emulator_host or os.getenv("FIRESTORE_EMULATOR_HOST")
    if not emulator_host:
        raise RuntimeError(
            "FIRESTORE_EMULATOR_HOST is required for firestore-emulator mode; refusing cloud access."
        )
    hostname = urlsplit(f"//{emulator_host}").hostname
    if hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("Firestore Emulator must bind to a loopback host.")
    if not settings.firebase_project_id:
        raise RuntimeError("FIREBASE_PROJECT_ID is required for firestore-emulator mode.")

    os.environ["FIRESTORE_EMULATOR_HOST"] = emulator_host
    from google.cloud import firestore

    from home_financial_backend.infrastructure.firestore_repositories import (
        create_firestore_demo_repositories,
    )

    client = firestore.Client(project=settings.firebase_project_id)
    return create_firestore_demo_repositories(client)
