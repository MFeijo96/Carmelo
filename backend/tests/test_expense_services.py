from datetime import date
from types import SimpleNamespace

import pytest

from home_financial_backend.api.contracts import ExpenseCreateRequest
from home_financial_backend.domain.errors import CSVStructureError
from home_financial_backend.domain.models import (
    ClassificationDecision,
    Expense,
    Household,
    SafeClassificationContext,
)
from home_financial_backend.domain.seed import DEMO_HOUSEHOLD, build_demo_categories
from home_financial_backend.infrastructure.memory_repositories import (
    InMemoryCategoryRepository,
    InMemoryClassificationDecisionRepository,
    InMemoryExpenseRepository,
    InMemoryHouseholdRepository,
    create_demo_repositories,
)
from home_financial_backend.runtime.contracts import ClassificationCandidate
from home_financial_backend.services.classification import (
    CategoryRule,
    ClassificationInput,
    ClassificationService,
)
from home_financial_backend.services.csv_import import CSVImportService
from home_financial_backend.services.expenses import ExpenseService

DEMO_HOUSEHOLD_ID = "demo-household"


def make_request(
    description: str,
    *,
    merchant: str | None = None,
    category_id: str | None = None,
) -> ExpenseCreateRequest:
    return ExpenseCreateRequest(
        date=date(2026, 10, 1),
        description=description,
        amount_cents=1500,
        payment_method="dinheiro",
        merchant=merchant,
        category_id=category_id,
    )


def make_services(fallback=None, rules=None):
    repositories = create_demo_repositories()
    classifier = ClassificationService(
        categories=repositories.categories,
        expenses=repositories.expenses,
        decisions=repositories.classification_decisions,
        fallback_classifier=fallback,
        **({"rules": rules} if rules is not None else {}),
    )
    expense_service = ExpenseService(
        households=repositories.households,
        categories=repositories.categories,
        expenses=repositories.expenses,
        decisions=repositories.classification_decisions,
        classifier=classifier,
    )
    return repositories, classifier, expense_service


def add_user_correction(
    repositories,
    *,
    household_id: str,
    expense_id: str,
    description: str,
    merchant: str,
    category_id: str,
) -> None:
    expense = Expense(
        id=expense_id,
        household_id=household_id,
        date=date(2026, 9, 1),
        description=description,
        amount_cents=500,
        payment_method="credito",
        category_id=category_id,
        merchant=merchant,
        source="manual",
        user_override=True,
    )
    repositories.expenses.add(expense)
    repositories.classification_decisions.add(
        ClassificationDecision(
            id=f"decision-{expense_id}",
            household_id=household_id,
            expense_id=expense_id,
            category_id=category_id,
            confidence=1.0,
            reason="Correção de teste.",
            source="user_supplied",
            review_required=False,
            user_override=True,
        )
    )


def test_manual_creation_honors_user_category_and_records_decision() -> None:
    repositories, _, expense_service = make_services()

    expense = expense_service.create_manual(
        DEMO_HOUSEHOLD_ID,
        make_request("Compra no supermercado", category_id="category-restaurantes"),
    )

    assert expense.category_id == "category-restaurantes"
    assert expense.user_override is True
    assert expense.source == "manual"
    decision = repositories.classification_decisions.list_by_household(DEMO_HOUSEHOLD_ID)[0]
    assert decision.source == "user_supplied"
    assert decision.confidence == 1.0


def test_most_specific_deterministic_rule_wins_over_shorter_rule() -> None:
    _, _, expense_service = make_services()

    expense = expense_service.create_manual(
        DEMO_HOUSEHOLD_ID,
        make_request("Compra no supermercado e restaurante"),
    )

    assert expense.category_id == "category-mercado"
    assert expense.review_required is False


def test_exact_household_correction_precedes_deterministic_rule() -> None:
    repositories, _, expense_service = make_services()
    original = expense_service.create_manual(
        DEMO_HOUSEHOLD_ID,
        make_request("Compra no supermercado", merchant="Mercado Central"),
    )
    corrected = expense_service.correct_category(
        DEMO_HOUSEHOLD_ID,
        original.id,
        "category-restaurantes",
    )

    repeated = expense_service.create_manual(
        DEMO_HOUSEHOLD_ID,
        make_request("  COMPRA NO SUPERMERCADO ", merchant="mercado central"),
    )

    assert corrected.category_id == "category-restaurantes"
    assert corrected.user_override is True
    assert repeated.category_id == "category-restaurantes"
    latest_decision = repositories.classification_decisions.list_by_household(DEMO_HOUSEHOLD_ID)[-1]
    assert latest_decision.source == "exact_household_correction"


