from dataclasses import dataclass

from home_financial_backend.domain.errors import (
    AmbiguousCategoryLabel,
    CategoryAlreadyExists,
    CategoryNotFound,
    DuplicateRecord,
    ExpenseNotFound,
    HouseholdNotFound,
    ParentCategoryNotAssignable,
    UnknownCategoryLabel,
)
from home_financial_backend.domain.models import (
    Category,
    ClassificationDecision,
    EvaluationRun,
    Expense,
    Household,
    ImportRun,
    InsightRun,
    LLMDataMap,
    MerchantContext,
)
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


class InMemoryHouseholdRepository:
    def __init__(self, households: tuple[Household, ...]) -> None:
        self._households = {household.id: household for household in households}
        if len(self._households) != len(households):
            raise DuplicateRecord("Household identifiers must be unique")
        if sum(household.is_demo for household in households) != 1:
            raise ValueError("Exactly one demo household must be configured")

    def get_demo(self) -> Household:
        for household in self._households.values():
            if household.is_demo:
                return household
        raise HouseholdNotFound("The demo household is not configured")

    def get_by_id(self, household_id: str) -> Household | None:
        return self._households.get(household_id)


class InMemoryCategoryRepository:
    def __init__(
        self,
        categories: tuple[Category, ...],
        households: HouseholdRepository,
    ) -> None:
        self._categories = {category.id: category for category in categories}
        self._households = households
        if len(self._categories) != len(categories):
            raise DuplicateRecord("Category identifiers must be unique")

        for category in categories:
            if households.get_by_id(category.household_id) is None:
                raise HouseholdNotFound("A category references an unknown household")
            if category.parent_category_id is not None:
                parent = self._categories.get(category.parent_category_id)
                if parent is None or parent.household_id != category.household_id:
                    raise CategoryNotFound("A category parent must exist in the same household")
                if parent.parent_category_id is not None:
                    raise ValueError("Categories may only be nested one level deep")

    def add(self, category: Category) -> Category:
        if self._households.get_by_id(category.household_id) is None:
            raise HouseholdNotFound("Household not found")
        if category.id in self._categories:
            raise DuplicateRecord("Category identifier already exists")
        if category.parent_category_id is None:
            raise CategoryNotFound("Custom categories must be leaves under a top-level category")
        parent = self.get_for_household(category.parent_category_id, category.household_id)
        if parent is None or not parent.is_active or parent.parent_category_id is not None:
            raise CategoryNotFound("Custom leaves must be under an active top-level category")
        self._ensure_unique_label(category.household_id, category.label)
        self._categories[category.id] = category
        return category

    def list_by_household(self, household_id: str) -> tuple[Category, ...]:
        if self._households.get_by_id(household_id) is None:
            raise HouseholdNotFound("Household not found")
        return tuple(
            category
            for category in self._categories.values()
            if category.household_id == household_id
        )

    def get_for_household(self, category_id: str, household_id: str) -> Category | None:
        category = self._categories.get(category_id)
        if category is None or category.household_id != household_id:
            return None
        return category

    def is_active_leaf(self, household_id: str, category_id: str) -> bool:
        category = self.get_for_household(category_id, household_id)
        if category is None or not category.is_active:
            return False
        return not any(
            child.is_active
            and child.household_id == household_id
            and child.parent_category_id == category_id
            for child in self._categories.values()
        )

    def require_active_leaf(self, household_id: str, category_id: str) -> Category:
        category = self.get_for_household(category_id, household_id)
        if category is None or not category.is_active:
            raise CategoryNotFound("Active category not found in household")
        if not self.is_active_leaf(household_id, category_id):
            raise ParentCategoryNotAssignable("Parent categories cannot be assigned to expenses")
        return category

    def update(self, category: Category) -> Category:
        existing = self.get_for_household(category.id, category.household_id)
        if existing is None:
            raise CategoryNotFound("Category not found in household")
        if category.is_standard != existing.is_standard:
            raise ValueError("Standard category identity cannot be changed")
        if existing.is_standard and category.label != existing.label:
            raise ValueError("Standard category labels cannot be changed")
        self._ensure_unique_label(category.household_id, category.label, exclude_id=category.id)
        self._categories[category.id] = category
        return category

    def merge_custom_leaf(
        self,
        household_id: str,
        source_category_id: str,
        target_category_id: str,
    ) -> tuple[Category, Category]:
        source = self.require_active_leaf(household_id, source_category_id)
        target = self.require_active_leaf(household_id, target_category_id)
        if source.id == target.id:
            raise ValueError("Source and target categories must differ")
        if source.is_standard:
            raise ValueError("Standard categories cannot be merged")
        source = source.model_copy(update={"is_active": False})
        self._categories[source.id] = source
        return source, target

    def delete_custom_by_household(self, household_id: str) -> None:
        if self._households.get_by_id(household_id) is None:
            raise HouseholdNotFound("Household not found")
        self._categories = {
            category_id: category
            for category_id, category in self._categories.items()
            if category.household_id != household_id or category.is_standard
        }

    def _ensure_unique_label(
        self,
        household_id: str,
        label: str,
        *,
        exclude_id: str | None = None,
    ) -> None:
        normalized = normalize_text(label)
        if any(
            category.household_id == household_id
            and category.id != exclude_id
            and category.is_active
            and normalize_text(category.label) == normalized
            for category in self._categories.values()
        ):
            raise CategoryAlreadyExists("A category with this normalized label already exists")

    def resolve_active_leaf(self, household_id: str, label: str) -> Category:
        normalized_label = normalize_text(label)
        if not normalized_label:
            raise UnknownCategoryLabel("Category label cannot be blank")
        matches = [
            category
            for category in self.list_by_household(household_id)
            if category.is_active and normalize_text(category.label) == normalized_label
        ]
        if not matches:
            raise UnknownCategoryLabel(f"Unknown category label: {label}")
        if len(matches) > 1:
            raise AmbiguousCategoryLabel(f"Ambiguous category label: {label}")
        return self.require_active_leaf(household_id, matches[0].id)


