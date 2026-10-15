import os
from datetime import date

import pytest

firestore = pytest.importorskip("google.cloud.firestore")

from home_financial_backend.domain.models import (
    ClassificationDecision,
    EvaluationRun,
    Expense,
    ImportRun,
    InsightCard,
    InsightRun,
)
from home_financial_backend.domain.seed import DEMO_HOUSEHOLD
from home_financial_backend.infrastructure.firestore_repositories import (
    create_firestore_demo_repositories,
)
from home_financial_backend.services.categories import delete_demo_data
from home_financial_backend.services.classification import ClassificationService
from home_financial_backend.services.csv_import import CSVImportService
from home_financial_backend.services.dashboard import DashboardService
from home_financial_backend.services.expenses import ExpenseService
from home_financial_backend.services.exports import ExportService
from home_financial_backend.services.merchant_context import MerchantContextService

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason="Set FIRESTORE_EMULATOR_HOST to run Firestore Emulator integration tests.",
)


@pytest.fixture
def firestore_repositories():
    project_id = os.getenv("FIREBASE_PROJECT_ID", "demo-home-financial")
    client = firestore.Client(project=project_id)
    repositories = create_firestore_demo_repositories(client)

    def clear_demo() -> int:
        return delete_demo_data(
            DEMO_HOUSEHOLD.id,
            households=repositories.households,
            categories=repositories.categories,
            expenses=repositories.expenses,
            decisions=repositories.classification_decisions,
            import_runs=repositories.import_runs,
            insight_runs=repositories.insight_runs,
            evaluation_runs=repositories.evaluation_runs,
            merchant_contexts=repositories.merchant_contexts,
        )

    clear_demo()
    yield client, repositories, clear_demo
    clear_demo()
    client.close()


def test_firestore_merchant_alias_persists_is_not_exported_and_is_deleted(
    firestore_repositories,
) -> None:
    client, repositories, clear_demo = firestore_repositories
    contexts = MerchantContextService(repositories.merchant_contexts)
    expenses = ExpenseService(
        repositories.households,
        repositories.categories,
        repositories.expenses,
        repositories.classification_decisions,
        ClassificationService(
            repositories.categories,
            repositories.expenses,
            repositories.classification_decisions,
        ),
        merchant_contexts=contexts,
    )
    request = {
        "date": date(2026, 10, 12),
        "description": "Compra privada",
        "amount_cents": 5000,
        "payment_method": "debito",
        "category_id": "category-mercado",
        "merchant": "Mercado Emulador 4242",
        "recurring": True,
    }
    from home_financial_backend.api.contracts import ExpenseCreateRequest

    expenses.create_manual(DEMO_HOUSEHOLD.id, ExpenseCreateRequest(**request))
    expenses.create_manual(DEMO_HOUSEHOLD.id, ExpenseCreateRequest(**request))

    reopened = create_firestore_demo_repositories(client)
    stored = reopened.merchant_contexts.list_by_household(DEMO_HOUSEHOLD.id)
    assert len(stored) == 1
    assert stored[0].recurring_count == 2
    assert stored[0].category_hints == ("Mercado",)

    exporter = ExportService(
        reopened.households,
        reopened.categories,
        reopened.expenses,
        reopened.import_runs,
        reopened.classification_decisions,
        reopened.insight_runs,
        reopened.evaluation_runs,
    )
    exported = (
        str(exporter.archive(DEMO_HOUSEHOLD.id)) + exporter.csv_expenses(DEMO_HOUSEHOLD.id)[0]
    )
    assert stored[0].alias not in exported
    assert "llm_data_maps" not in exported

    clear_demo()
    after_delete = create_firestore_demo_repositories(client)
    assert after_delete.merchant_contexts.list_by_household(DEMO_HOUSEHOLD.id) == ()
    assert list(client.collection("llm_data_maps").stream()) == []