def test_household_correction_frequency_resolves_unmatched_merchant() -> None:
    _, _, expense_service = make_services()
    for index in range(2):
        expense = expense_service.create_manual(
            DEMO_HOUSEHOLD_ID,
            make_request(f"Compra avulsa {index}", merchant="Loja da Casa"),
        )
        expense_service.correct_category(
            DEMO_HOUSEHOLD_ID,
            expense.id,
            "category-mercado",
        )

    suggested = expense_service.create_manual(
        DEMO_HOUSEHOLD_ID,
        make_request("Compra avulsa nova", merchant="LOJA DA CASA"),
    )

    assert suggested.category_id == "category-mercado"
    assert suggested.review_required is False


def test_unambiguous_rule_precedes_household_correction_frequency() -> None:
    _, _, expense_service = make_services()
    previous = expense_service.create_manual(
        DEMO_HOUSEHOLD_ID,
        make_request("Compra avulsa", merchant="Loja Comum"),
    )
    expense_service.correct_category(
        DEMO_HOUSEHOLD_ID,
        previous.id,
        "category-mercado",
    )

    classified = expense_service.create_manual(
        DEMO_HOUSEHOLD_ID,
        make_request("Jantar em restaurante", merchant="LOJA COMUM"),
    )

    assert classified.category_id == "category-restaurantes"


def test_global_correction_frequency_only_breaks_household_tie() -> None:
    second_household = Household(id="other-household", name="Outra casa", is_demo=False)
    households = InMemoryHouseholdRepository((DEMO_HOUSEHOLD, second_household))
    demo_categories = build_demo_categories()
    other_categories = tuple(
        category.model_copy(
            update={
                "id": f"other-{category.id}",
                "household_id": second_household.id,
                "parent_category_id": (
                    f"other-{category.parent_category_id}" if category.parent_category_id else None
                ),
            }
        )
        for category in demo_categories
    )
    categories = InMemoryCategoryRepository((*demo_categories, *other_categories), households)
    expenses = InMemoryExpenseRepository(households, categories)
    decisions = InMemoryClassificationDecisionRepository(households, expenses, categories)
    repositories = SimpleNamespace(
        households=households,
        categories=categories,
        expenses=expenses,
        classification_decisions=decisions,
    )
    add_user_correction(
        repositories,
        household_id=DEMO_HOUSEHOLD_ID,
        expense_id="demo-market",
        description="Compra avulsa um",
        merchant="Loja Global",
        category_id="category-mercado",
    )
    add_user_correction(
        repositories,
        household_id=DEMO_HOUSEHOLD_ID,
        expense_id="demo-restaurant",
        description="Compra avulsa dois",
        merchant="Loja Global",
        category_id="category-restaurantes",
    )
    add_user_correction(
        repositories,
        household_id=second_household.id,
        expense_id="other-market",
        description="Compra avulsa tres",
        merchant="Loja Global",
        category_id="other-category-mercado",
    )
    classifier = ClassificationService(categories, expenses, decisions)

    result = classifier.classify(
        ClassificationInput(
            expense_id="new-expense",
            household_id=DEMO_HOUSEHOLD_ID,
            description="Compra avulsa quatro",
            merchant="Loja Global",
        )
    )

    assert result.category_id == "category-mercado"
    assert result.source == "global_frequency"


def test_global_frequency_does_not_classify_without_household_correction_tie() -> None:
    repositories, _, _ = make_services()
    add_user_correction(
        repositories,
        household_id=DEMO_HOUSEHOLD_ID,
        expense_id="global-only-correction",
        description="Compra anterior sem regra",
        merchant="Global sem empate",
        category_id="category-mercado",
    )

    class NoHouseholdHistory:
        def list_by_household(self, household_id: str):
            return ()

        def list_all(self):
            return repositories.classification_decisions.list_all()

    classifier = ClassificationService(
        categories=repositories.categories,
        expenses=repositories.expenses,
        decisions=NoHouseholdHistory(),
    )
    decision = classifier.classify(
        ClassificationInput(
            expense_id="no-local-history",
            household_id=DEMO_HOUSEHOLD_ID,
            description="Compra nova sem regra",
            merchant="Global sem empate",
        )
    )

    assert decision.category_id == "category-outros"
    assert decision.source == "fallback_outros"