class InMemoryExpenseRepository:
    def __init__(
        self,
        households: HouseholdRepository,
        categories: CategoryRepository,
    ) -> None:
        self._households = households
        self._categories = categories
        self._expenses: dict[str, Expense] = {}

    def add(self, expense: Expense) -> Expense:
        if self._households.get_by_id(expense.household_id) is None:
            raise HouseholdNotFound("Household not found")
        self._categories.require_active_leaf(expense.household_id, expense.category_id)
        if expense.id in self._expenses:
            raise DuplicateRecord("Expense identifier already exists")
        self._expenses[expense.id] = expense
        return expense

    def update(self, expense: Expense) -> Expense:
        if self._households.get_by_id(expense.household_id) is None:
            raise HouseholdNotFound("Household not found")
        if expense.id not in self._expenses:
            raise ExpenseNotFound("Expense not found in household")
        if self._expenses[expense.id].household_id != expense.household_id:
            raise ExpenseNotFound("Expense not found in household")
        self._categories.require_active_leaf(expense.household_id, expense.category_id)
        self._expenses[expense.id] = expense
        return expense

    def get_for_household(self, expense_id: str, household_id: str) -> Expense | None:
        expense = self._expenses.get(expense_id)
        if expense is None or expense.household_id != household_id:
            return None
        return expense

    def list_by_household(self, household_id: str) -> tuple[Expense, ...]:
        if self._households.get_by_id(household_id) is None:
            raise HouseholdNotFound("Household not found")
        return tuple(
            expense for expense in self._expenses.values() if expense.household_id == household_id
        )

    def delete_by_household(self, household_id: str) -> None:
        if self._households.get_by_id(household_id) is None:
            raise HouseholdNotFound("Household not found")
        self._expenses = {
            expense_id: expense
            for expense_id, expense in self._expenses.items()
            if expense.household_id != household_id
        }


