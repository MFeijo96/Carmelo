from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from home_financial_backend.domain.models import (
    Category,
    EvaluationRun,
    Expense,
    Household,
    ImportRun,
    InsightRun,
    MonthlyDashboard,
    PaymentMethod,
)


class ApiContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExpenseCreateRequest(ApiContract):
    date: date
    description: str = Field(min_length=1, max_length=120)
    amount_cents: int = Field(strict=True, gt=0)
    payment_method: PaymentMethod
    category_id: str | None = Field(default=None, min_length=1)
    recurring: bool = False
    merchant: str | None = None
    notes: str | None = None

    @field_validator("description")
    @classmethod
    def trim_description(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Description cannot be blank")
        return value

    @field_validator("category_id")
    @classmethod
    def trim_category_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Category identifier cannot be blank")
        return value


class CategoryCreateRequest(ApiContract):
    label: str = Field(min_length=1, max_length=80)
    parent_category_id: str = Field(min_length=1)

    @field_validator("label", "parent_category_id")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank")
        return value


class CategoryRenameRequest(ApiContract):
    label: str = Field(min_length=1, max_length=80)

    @field_validator("label")
    @classmethod
    def trim_label(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Category label cannot be blank")
        return value


class CategoryCorrectionRequest(ApiContract):
    category_id: str = Field(min_length=1)


class CategoryMergeRequest(ApiContract):
    source_category_id: str = Field(min_length=1)
    target_category_id: str = Field(min_length=1)


class ExpenseListData(ApiContract):
    expenses: tuple[Expense, ...]
    total_count: int = Field(ge=0)


class CategoryListData(ApiContract):
    categories: tuple[Category, ...]


class HouseholdData(ApiContract):
    household: Household


class CategoryResultData(ApiContract):
    category: Category


class ImportResultData(ApiContract):
    import_run: ImportRun


class MonthlyInsightsRequest(ApiContract):
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")


class MonthlyDashboardRequest(ApiContract):
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")


class EvaluationRequest(ApiContract):
    dataset_version: str | None = None


class EvaluationResultData(ApiContract):
    evaluation: EvaluationRun


class DashboardResultData(ApiContract):
    dashboard: MonthlyDashboard


class InsightSourceExpense(ApiContract):
    expense_id: str
    category_label: str
    date: date
    amount_cents: int


class InsightResultData(ApiContract):
    insight_run: InsightRun
    sources: dict[str, tuple[InsightSourceExpense, ...]]


class ExpenseResultData(ApiContract):
    expense: Expense


class ArchiveResultData(ApiContract):
    archive: dict[str, Any]


class DeletionResultData(ApiContract):
    household_id: str
    deleted_expense_count: int
    status: str = "deleted"


class HealthData(ApiContract):
    status: str
    provider_configured: bool
    persistence_mode: str
