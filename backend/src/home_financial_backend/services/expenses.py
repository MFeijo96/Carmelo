from uuid import uuid4

from home_financial_backend.api.contracts import ExpenseCreateRequest
from home_financial_backend.domain.errors import CategoryNotFound, HouseholdNotFound
from home_financial_backend.domain.models import (
    ClassificationDecision,
    Expense,
    ExpenseSource,
    SafeClassificationContext,
    utc_now,
)
from home_financial_backend.domain.repositories import (
    CategoryRepository,
    ClassificationDecisionRepository,
    ExpenseRepository,
    HouseholdRepository,
)
from home_financial_backend.observability import confidence_bucket, log_event
from home_financial_backend.services.classification import (
    ClassificationInput,
    ClassificationService,
)
from home_financial_backend.services.merchant_context import MerchantContextService


class ExpenseService:
    def __init__(
        self,
        households: HouseholdRepository,
        categories: CategoryRepository,
        expenses: ExpenseRepository,
        decisions: ClassificationDecisionRepository,
        classifier: ClassificationService,
        merchant_contexts: MerchantContextService | None = None,
    ) -> None:
        self._households = households
        self._categories = categories
        self._expenses = expenses
        self._decisions = decisions
        self._classifier = classifier
        self._merchant_contexts = merchant_contexts

    def create_manual(
        self,
        household_id: str,
        request: ExpenseCreateRequest,
        safe_context: SafeClassificationContext | None = None,
    ) -> Expense:
        return self._create(household_id, request, source="manual", safe_context=safe_context)

    def create_imported(
        self,
        household_id: str,
        request: ExpenseCreateRequest,
        safe_context: SafeClassificationContext | None = None,
    ) -> Expense:
        return self._create(household_id, request, source="csv", safe_context=safe_context)

    def _create(
        self,
        household_id: str,
        request: ExpenseCreateRequest,
        *,
        source: ExpenseSource,
        safe_context: SafeClassificationContext | None,
    ) -> Expense:
        if self._households.get_by_id(household_id) is None:
            raise HouseholdNotFound("Household not found")
        expense_id = uuid4().hex
        decision = self._classifier.classify(
            ClassificationInput(
                expense_id=expense_id,
                household_id=household_id,
                description=request.description,
                merchant=request.merchant,
                explicit_category_id=request.category_id,
                safe_context=safe_context
                or self._classification_context(household_id, request.merchant),
            )
        )
        now = utc_now()
        expense = Expense(
            id=expense_id,
            household_id=household_id,
            date=request.date,
            description=request.description,
            amount_cents=request.amount_cents,
            payment_method=request.payment_method,
            recurring=request.recurring,
            category_id=decision.category_id,
            merchant=request.merchant,
            notes=request.notes,
            source=source,
            confidence=decision.confidence,
            review_required=decision.review_required,
            user_override=decision.user_override,
            created_at=now,
            updated_at=now,
        )
        self._expenses.add(expense)
        self._decisions.add(decision)
        self._record_merchant(household_id, expense)
        log_event(
            "expense_classified",
            expense_source=source,
            decision_source=decision.source,
            confidence_bucket=confidence_bucket(decision.confidence),
            review_required=decision.review_required,
        )
        return expense

    def _classification_context(
        self,
        household_id: str,
        merchant: str | None,
    ) -> SafeClassificationContext | None:
        if self._merchant_contexts is not None:
            return self._merchant_contexts.classification_context(household_id, merchant)
        if merchant is None or not merchant.strip():
            return None
        return SafeClassificationContext(
            merchant_alias=f"Estabelecimento {uuid4().hex[:8]}",
            business_context="Contexto comercial não identificado.",
            category_hints=(),
            recurring_count=0,
        )

    def _record_merchant(self, household_id: str, expense: Expense) -> None:
        if self._merchant_contexts is None:
            return
        category = self._categories.get_for_household(expense.category_id, household_id)
        if category is not None:
            self._merchant_contexts.record_expense(
                household_id,
                expense.merchant,
                category.label,
                expense.recurring,
            )

    def correct_category(
        self,
        household_id: str,
        expense_id: str,
        category_id: str,
    ) -> Expense:
        expense = self._expenses.get_for_household(expense_id, household_id)
        if expense is None:
            raise CategoryNotFound("Expense not found in household")
        self._categories.require_active_leaf(household_id, category_id)
        decision = ClassificationDecision(
            id=uuid4().hex,
            household_id=household_id,
            expense_id=expense_id,
            category_id=category_id,
            confidence=1.0,
            reason="Categoria corrigida pelo usuário.",
            source="user_supplied",
            review_required=False,
            user_override=True,
        )
        updated_expense = expense.model_copy(
            update={
                "category_id": category_id,
                "confidence": 1.0,
                "review_required": False,
                "user_override": True,
                "updated_at": utc_now(),
            }
        )
        self._expenses.update(updated_expense)
        self._decisions.add(decision)
        log_event("expense_corrected", previously_overridden=expense.user_override)
        return updated_expense