class InMemoryClassificationDecisionRepository:
    def __init__(
        self,
        households: HouseholdRepository,
        expenses: InMemoryExpenseRepository,
        categories: CategoryRepository,
    ) -> None:
        self._households = households
        self._expenses = expenses
        self._categories = categories
        self._decisions: dict[str, ClassificationDecision] = {}

    def add(self, decision: ClassificationDecision) -> ClassificationDecision:
        if self._households.get_by_id(decision.household_id) is None:
            raise HouseholdNotFound("Household not found")
        expense = self._expenses.get_for_household(decision.expense_id, decision.household_id)
        if expense is None:
            raise ExpenseNotFound("Classification decision references an unknown expense")
        self._categories.require_active_leaf(decision.household_id, decision.category_id)
        if decision.id in self._decisions:
            raise DuplicateRecord("Classification decision identifier already exists")
        self._decisions[decision.id] = decision
        return decision

    def list_by_household(self, household_id: str) -> tuple[ClassificationDecision, ...]:
        if self._households.get_by_id(household_id) is None:
            raise HouseholdNotFound("Household not found")
        return tuple(
            decision
            for decision in self._decisions.values()
            if decision.household_id == household_id
        )

    def list_all(self) -> tuple[ClassificationDecision, ...]:
        return tuple(self._decisions.values())

    def update_category(
        self,
        household_id: str,
        source_category_id: str,
        target_category_id: str,
    ) -> None:
        for decision_id, decision in tuple(self._decisions.items()):
            if decision.household_id == household_id and decision.category_id == source_category_id:
                self._decisions[decision_id] = decision.model_copy(
                    update={"category_id": target_category_id}
                )

    def delete_by_household(self, household_id: str) -> None:
        if self._households.get_by_id(household_id) is None:
            raise HouseholdNotFound("Household not found")
        self._decisions = {
            decision_id: decision
            for decision_id, decision in self._decisions.items()
            if decision.household_id != household_id
        }


class InMemoryImportRunRepository:
    def __init__(self, households: HouseholdRepository) -> None:
        self._households = households
        self._runs: dict[str, ImportRun] = {}

    def add(self, import_run: ImportRun) -> ImportRun:
        if self._households.get_by_id(import_run.household_id) is None:
            raise HouseholdNotFound("Household not found")
        if import_run.id in self._runs:
            raise DuplicateRecord("Import run identifier already exists")
        self._runs[import_run.id] = import_run
        return import_run

    def list_by_household(self, household_id: str) -> tuple[ImportRun, ...]:
        if self._households.get_by_id(household_id) is None:
            raise HouseholdNotFound("Household not found")
        return tuple(
            import_run
            for import_run in self._runs.values()
            if import_run.household_id == household_id
        )

    def delete_by_household(self, household_id: str) -> None:
        if self._households.get_by_id(household_id) is None:
            raise HouseholdNotFound("Household not found")
        self._runs = {
            run_id: run for run_id, run in self._runs.items() if run.household_id != household_id
        }


class InMemoryInsightRunRepository:
    def __init__(self, households: HouseholdRepository) -> None:
        self._households = households
        self._runs: dict[str, InsightRun] = {}

    def add(self, insight_run: InsightRun) -> InsightRun:
        if self._households.get_by_id(insight_run.household_id) is None:
            raise HouseholdNotFound("Household not found")
        if insight_run.id in self._runs:
            raise DuplicateRecord("Insight run identifier already exists")
        self._runs[insight_run.id] = insight_run
        return insight_run

    def list_by_household(self, household_id: str) -> tuple[InsightRun, ...]:
        if self._households.get_by_id(household_id) is None:
            raise HouseholdNotFound("Household not found")
        return tuple(run for run in self._runs.values() if run.household_id == household_id)

    def delete_by_household(self, household_id: str) -> None:
        if self._households.get_by_id(household_id) is None:
            raise HouseholdNotFound("Household not found")
        self._runs = {
            run_id: run for run_id, run in self._runs.items() if run.household_id != household_id
        }


