from datetime import UTC, date, datetime
from math import isclose
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

PaymentMethod = Literal["dinheiro", "debito", "credito"]
ExpenseSource = Literal["manual", "csv"]
ClassificationSource = Literal[
    "user_supplied",
    "exact_household_correction",
    "deterministic_rule",
    "household_frequency",
    "global_frequency",
    "llm_fallback",
    "fallback_outros",
]
EVALUATION_THRESHOLD = 0.70


def utc_now() -> datetime:
    return datetime.now(UTC)


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Household(DomainModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    is_demo: bool = True
    schema_version: str = "1.0"
    created_at: datetime = Field(default_factory=utc_now)


class Category(DomainModel):
    id: str = Field(min_length=1)
    household_id: str = Field(min_length=1)
    canonical_key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    parent_category_id: str | None = None
    is_standard: bool = True
    is_active: bool = True
    schema_version: str = "1.0"
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("label")
    @classmethod
    def trim_label(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Category label cannot be blank")
        return value


class Expense(DomainModel):
    id: str = Field(min_length=1)
    household_id: str = Field(min_length=1)
    date: date
    description: str = Field(min_length=1, max_length=120)
    amount_cents: StrictInt = Field(gt=0)
    payment_method: PaymentMethod
    recurring: bool = False
    category_id: str = Field(min_length=1)
    merchant: str | None = None
    notes: str | None = None
    source: ExpenseSource
    confidence: float | None = Field(default=None, ge=0, le=1)
    review_required: bool = False
    user_override: bool = False
    schema_version: str = "1.0"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("description")
    @classmethod
    def trim_description(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Description cannot be blank")
        return value


class SafeClassificationContext(DomainModel):
    merchant_alias: str | None = None
    business_context: str | None = None
    category_hints: tuple[str, ...] = ()
    recurring_count: int = Field(ge=0, default=0)


class ImportRowError(DomainModel):
    row: int = Field(ge=1)
    field: str = Field(min_length=1)
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    value: str | None = None


class ImportRun(DomainModel):
    id: str = Field(min_length=1)
    household_id: str = Field(min_length=1)
    source_name: str | None = None
    total_rows: int = Field(ge=0)
    imported_rows: int = Field(ge=0)
    rejected_rows: int = Field(ge=0)
    row_errors: tuple[ImportRowError, ...] = ()
    status: Literal["completed", "failed"]
    schema_version: str = "1.0"
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def counts_match(self) -> "ImportRun":
        if self.total_rows != self.imported_rows + self.rejected_rows:
            raise ValueError("total_rows must equal imported_rows plus rejected_rows")
        return self


class ClassificationDecision(DomainModel):
    id: str = Field(min_length=1)
    household_id: str = Field(min_length=1)
    expense_id: str = Field(min_length=1)
    category_id: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1)
    source: ClassificationSource
    review_required: bool
    user_override: bool = False
    schema_version: str = "1.0"
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Classification reason cannot be blank")
        return value


class InsightCard(DomainModel):
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)
    source_refs: tuple[str, ...] = Field(min_length=1)


ProviderErrorCode = Literal[
    "authentication",
    "rate_limit",
    "timeout",
    "invalid_response",
    "safety_rejection",
    "provider_error",
]


class InsightRun(DomainModel):
    id: str = Field(min_length=1)
    household_id: str = Field(min_length=1)
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    summary_version: str = Field(min_length=1)
    summary_hash: str = Field(min_length=1)
    cards: tuple[InsightCard, ...]
    provider: str | None = None
    provider_status: Literal["used", "unavailable", "failed", "not_configured"]
    provider_error_code: ProviderErrorCode | None = None
    safety_status: Literal["accepted", "fallback"]
    model: str | None = None
    latency_ms: int | None = Field(default=None, ge=0)
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    schema_version: str = "1.0"
    created_at: datetime = Field(default_factory=utc_now)


class InsightGroup(DomainModel):
    token: str = Field(min_length=1)
    category_id: str = Field(min_length=1)
    category_label: str = Field(min_length=1)
    amount_cents: StrictInt = Field(ge=0)
    expense_count: int = Field(ge=0)


class CategoryAmount(DomainModel):
    category_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    amount_cents: StrictInt = Field(ge=0)
    percentage: float = Field(ge=0, le=100)


class PaymentAmount(DomainModel):
    payment_method: PaymentMethod
    amount_cents: StrictInt = Field(ge=0)


class MonthlyDashboard(DomainModel):
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    total_cents: StrictInt = Field(ge=0)
    expense_count: int = Field(ge=0)
    category_breakdown: tuple[CategoryAmount, ...]
    payment_breakdown: tuple[PaymentAmount, ...]
    recurring_cents: StrictInt = Field(ge=0)
    previous_month_total_cents: StrictInt | None = Field(default=None, ge=0)
    change_cents: int | None = None
    change_percentage: float | None = None


class CategoryConfusion(DomainModel):
    expected_category_id: str = Field(min_length=1)
    predicted_category_id: str = Field(min_length=1)
    count: int = Field(gt=0)


class EvaluationRun(DomainModel):
    id: str = Field(min_length=1)
    household_id: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    taxonomy_version: str = Field(min_length=1)
    total_count: int = Field(gt=0)
    correct_count: int = Field(ge=0)
    accuracy: float = Field(ge=0, le=1)
    confusion_details: tuple[CategoryConfusion, ...] = ()
    passed: bool
    schema_version: str = "1.0"
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def metrics_match(self) -> "EvaluationRun":
        if self.correct_count > self.total_count:
            raise ValueError("correct_count cannot exceed total_count")
        expected_accuracy = self.correct_count / self.total_count
        if not isclose(self.accuracy, expected_accuracy, abs_tol=1e-9):
            raise ValueError("accuracy must equal correct_count divided by total_count")
        if self.passed != (self.accuracy >= EVALUATION_THRESHOLD):
            raise ValueError("passed must reflect the 70% acceptance threshold")
        return self


class MerchantContext(DomainModel):
    id: str = Field(min_length=1)
    household_id: str = Field(min_length=1)
    original_value: str = Field(min_length=1)
    alias: str = Field(min_length=1)
    business_context: str = Field(min_length=1)
    category_hints: tuple[str, ...] = ()
    recurring_count: int = Field(ge=0)
    schema_version: str = "1.0"
    created_at: datetime = Field(default_factory=utc_now)


class LLMDataMap(DomainModel):
    id: str = Field(min_length=1)
    household_id: str = Field(min_length=1)
    alias: str = Field(min_length=1)
    merchant_context_id: str = Field(min_length=1)
    schema_version: str = "1.0"
    created_at: datetime = Field(default_factory=utc_now)