def test_firestore_csv_import_is_visible_in_monthly_dashboard(firestore_repositories) -> None:
    _, repositories, _ = firestore_repositories
    classifier = ClassificationService(
        repositories.categories,
        repositories.expenses,
        repositories.classification_decisions,
    )
    expenses = ExpenseService(
        repositories.households,
        repositories.categories,
        repositories.expenses,
        repositories.classification_decisions,
        classifier,
    )
    importer = CSVImportService(
        repositories.categories,
        repositories.import_runs,
        expenses,
    )
    report = importer.import_text(
        DEMO_HOUSEHOLD.id,
        "data,descricao,valor,forma_pagamento,categoria,recorrente\n"
        '12/10/2026,Compra de integração,"125,50",credito,Mercado,sim\n',
        "emulator.csv",
    )
    dashboard = DashboardService(
        repositories.households,
        repositories.categories,
        repositories.expenses,
    ).monthly(DEMO_HOUSEHOLD.id, "2026-10")

    assert report.imported_rows == 1
    assert report.rejected_rows == 0
    assert dashboard.total_cents == 12550
    assert dashboard.expense_count == 1
    assert dashboard.recurring_cents == 12550


def test_firestore_persistence_exports_and_deletion(firestore_repositories) -> None:
    client, repositories, clear_demo = firestore_repositories
    expense = Expense(
        id="emulator-expense-1",
        household_id=DEMO_HOUSEHOLD.id,
        date=date(2026, 10, 12),
        description="Despesa de integração sintética",
        amount_cents=12550,
        payment_method="credito",
        recurring=True,
        category_id="category-mercado",
        source="manual",
        confidence=1.0,
        user_override=True,
    )
    repositories.expenses.add(expense)
    repositories.classification_decisions.add(
        ClassificationDecision(
            id="emulator-decision-1",
            household_id=DEMO_HOUSEHOLD.id,
            expense_id=expense.id,
            category_id=expense.category_id,
            confidence=1.0,
            reason="Categoria informada no teste de integração.",
            source="user_supplied",
            review_required=False,
            user_override=True,
        )
    )
    repositories.import_runs.add(
        ImportRun(
            id="emulator-import-1",
            household_id=DEMO_HOUSEHOLD.id,
            total_rows=1,
            imported_rows=1,
            rejected_rows=0,
            status="completed",
        )
    )
    repositories.insight_runs.add(
        InsightRun(
            id="emulator-insight-1",
            household_id=DEMO_HOUSEHOLD.id,
            month="2026-10",
            summary_version="1.0",
            summary_hash="synthetic-hash",
            cards=(
                InsightCard(
                    title="Resumo de teste",
                    text="As despesas do mês foram registradas para validação.",
                    source_refs=("opaque-test-source",),
                ),
            ),
            provider_status="not_configured",
            safety_status="fallback",
        )
    )
    repositories.evaluation_runs.add(
        EvaluationRun(
            id="emulator-evaluation-1",
            household_id=DEMO_HOUSEHOLD.id,
            dataset_version="test-v1",
            taxonomy_version="1.0",
            total_count=1,
            correct_count=1,
            accuracy=1.0,
            passed=True,
        )
    )

    reopened = create_firestore_demo_repositories(client)
    persisted = reopened.expenses.get_for_household(expense.id, DEMO_HOUSEHOLD.id)
    assert persisted == expense
    assert len(reopened.classification_decisions.list_by_household(DEMO_HOUSEHOLD.id)) == 1

    exporter = ExportService(
        reopened.households,
        reopened.categories,
        reopened.expenses,
        reopened.import_runs,
        reopened.classification_decisions,
        reopened.insight_runs,
        reopened.evaluation_runs,
    )
    csv_content, _ = exporter.csv_expenses(DEMO_HOUSEHOLD.id)
    archive = exporter.archive(DEMO_HOUSEHOLD.id)
    assert '12/10/2026,Despesa de integração sintética,"125,50"' in csv_content
    assert len(archive["expenses"]) == 1
    assert len(archive["imports"]) == 1
    assert len(archive["classification_decisions"]) == 1
    assert len(archive["insights"]) == 1
    assert len(archive["evaluations"]) == 1

    assert clear_demo() == 1
    after_delete = create_firestore_demo_repositories(client)
    assert after_delete.households.get_demo().id == DEMO_HOUSEHOLD.id
    assert after_delete.expenses.list_by_household(DEMO_HOUSEHOLD.id) == ()
    assert after_delete.classification_decisions.list_by_household(DEMO_HOUSEHOLD.id) == ()
    assert after_delete.import_runs.list_by_household(DEMO_HOUSEHOLD.id) == ()
    assert after_delete.insight_runs.list_by_household(DEMO_HOUSEHOLD.id) == ()
    assert after_delete.evaluation_runs.list_by_household(DEMO_HOUSEHOLD.id) == ()
