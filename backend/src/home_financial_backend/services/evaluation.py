from collections import Counter
from datetime import date
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from home_financial_backend.domain.errors import (
    CategoryNotFound,
    EvaluationUnavailable,
    ParentCategoryNotAssignable,
)
from home_financial_backend.domain.models import (
    EVALUATION_THRESHOLD,
    CategoryConfusion,
    ClassificationDecision,
    EvaluationRun,
    Expense,
    PaymentMethod,
)
from home_financial_backend.domain.repositories import (
    CategoryRepository,
    EvaluationRunRepository,
    HouseholdRepository,
)
from home_financial_backend.services.classification import (
    ClassificationInput,
    ClassificationService,
)


class GoldenRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    description: str = Field(min_length=1)
    amount_cents: int = Field(gt=0)
    payment_method: PaymentMethod
    recurring: bool = False
    merchant: str | None = None
    expected_category_id: str = Field(min_length=1)


class GoldenDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(min_length=1)
    records: tuple[GoldenRecord, ...] = Field(min_length=1)


class _EmptyHistory:
    def list_by_household(self, household_id: str) -> tuple[ClassificationDecision, ...]:
        return ()

    def list_all(self) -> tuple[ClassificationDecision, ...]:
        return ()


class _NoStoredExpenses:
    def get_for_household(self, expense_id: str, household_id: str) -> Expense | None:
        return None


class EvaluationService:
    def __init__(
        self,
        households: HouseholdRepository,
        categories: CategoryRepository,
        evaluations: EvaluationRunRepository,
        dataset_path: str | None,
    ) -> None:
        self._households = households
        self._categories = categories
        self._evaluations = evaluations
        self._dataset_path = dataset_path

    def run(self, household_id: str, dataset_version: str | None = None) -> EvaluationRun:
        if self._households.get_by_id(household_id) is None:
            raise EvaluationUnavailable("Demo household is unavailable")
        if self._dataset_path is None:
            raise EvaluationUnavailable(
                "Golden dataset is not configured; no evaluation result was generated."
            )
        path = Path(self._dataset_path)
        try:
            dataset = GoldenDataset.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise EvaluationUnavailable(
                "Golden dataset could not be loaded or validated."
            ) from error
        if dataset_version is not None and dataset.version != dataset_version:
            raise EvaluationUnavailable("Requested golden dataset version is not available.")

        classifier = ClassificationService(
            categories=self._categories,
            expenses=_NoStoredExpenses(),
            decisions=_EmptyHistory(),
            fallback_classifier=None,
        )
        confusion: Counter[tuple[str, str]] = Counter()
        correct = 0
        for index, record in enumerate(dataset.records):
            try:
                category = self._categories.require_active_leaf(
                    household_id,
                    record.expected_category_id,
                )
            except (CategoryNotFound, ParentCategoryNotAssignable) as error:
                raise EvaluationUnavailable(
                    "Golden dataset contains an invalid expected category."
                ) from error
            decision = classifier.classify(
                ClassificationInput(
                    expense_id=f"eval-{index}",
                    household_id=household_id,
                    description=record.description,
                    merchant=record.merchant,
                )
            )
            confusion[(category.id, decision.category_id)] += 1
            correct += decision.category_id == category.id

        total = len(dataset.records)
        accuracy = correct / total
        result = EvaluationRun(
            id=uuid4().hex,
            household_id=household_id,
            dataset_version=dataset.version,
            taxonomy_version="1.0",
            total_count=total,
            correct_count=correct,
            accuracy=accuracy,
            confusion_details=tuple(
                CategoryConfusion(
                    expected_category_id=expected,
                    predicted_category_id=predicted,
                    count=count,
                )
                for (expected, predicted), count in sorted(confusion.items())
            ),
            passed=accuracy >= EVALUATION_THRESHOLD,
        )
        return self._evaluations.add(result)
