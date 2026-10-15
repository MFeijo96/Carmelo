from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from pydantic import ValidationError

from home_financial_backend.domain.errors import (
    CategoryNotFound,
    FallbackUnavailable,
    HouseholdNotFound,
    ParentCategoryNotAssignable,
)
from home_financial_backend.domain.models import (
    Category,
    ClassificationDecision,
    ClassificationSource,
    Expense,
    SafeClassificationContext,
)
from home_financial_backend.domain.normalization import normalize_text
from home_financial_backend.domain.repositories import (
    CategoryRepository,
    DecisionHistory,
    ExpenseLookup,
)
from home_financial_backend.runtime.contracts import ClassificationCandidate


@dataclass(frozen=True)
class ClassificationInput:
    expense_id: str
    household_id: str
    description: str
    merchant: str | None = None
    explicit_category_id: str | None = None
    safe_context: SafeClassificationContext | None = None


@dataclass(frozen=True)
class CategoryRule:
    category_id: str
    terms: tuple[str, ...]


DEFAULT_RULES = (
    CategoryRule("category-mercado", ("supermercado", "mercearia", "mercado", "acougue", "feira")),
    CategoryRule(
        "category-restaurantes",
        ("restaurante", "lanchonete", "pizzaria", "delivery", "cafeteria"),
    ),
    CategoryRule("category-moradia", ("aluguel", "condominio", "prestacao da casa")),
    CategoryRule(
        "category-contas-da-casa",
        (
            "conta de luz",
            "conta de agua",
            "energia eletrica",
            "internet residencial",
            "gas de cozinha",
        ),
    ),
    CategoryRule(
        "category-transporte",
        ("combustivel", "gasolina", "onibus", "metro", "estacionamento", "transporte"),
    ),
    CategoryRule("category-saude", ("farmacia", "remedio", "consulta medica", "plano de saude")),
    CategoryRule(
        "category-educacao", ("mensalidade escolar", "material escolar", "curso", "escola")
    ),
    CategoryRule("category-assinaturas", ("assinatura", "streaming", "servico de streaming")),
    CategoryRule("category-dividas", ("financiamento", "parcela de emprestimo", "juros da divida")),
    CategoryRule("category-pets", ("veterinario", "racao", "pet shop")),
    CategoryRule("category-impostos-taxas", ("ipva", "iptu", "taxa municipal")),
    CategoryRule("category-cuidados-pessoais", ("cabeleireiro", "barbearia", "higiene pessoal")),
    CategoryRule("category-lazer", ("cinema", "parque de diversoes", "ingresso de show")),
)

FallbackClassifier = Callable[
    [SafeClassificationContext, tuple[Category, ...]],
    ClassificationCandidate | dict[str, object] | None,
]


