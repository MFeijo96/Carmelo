from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_EVALUATION_DATASET_PATH = str(
    Path(__file__).resolve().parents[2] / "data" / "golden-expenses.json"
)


class Settings(BaseSettings):
    app_env: str = "local"
    persistence_mode: Literal["memory", "firestore-emulator"] = "memory"
    firebase_project_id: str | None = None
    firestore_emulator_host: str | None = None
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_temperature: float = 0.1
    openai_max_tokens: int = 800
    openai_timeout_seconds: int = 15
    openai_input_usd_per_million_tokens: float | None = None
    openai_output_usd_per_million_tokens: float | None = None
    evaluation_dataset_path: str | None = DEFAULT_EVALUATION_DATASET_PATH

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
