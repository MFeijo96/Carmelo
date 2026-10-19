from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_EVALUATION_DATASET_PATH = str(
    Path(__file__).resolve().parents[2] / "data" / "golden-expenses.json"
)


class Settings(BaseSettings):
    app_env: str = "local"
    persistence_mode: Literal["memory", "firestore-emulator"] = "memory"
    firebase_project_id: str | None = None
    firestore_emulator_host: str | None = None
    copilot_enabled: bool = False
    copilot_model: str | None = Field(default=None, min_length=1, pattern=r"^\S+$")
    copilot_github_token: SecretStr | None = Field(default=None, exclude=True, repr=False)
    copilot_cli_path: str | None = None
    copilot_cli_url: str | None = Field(
        default=None, pattern=r"^(127\.0\.0\.1|localhost|\[::1\]):[0-9]+$"
    )
    llm_timeout_seconds: float = Field(default=15, gt=0, le=120)
    evaluation_dataset_path: str | None = DEFAULT_EVALUATION_DATASET_PATH

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("copilot_cli_url")
    @classmethod
    def validate_cli_port(cls, value: str | None) -> str | None:
        if value is not None and not 1 <= int(value.rsplit(":", 1)[1]) <= 65535:
            raise ValueError("COPILOT_CLI_URL requires a valid loopback port")
        return value

    @model_validator(mode="after")
    def require_copilot_model(self) -> "Settings":
        if self.copilot_enabled and not self.copilot_model:
            raise ValueError("COPILOT_MODEL is required when COPILOT_ENABLED=true")
        if self.copilot_cli_path and self.copilot_cli_url:
            raise ValueError("Configure COPILOT_CLI_PATH or COPILOT_CLI_URL, not both")
        return self


settings = Settings()
