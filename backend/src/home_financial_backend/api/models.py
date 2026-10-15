from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

DataT = TypeVar("DataT")


class ApiError(BaseModel):
    code: str
    message: str
    field: str | None = None
    row: int | None = None
    value: str | None = None


class ApiMeta(BaseModel):
    request_id: str
    schema_version: str = "1.0"


class ApiEnvelope(BaseModel, Generic[DataT]):
    model_config = ConfigDict(extra="forbid")

    data: DataT | None
    errors: list[ApiError]
    meta: ApiMeta


class HealthData(BaseModel):
    status: str