def test_llm_fallback_receives_only_safe_context_and_marks_low_confidence_review() -> None:
    observed = {}

    def fallback(context, categories):
        observed["context"] = context
        observed["categories"] = categories
        return ClassificationCandidate(
            category_id="category-restaurantes",
            confidence=0.65,
            reason="Contexto de estabelecimento compatível.",
            source="llm_fallback",
            review_required=False,
        )

    _, classifier, _ = make_services(fallback=fallback)
    safe_context = SafeClassificationContext(
        merchant_alias="Estabelecimento 7",
        business_context="Alimentação preparada",
        category_hints=("restaurantes",),
        recurring_count=1,
    )

    decision = classifier.classify(
        ClassificationInput(
            expense_id="fallback-expense",
            household_id=DEMO_HOUSEHOLD_ID,
            description="Descrição privada não enviada",
            merchant="Nome privado não enviado",
            safe_context=safe_context,
        )
    )

    assert observed["context"] == safe_context
    assert set(safe_context.model_dump()) == {
        "merchant_alias",
        "business_context",
        "category_hints",
        "recurring_count",
    }
    assert decision.category_id == "category-restaurantes"
    assert decision.review_required is True


def test_unresolved_or_ambiguous_classification_falls_back_to_outros_for_review() -> None:
    ambiguous_rules = (
        CategoryRule("category-mercado", ("mercado",)),
        CategoryRule("category-restaurantes", ("passeio",)),
    )
    _, classifier, _ = make_services(rules=ambiguous_rules)

    decision = classifier.classify(
        ClassificationInput(
            expense_id="unresolved-expense",
            household_id=DEMO_HOUSEHOLD_ID,
            description="mercado passeio sem contexto",
        )
    )

    assert decision.category_id == "category-outros"
    assert decision.source == "fallback_outros"
    assert decision.confidence == 0
    assert decision.review_required is True


def test_csv_import_keeps_valid_rows_and_rejects_parent_category_row() -> None:
    repositories, _, expense_service = make_services()
    importer = CSVImportService(
        categories=repositories.categories,
        import_runs=repositories.import_runs,
        expenses=expense_service,
    )
    content = (
        "data,descricao,valor,forma_pagamento,estabelecimento,categoria,recorrente,observacoes\n"
        '01/10/2026,Compra do mês,"R$ 1.234,56",Debito,Mercado XP,Mercado,sim,\n'
        '01/10/2026,Compra no mercado,"12,00",credito,Mercado XP,Alimentação,nao,\n'
        '02/10/2026,Jantar em restaurante,"35,90",credito,Restaurante Y,,nao,\n'
        '03/10/2026,Descrição inválida,"10,00",pix,,,nao,\n'
    )

    result = importer.import_text(DEMO_HOUSEHOLD_ID, content, "despesas.csv")
    expenses = repositories.expenses.list_by_household(DEMO_HOUSEHOLD_ID)

    assert (result.total_rows, result.imported_rows, result.rejected_rows) == (4, 2, 2)
    assert len(result.row_errors) == 2
    assert result.row_errors[0].row == 3
    assert result.row_errors[0].field == "categoria"
    assert result.row_errors[1].field == "forma_pagamento"
    assert sorted(expense.amount_cents for expense in expenses) == [3590, 123456]
    assert next(expense for expense in expenses if expense.amount_cents == 123456).recurring is True
    assert next(expense for expense in expenses if expense.amount_cents == 3590).category_id == (
        "category-restaurantes"
    )
    assert repositories.import_runs.list_by_household(DEMO_HOUSEHOLD_ID) == (result,)


def test_structurally_invalid_csv_is_rejected_before_any_writes() -> None:
    repositories, _, expense_service = make_services()
    importer = CSVImportService(
        categories=repositories.categories,
        import_runs=repositories.import_runs,
        expenses=expense_service,
    )

    with pytest.raises(CSVStructureError):
        importer.import_text(
            DEMO_HOUSEHOLD_ID,
            "data,descricao,valor\n01/10/2026,Uma linha,10,00\n",
        )

    assert repositories.expenses.list_by_household(DEMO_HOUSEHOLD_ID) == ()
    assert repositories.import_runs.list_by_household(DEMO_HOUSEHOLD_ID) == ()