class InMemoryEvaluationRunRepository:
    def __init__(self, households: HouseholdRepository) -> None:
        self._households = households
        self._runs: dict[str, EvaluationRun] = {}

    def add(self, evaluation_run: EvaluationRun) -> EvaluationRun:
        if self._households.get_by_id(evaluation_run.household_id) is None:
            raise HouseholdNotFound("Household not found")
        if evaluation_run.id in self._runs:
            raise DuplicateRecord("Evaluation run identifier already exists")
        self._runs[evaluation_run.id] = evaluation_run
        return evaluation_run

    def list_by_household(self, household_id: str) -> tuple[EvaluationRun, ...]:
        if self._households.get_by_id(household_id) is None:
            raise HouseholdNotFound("Household not found")
        return tuple(run for run in self._runs.values() if run.household_id == household_id)

    def delete_by_household(self, household_id: str) -> None:
        if self._households.get_by_id(household_id) is None:
            raise HouseholdNotFound("Household not found")
        self._runs = {
            run_id: run for run_id, run in self._runs.items() if run.household_id != household_id
        }


class InMemoryMerchantContextRepository:
    def __init__(self, households: HouseholdRepository) -> None:
        self._households = households
        self._contexts: dict[str, MerchantContext] = {}
        self._maps: dict[str, LLMDataMap] = {}

    def get_by_original(self, household_id: str, original_value: str) -> MerchantContext | None:
        normalized = normalize_text(original_value)
        for context in self._contexts.values():
            if (
                context.household_id == household_id
                and normalize_text(context.original_value) == normalized
            ):
                return context
        return None

    def save(
        self,
        context: MerchantContext,
        data_map: LLMDataMap | None = None,
    ) -> MerchantContext:
        if self._households.get_by_id(context.household_id) is None:
            raise HouseholdNotFound("Household not found")
        self._contexts[context.id] = context
        if data_map is not None:
            if data_map.household_id != context.household_id:
                raise HouseholdNotFound("Data map household does not match its context")
            self._maps[data_map.id] = data_map
        return context

    def list_by_household(self, household_id: str) -> tuple[MerchantContext, ...]:
        if self._households.get_by_id(household_id) is None:
            raise HouseholdNotFound("Household not found")
        return tuple(c for c in self._contexts.values() if c.household_id == household_id)

    def delete_by_household(self, household_id: str) -> None:
        if self._households.get_by_id(household_id) is None:
            raise HouseholdNotFound("Household not found")
        self._contexts = {k: v for k, v in self._contexts.items() if v.household_id != household_id}
        self._maps = {k: v for k, v in self._maps.items() if v.household_id != household_id}


@dataclass(frozen=True)
class DemoRepositories:
    households: HouseholdRepository
    categories: CategoryRepository
    expenses: ExpenseRepository
    classification_decisions: ClassificationDecisionRepository
    import_runs: ImportRunRepository
    insight_runs: InsightRunRepository
    evaluation_runs: EvaluationRunRepository
    merchant_contexts: MerchantContextRepository


def create_demo_repositories() -> DemoRepositories:
    from home_financial_backend.domain.seed import DEMO_HOUSEHOLD, build_demo_categories

    households = InMemoryHouseholdRepository((DEMO_HOUSEHOLD,))
    categories = InMemoryCategoryRepository(build_demo_categories(), households)
    expenses = InMemoryExpenseRepository(households, categories)
    classification_decisions = InMemoryClassificationDecisionRepository(
        households,
        expenses,
        categories,
    )
    import_runs = InMemoryImportRunRepository(households)
    insight_runs = InMemoryInsightRunRepository(households)
    evaluation_runs = InMemoryEvaluationRunRepository(households)
    merchant_contexts = InMemoryMerchantContextRepository(households)
    return DemoRepositories(
        households,
        categories,
        expenses,
        classification_decisions,
        import_runs,
        insight_runs,
        evaluation_runs,
        merchant_contexts,
    )
