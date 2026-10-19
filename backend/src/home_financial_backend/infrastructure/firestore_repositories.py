from collections.abc import Iterable
from typing import Any, Generic, TypeVar

from google.api_core.exceptions import AlreadyExists
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import BaseModel

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
    ExpenseRepository,
    HouseholdRepository,
)
from home_financial_backend.infrastructure.memory_repositories import DemoRepositories

RecordT = TypeVar("RecordT", bound=BaseModel)
HouseholdRecordT = TypeVar("HouseholdRecordT", ImportRun, InsightRun, EvaluationRun)


def _model_data(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")


def _from_snapshot(snapshot, model_type: type[RecordT]) -> RecordT:
    payload = snapshot.to_dict() or {}
    payload.setdefault("id", snapshot.id)
    return model_type.model_validate(payload)


def _delete_documents(client: firestore.Client, references: Iterable) -> None:
    pending = iter(references)
    while batch_refs := tuple(next(pending, None) for _ in range(450)):
        refs = tuple(reference for reference in batch_refs if reference is not None)
        if not refs:
            break
        batch = client.batch()
        for reference in refs:
            batch.delete(reference)
        batch.commit()


class FirestoreHouseholdRepository:
    def __init__(self, client: firestore.Client) -> None:
        self._collection = client.collection("households")

    def get_demo(self) -> Household:
        snapshots = tuple(
            self._collection.where(filter=FieldFilter("is_demo", "==", True)).limit(2).stream()
        )
        if not snapshots:
            raise HouseholdNotFound("The demo household is not configured")
        if len(snapshots) != 1:
            raise ValueError("Exactly one demo household must be configured")
        return _from_snapshot(snapshots[0], Household)

    def get_by_id(self, household_id: str) -> Household | None:
        snapshot = self._collection.document(household_id).get()
        return _from_snapshot(snapshot, Household) if snapshot.exists else None


class FirestoreCategoryRepository:
    def __init__(self, client: firestore.Client, households: HouseholdRepository) -> None:
        self._client = client
        self._collection = client.collection("categories")
        self._households = households

    def add(self, category: Category) -> Category:
        if self._households.get_by_id(category.household_id) is None:
            raise HouseholdNotFound("Household not found")
        reference = self._collection.document(category.id)
        if reference.get().exists:
            raise DuplicateRecord("Category identifier already exists")
        if category.parent_category_id is None:
            raise CategoryNotFound("Custom categories must be leaves under a top-level category")
        parent = self.get_for_household(category.parent_category_id, category.household_id)
        if parent is None or not parent.is_active or parent.parent_category_id is not None:
            raise CategoryNotFound("Custom leaves must be under an active top-level category")
        self._ensure_unique_label(category.household_id, category.label)
        reference.set(_model_data(category))
        return category

    def list_by_household(self, household_id: str) -> tuple[Category, ...]:
        if self._households.get_by_id(household_id) is None:
            raise HouseholdNotFound("Household not found")
        snapshots = self._collection.where(
            filter=FieldFilter("household_id", "==", household_id)
        ).stream()
        return tuple(_from_snapshot(snapshot, Category) for snapshot in snapshots)

    def get_for_household(self, category_id: str, household_id: str) -> Category | None:
        snapshot = self._collection.document(category_id).get()
        if not snapshot.exists:
            return None
        category = _from_snapshot(snapshot, Category)
        return category if category.household_id == household_id else None

    def is_active_leaf(self, household_id: str, category_id: str) -> bool:
        category = self.get_for_household(category_id, household_id)
        if category is None or not category.is_active:
            return False
        return not any(
            child.is_active and child.parent_category_id == category_id
            for child in self.list_by_household(household_id)
        )

    def require_active_leaf(self, household_id: str, category_id: str) -> Category:
        category = self.get_for_household(category_id, household_id)
        if category is None or not category.is_active:
            raise CategoryNotFound("Active category not found in household")
        if not self.is_active_leaf(household_id, category_id):
            raise ParentCategoryNotAssignable("Parent categories cannot be assigned to expenses")
        return category

    def resolve_active_leaf(self, household_id: str, label: str) -> Category:
        normalized = normalize_text(label)
        if not normalized:
            raise UnknownCategoryLabel("Category label cannot be blank")
        matches = [
            category
            for category in self.list_by_household(household_id)
            if category.is_active and normalize_text(category.label) == normalized
        ]
        if not matches:
            raise UnknownCategoryLabel(f"Unknown category label: {label}")
        if len(matches) > 1:
            raise AmbiguousCategoryLabel(f"Ambiguous category label: {label}")
        return self.require_active_leaf(household_id, matches[0].id)

    def update(self, category: Category) -> Category:
        existing = self.get_for_household(category.id, category.household_id)
        if existing is None:
            raise CategoryNotFound("Category not found in household")
        if category.is_standard != existing.is_standard:
            raise ValueError("Standard category identity cannot be changed")
        if existing.is_standard and category.label != existing.label:
            raise ValueError("Standard category labels cannot be changed")
        self._ensure_unique_label(category.household_id, category.label, exclude_id=category.id)
        self._collection.document(category.id).set(_model_data(category))
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
        deactivated = source.model_copy(update={"is_active": False})
        self._collection.document(source.id).set(_model_data(deactivated))
        return deactivated, target

    def delete_custom_by_household(self, household_id: str) -> None:
        categories = self.list_by_household(household_id)
        references = (
            self._collection.document(category.id)
            for category in categories
            if not category.is_standard
        )
        _delete_documents(self._client, references)

    def _ensure_unique_label(
        self,
        household_id: str,
        label: str,
        *,
        exclude_id: str | None = None,
    ) -> None:
        normalized = normalize_text(label)
        if any(
            category.id != exclude_id
            and category.is_active
            and normalize_text(category.label) == normalized
            for category in self.list_by_household(household_id)
        ):
            raise CategoryAlreadyExists("A category with this normalized label already exists")


class FirestoreExpenseRepository:
    def __init__(
        self,
        client: firestore.Client,
        households: HouseholdRepository,
        categories: CategoryRepository,
    ) -> None:
        self._client = client
        self._collection = client.collection("expenses")
        self._households = households
        self._categories = categories

    def add(self, expense: Expense) -> Expense:
        if self._households.get_by_id(expense.household_id) is None:
            raise HouseholdNotFound("Household not found")
        self._categories.require_active_leaf(expense.household_id, expense.category_id)
        reference = self._collection.document(expense.id)
        try:
            reference.create(_model_data(expense))
        except AlreadyExists as error:
            raise DuplicateRecord("Expense identifier already exists") from error
        return expense

    def update(self, expense: Expense) -> Expense:
        current = self.get_for_household(expense.id, expense.household_id)
        if current is None:
            raise ExpenseNotFound("Expense not found in household")
        self._categories.require_active_leaf(expense.household_id, expense.category_id)
        self._collection.document(expense.id).set(_model_data(expense))
        return expense

    def get_for_household(self, expense_id: str, household_id: str) -> Expense | None:
        snapshot = self._collection.document(expense_id).get()
        if not snapshot.exists:
            return None
        expense = _from_snapshot(snapshot, Expense)
        return expense if expense.household_id == household_id else None

    def list_by_household(self, household_id: str) -> tuple[Expense, ...]:
        if self._households.get_by_id(household_id) is None:
            raise HouseholdNotFound("Household not found")
        snapshots = self._collection.where(
            filter=FieldFilter("household_id", "==", household_id)
        ).stream()
        return tuple(_from_snapshot(snapshot, Expense) for snapshot in snapshots)

    def delete_by_household(self, household_id: str) -> None:
        if self._households.get_by_id(household_id) is None:
            raise HouseholdNotFound("Household not found")
        references = (
            snapshot.reference
            for snapshot in self._collection.where(
                filter=FieldFilter("household_id", "==", household_id)
            ).stream()
        )
        _delete_documents(self._client, references)


class FirestoreClassificationDecisionRepository:
    def __init__(
        self,
        client: firestore.Client,
        households: HouseholdRepository,
        expenses: ExpenseRepository,
        categories: CategoryRepository,
    ) -> None:
        self._client = client
        self._collection = client.collection("classification_decisions")
        self._households = households
        self._expenses = expenses
        self._categories = categories

    def add(self, decision: ClassificationDecision) -> ClassificationDecision:
        if self._households.get_by_id(decision.household_id) is None:
            raise HouseholdNotFound("Household not found")
        if self._expenses.get_for_household(decision.expense_id, decision.household_id) is None:
            raise ExpenseNotFound("Classification decision references an unknown expense")
        self._categories.require_active_leaf(decision.household_id, decision.category_id)
        reference = self._collection.document(decision.id)
        if reference.get().exists:
            raise DuplicateRecord("Classification decision identifier already exists")
        reference.set(_model_data(decision))
        return decision

    def list_by_household(self, household_id: str) -> tuple[ClassificationDecision, ...]:
        if self._households.get_by_id(household_id) is None:
            raise HouseholdNotFound("Household not found")
        snapshots = self._collection.where(
            filter=FieldFilter("household_id", "==", household_id)
        ).stream()
        return tuple(_from_snapshot(snapshot, ClassificationDecision) for snapshot in snapshots)

    def list_all(self) -> tuple[ClassificationDecision, ...]:
        return tuple(
            _from_snapshot(snapshot, ClassificationDecision)
            for snapshot in self._collection.stream()
        )

    def update_category(
        self,
        household_id: str,
        source_category_id: str,
        target_category_id: str,
    ) -> None:
        snapshots = self._collection.where(
            filter=FieldFilter("household_id", "==", household_id)
        ).stream()
        for snapshot in snapshots:
            if (snapshot.to_dict() or {}).get("category_id") == source_category_id:
                snapshot.reference.update({"category_id": target_category_id})

    def delete_by_household(self, household_id: str) -> None:
        if self._households.get_by_id(household_id) is None:
            raise HouseholdNotFound("Household not found")
        references = (
            snapshot.reference
            for snapshot in self._collection.where(
                filter=FieldFilter("household_id", "==", household_id)
            ).stream()
        )
        _delete_documents(self._client, references)


class _FirestoreArtifactRepository(Generic[HouseholdRecordT]):
    def __init__(
        self,
        client: firestore.Client,
        households: HouseholdRepository,
        collection_name: str,
        model_type: type[HouseholdRecordT],
    ) -> None:
        self._client = client
        self._collection = client.collection(collection_name)
        self._households = households
        self._model_type: type[HouseholdRecordT] = model_type

    def add(self, item: HouseholdRecordT) -> HouseholdRecordT:
        if self._households.get_by_id(item.household_id) is None:
            raise HouseholdNotFound("Household not found")
        reference = self._collection.document(item.id)
        if reference.get().exists:
            raise DuplicateRecord("Record identifier already exists")
        reference.set(_model_data(item))
        return item

    def list_by_household(self, household_id: str) -> tuple[HouseholdRecordT, ...]:
        if self._households.get_by_id(household_id) is None:
            raise HouseholdNotFound("Household not found")
        snapshots = self._collection.where(
            filter=FieldFilter("household_id", "==", household_id)
        ).stream()
        return tuple(_from_snapshot(snapshot, self._model_type) for snapshot in snapshots)

    def delete_by_household(self, household_id: str) -> None:
        if self._households.get_by_id(household_id) is None:
            raise HouseholdNotFound("Household not found")
        references = (
            snapshot.reference
            for snapshot in self._collection.where(
                filter=FieldFilter("household_id", "==", household_id)
            ).stream()
        )
        _delete_documents(self._client, references)


class FirestoreImportRunRepository(_FirestoreArtifactRepository[ImportRun]):
    def __init__(self, client: firestore.Client, households: HouseholdRepository) -> None:
        super().__init__(client, households, "imports", ImportRun)


class FirestoreInsightRunRepository(_FirestoreArtifactRepository[InsightRun]):
    def __init__(self, client: firestore.Client, households: HouseholdRepository) -> None:
        super().__init__(client, households, "insight_runs", InsightRun)


class FirestoreEvaluationRunRepository(_FirestoreArtifactRepository[EvaluationRun]):
    def __init__(self, client: firestore.Client, households: HouseholdRepository) -> None:
        super().__init__(client, households, "evaluation_runs", EvaluationRun)


class FirestoreMerchantContextRepository:
    def __init__(self, client: firestore.Client, households: HouseholdRepository) -> None:
        self._client = client
        self._contexts = client.collection("merchant_contexts")
        self._maps = client.collection("llm_data_maps")
        self._households = households

    def get_by_original(self, household_id: str, original_value: str) -> MerchantContext | None:
        normalized = normalize_text(original_value)
        snapshots = self._contexts.where(filter=FieldFilter("household_id", "==", household_id))
        for snapshot in snapshots.stream():
            context = _from_snapshot(snapshot, MerchantContext)
            if normalize_text(context.original_value) == normalized:
                return context
        return None

    def save(
        self,
        context: MerchantContext,
        data_map: LLMDataMap | None = None,
    ) -> MerchantContext:
        if self._households.get_by_id(context.household_id) is None:
            raise HouseholdNotFound("Household not found")
        self._contexts.document(context.id).set(_model_data(context))
        if data_map is not None:
            if data_map.household_id != context.household_id:
                raise HouseholdNotFound("Data map household does not match its context")
            self._maps.document(data_map.id).set(_model_data(data_map))
        return context

    def list_by_household(self, household_id: str) -> tuple[MerchantContext, ...]:
        if self._households.get_by_id(household_id) is None:
            raise HouseholdNotFound("Household not found")
        snapshots = self._contexts.where(filter=FieldFilter("household_id", "==", household_id))
        return tuple(_from_snapshot(snapshot, MerchantContext) for snapshot in snapshots.stream())

    def delete_by_household(self, household_id: str) -> None:
        if self._households.get_by_id(household_id) is None:
            raise HouseholdNotFound("Household not found")
        for collection in (self._contexts, self._maps):
            references = (
                snapshot.reference
                for snapshot in collection.where(
                    filter=FieldFilter("household_id", "==", household_id)
                ).stream()
            )
            _delete_documents(self._client, references)


def create_firestore_demo_repositories(client: firestore.Client) -> DemoRepositories:
    from home_financial_backend.domain.seed import DEMO_HOUSEHOLD, build_demo_categories

    household_repository = FirestoreHouseholdRepository(client)
    household_ref = client.collection("households").document(DEMO_HOUSEHOLD.id)
    if not household_ref.get().exists:
        household_ref.set(_model_data(DEMO_HOUSEHOLD))
    household_repository.get_demo()

    category_repository = FirestoreCategoryRepository(client, household_repository)
    for category in build_demo_categories():
        if category_repository.get_for_household(category.id, category.household_id) is None:
            client.collection("categories").document(category.id).set(_model_data(category))

    expense_repository = FirestoreExpenseRepository(
        client,
        household_repository,
        category_repository,
    )
    decision_repository = FirestoreClassificationDecisionRepository(
        client,
        household_repository,
        expense_repository,
        category_repository,
    )
    return DemoRepositories(
        households=household_repository,
        categories=category_repository,
        expenses=expense_repository,
        classification_decisions=decision_repository,
        import_runs=FirestoreImportRunRepository(client, household_repository),
        insight_runs=FirestoreInsightRunRepository(client, household_repository),
        evaluation_runs=FirestoreEvaluationRunRepository(client, household_repository),
        merchant_contexts=FirestoreMerchantContextRepository(client, household_repository),
    )
