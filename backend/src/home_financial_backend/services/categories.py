from uuid import uuid4

from home_financial_backend.domain.errors import CategoryNotFound, HouseholdNotFound
from home_financial_backend.domain.models import Category, utc_now
from home_financial_backend.domain.normalization import normalize_text
from home_financial_backend.domain.repositories import (
    CategoryRepository,
    ClassificationDecisionRepository,
    EvaluationRunRepository,
    ExpenseRepository,
    HouseholdRepository,
    ImportRunRepository,
    InsightRunRepository,
    MerchantContextRepository,
)


class CategoryService:
    def __init__(
        self,
        households: HouseholdRepository,
        categories: CategoryRepository,
        expenses: ExpenseRepository,
        decisions: ClassificationDecisionRepository,
    ) -> None:
        self._households = households
        self._categories = categories
        self._expenses = expenses
        self._decisions = decisions

    def create(self, household_id: str, label: str, parent_category_id: str) -> Category:
        parent = self._categories.get_for_household(parent_category_id, household_id)
        if parent is None or not parent.is_active or parent.parent_category_id is not None:
            raise CategoryNotFound("Choose an active top-level category")
        normalized_key = normalize_text(label).replace(" ", "-")
        if not normalized_key:
            raise ValueError("Category label cannot be blank")
        category_id = f"category-custom-{uuid4().hex}"
        category = Category(
            id=category_id,
            household_id=household_id,
            canonical_key=f"custom-{category_id.removeprefix('category-custom-')}",
            label=label,
            parent_category_id=parent.id,
            is_standard=False,
        )
        return self._categories.add(category)

    def rename(self, household_id: str, category_id: str, label: str) -> Category:
        category = self._categories.require_active_leaf(household_id, category_id)
        if category.is_standard:
            raise ValueError("Standard category labels cannot be changed")
        return self._categories.update(category.model_copy(update={"label": label.strip()}))

    def merge(
        self,
        household_id: str,
        source_category_id: str,
        target_category_id: str,
    ) -> Category:
        _, target = self._categories.merge_custom_leaf(
            household_id,
            source_category_id,
            target_category_id,
        )
        for expense in self._expenses.list_by_household(household_id):
            if expense.category_id == source_category_id:
                self._expenses.update(
                    expense.model_copy(update={"category_id": target.id, "updated_at": utc_now()})
                )
        self._decisions.update_category(household_id, source_category_id, target.id)
        return target

    def list(self, household_id: str) -> tuple[Category, ...]:
        return tuple(
            category
            for category in self._categories.list_by_household(household_id)
            if category.is_active
        )


def delete_demo_data(
    household_id: str,
    *,
    households: HouseholdRepository,
    categories: CategoryRepository,
    expenses: ExpenseRepository,
    decisions: ClassificationDecisionRepository,
    import_runs: ImportRunRepository,
    insight_runs: InsightRunRepository,
    evaluation_runs: EvaluationRunRepository,
    merchant_contexts: MerchantContextRepository | None = None,
) -> int:
    if households.get_by_id(household_id) is None or households.get_demo().id != household_id:
        raise HouseholdNotFound("Demo household not found")
    expense_count = len(expenses.list_by_household(household_id))
    expenses.delete_by_household(household_id)
    decisions.delete_by_household(household_id)
    import_runs.delete_by_household(household_id)
    insight_runs.delete_by_household(household_id)
    evaluation_runs.delete_by_household(household_id)
    if merchant_contexts is not None:
        merchant_contexts.delete_by_household(household_id)
    categories.delete_custom_by_household(household_id)
    return expense_count