class ClassificationService:
    def __init__(
        self,
        categories: CategoryRepository,
        expenses: ExpenseLookup,
        decisions: DecisionHistory,
        fallback_classifier: FallbackClassifier | None = None,
        rules: tuple[CategoryRule, ...] = DEFAULT_RULES,
    ) -> None:
        self._categories = categories
        self._expenses = expenses
        self._decisions = decisions
        self._fallback_classifier = fallback_classifier
        self._rules = rules

    def classify(self, item: ClassificationInput) -> ClassificationDecision:
        household = self._categories.list_by_household(item.household_id)
        if not household:
            raise HouseholdNotFound("Household has no categories")

        if item.explicit_category_id is not None:
            category = self._categories.require_active_leaf(
                item.household_id,
                item.explicit_category_id,
            )
            return self._decision(
                item,
                category,
                confidence=1.0,
                reason="Categoria informada pelo usuário.",
                source="user_supplied",
                user_override=True,
            )

        exact_correction = self._exact_household_correction(item)
        if exact_correction is not None:
            category = self._categories.require_active_leaf(item.household_id, exact_correction)
            return self._decision(
                item,
                category,
                confidence=0.95,
                reason="Categoria definida em uma correção anterior desta despesa.",
                source="exact_household_correction",
                user_override=False,
            )

        rule_match = self._most_specific_rule(item)
        if rule_match is not None:
            category, term = rule_match
            confidence = min(0.96, 0.72 + len(term) / 100)
            return self._decision(
                item,
                category,
                confidence=confidence,
                reason="Categoria sugerida por uma regra determinística.",
                source="deterministic_rule",
                user_override=False,
            )

        household_counts = self._frequency_counts(item, item.household_id)
        household_winners = self._frequency_winners(household_counts)
        if len(household_winners) == 1:
            category_id = self._category_id_for_key(item.household_id, household_winners[0])
        else:
            category_id = None
        if category_id is not None:
            category = self._categories.require_active_leaf(item.household_id, category_id)
            return self._decision(
                item,
                category,
                confidence=0.78,
                reason="Categoria baseada em correções anteriores desta casa.",
                source="household_frequency",
                user_override=False,
            )

        if len(household_winners) > 1:
            global_counts = self._frequency_counts(item, None, set(household_winners))
            global_winners = self._frequency_winners(global_counts)
            category_id = (
                self._category_id_for_key(item.household_id, global_winners[0])
                if len(global_winners) == 1
                else None
            )
        else:
            category_id = None
        if category_id is not None:
            category = self._categories.require_active_leaf(item.household_id, category_id)
            return self._decision(
                item,
                category,
                confidence=0.70,
                reason="Categoria escolhida pelo desempate de frequências de correção.",
                source="global_frequency",
                user_override=False,
            )

        llm_decision = self._llm_fallback(item, household)
        if llm_decision is not None:
            return llm_decision

        fallback_category = self._categories.require_active_leaf(
            item.household_id,
            "category-outros",
        )
        return self._decision(
            item,
            fallback_category,
            confidence=0.0,
            reason="Não foi possível sugerir uma categoria; revise esta despesa.",
            source="fallback_outros",
            user_override=False,
            review_required=True,
        )

    def _corrections_for(
        self, household_id: str | None
    ) -> list[tuple[ClassificationDecision, Expense]]:
        decisions = (
            self._decisions.list_by_household(household_id)
            if household_id is not None
            else self._decisions.list_all()
        )
        corrections: list[tuple[ClassificationDecision, Expense]] = []
        for decision in decisions:
            if not decision.user_override or decision.source != "user_supplied":
                continue
            expense = self._expenses.get_for_household(decision.expense_id, decision.household_id)
            if expense is not None:
                corrections.append((decision, expense))
        return corrections

    def _exact_household_correction(
        self,
        item: ClassificationInput,
    ) -> str | None:
        normalized_merchant = normalize_text(item.merchant)
        normalized_description = normalize_text(item.description)
        matches = [
            (decision, expense)
            for decision, expense in self._corrections_for(item.household_id)
            if normalize_text(expense.merchant) == normalized_merchant
            and normalize_text(expense.description) == normalized_description
        ]
        if not matches:
            return None
        decision, _ = max(matches, key=lambda pair: pair[0].created_at)
        return decision.category_id

    @staticmethod
    def _history_key(expense: Expense) -> str:
        return normalize_text(expense.merchant) or normalize_text(expense.description)

    def _frequency_counts(
        self,
        item: ClassificationInput,
        household_id: str | None,
        allowed_keys: set[str] | None = None,
    ) -> Counter[str]:
        key = normalize_text(item.merchant) or normalize_text(item.description)
        corrections = self._corrections_for(household_id)
        counts: Counter[str] = Counter()
        for decision, expense in corrections:
            if self._history_key(expense) != key:
                continue
            category = self._categories.get_for_household(
                decision.category_id,
                decision.household_id,
            )
            if category is not None and (
                allowed_keys is None or category.canonical_key in allowed_keys
            ):
                counts[category.canonical_key] += 1
        return counts

    @staticmethod
    def _frequency_winners(counts: Counter[str]) -> list[str]:
        if not counts:
            return []
        highest = max(counts.values())
        return [canonical_key for canonical_key, count in counts.items() if count == highest]

    def _category_id_for_key(self, household_id: str, canonical_key: str) -> str | None:
        return next(
            (
                category.id
                for category in self._categories.list_by_household(household_id)
                if category.canonical_key == canonical_key
                and category.is_active
                and self._categories.is_active_leaf(household_id, category.id)
            ),
            None,
        )

    def _most_specific_rule(self, item: ClassificationInput) -> tuple[Category, str] | None:
        text = normalize_text(f"{item.description} {item.merchant or ''}")
        matches: list[tuple[int, str, str]] = []
        for rule in self._rules:
            for raw_term in rule.terms:
                term = normalize_text(raw_term)
                if term and term in text:
                    matches.append((len(term), rule.category_id, term))
        if not matches:
            return None

        specificity = max(match[0] for match in matches)
        most_specific = [match for match in matches if match[0] == specificity]
        category_ids = {match[1] for match in most_specific}
        if len(category_ids) != 1:
            return None
        category_id = next(iter(category_ids))
        try:
            category = self._categories.require_active_leaf(item.household_id, category_id)
        except CategoryNotFound:
            return None
        term = max((match[2] for match in most_specific), key=len)
        return category, term

    def _llm_fallback(
        self,
        item: ClassificationInput,
        household_categories: tuple[Category, ...],
    ) -> ClassificationDecision | None:
        if self._fallback_classifier is None or item.safe_context is None:
            return None
        leaf_categories = tuple(
            category
            for category in household_categories
            if category.is_active
            and self._categories.is_active_leaf(item.household_id, category.id)
        )
        try:
            raw_candidate = self._fallback_classifier(item.safe_context, leaf_categories)
            if raw_candidate is None:
                return None
            candidate = ClassificationCandidate.model_validate(raw_candidate)
            category = self._categories.require_active_leaf(
                item.household_id,
                candidate.category_id,
            )
        except (
            ValidationError,
            CategoryNotFound,
            ParentCategoryNotAssignable,
            FallbackUnavailable,
            OSError,
        ):
            return None
        return self._decision(
            item,
            category,
            confidence=candidate.confidence,
            reason=candidate.reason,
            source="llm_fallback",
            user_override=False,
            review_required=candidate.review_required or candidate.confidence < 0.70,
        )

    @staticmethod
    def _decision(
        item: ClassificationInput,
        category: Category,
        *,
        confidence: float,
        reason: str,
        source: ClassificationSource,
        user_override: bool,
        review_required: bool = False,
    ) -> ClassificationDecision:
        return ClassificationDecision(
            id=uuid4().hex,
            household_id=item.household_id,
            expense_id=item.expense_id,
            category_id=category.id,
            confidence=confidence,
            reason=reason,
            source=source,
            review_required=review_required or confidence < 0.70,
            user_override=user_override,
        )
