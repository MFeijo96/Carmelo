from secrets import token_hex
from uuid import uuid4

from home_financial_backend.domain.models import (
    Expense,
    LLMDataMap,
    MerchantContext,
    SafeClassificationContext,
)
from home_financial_backend.domain.normalization import normalize_text
from home_financial_backend.domain.repositories import MerchantContextRepository

UNKNOWN_BUSINESS_CONTEXT = "Contexto comercial não identificado."
MAX_CATEGORY_HINTS = 3


class MerchantContextService:
    """Owns the backend-only merchant alias map and the provider-safe projection."""

    def __init__(self, contexts: MerchantContextRepository) -> None:
        self._contexts = contexts

    def classification_context(
        self,
        household_id: str,
        merchant: str | None,
    ) -> SafeClassificationContext | None:
        if merchant is None or not merchant.strip():
            return None
        return self._project(self._get_or_create(household_id, merchant))

    def record_expense(
        self,
        household_id: str,
        merchant: str | None,
        category_label: str,
        recurring: bool,
    ) -> None:
        if merchant is None or not merchant.strip():
            return
        context = self._get_or_create(household_id, merchant)
        hints = context.category_hints
        if category_label not in hints:
            hints = (*hints, category_label)[-MAX_CATEGORY_HINTS:]
        self._contexts.save(
            context.model_copy(
                update={
                    "category_hints": hints,
                    "recurring_count": context.recurring_count + int(recurring),
                }
            )
        )

    def insight_projection(
        self,
        household_id: str,
        expenses: tuple[Expense, ...],
    ) -> tuple[SafeClassificationContext, ...]:
        merchants = {normalize_text(item.merchant) for item in expenses if item.merchant}
        projection = [
            self._project(context)
            for context in self._contexts.list_by_household(household_id)
            if normalize_text(context.original_value) in merchants
        ]
        return tuple(sorted(projection, key=lambda item: item.merchant_alias or ""))

    def _get_or_create(self, household_id: str, merchant: str) -> MerchantContext:
        existing = self._contexts.get_by_original(household_id, merchant)
        if existing is not None:
            return existing
        alias = f"Estabelecimento {token_hex(4)}"
        context = MerchantContext(
            id=uuid4().hex,
            household_id=household_id,
            original_value=merchant.strip(),
            alias=alias,
            business_context=UNKNOWN_BUSINESS_CONTEXT,
            category_hints=(),
            recurring_count=0,
        )
        data_map = LLMDataMap(
            id=uuid4().hex,
            household_id=household_id,
            alias=alias,
            merchant_context_id=context.id,
        )
        return self._contexts.save(context, data_map)

    @staticmethod
    def _project(context: MerchantContext) -> SafeClassificationContext:
        return SafeClassificationContext(
            merchant_alias=context.alias,
            business_context=context.business_context,
            category_hints=context.category_hints,
            recurring_count=context.recurring_count,
        )
