import json
import logging
from time import perf_counter
from types import SimpleNamespace

import pytest

from home_financial_backend import observability
from home_financial_backend.domain.models import Expense, InsightCard
from home_financial_backend.domain.seed import DEMO_HOUSEHOLD
from home_financial_backend.infrastructure.memory_repositories import create_demo_repositories
from home_financial_backend.runtime import adapters
from home_financial_backend.runtime.adapters import CrewAIInsightGenerator
from home_financial_backend.runtime.usage import ProviderUsage, record_usage
from home_financial_backend.services.classification import ClassificationService
from home_financial_backend.services.csv_import import CSVImportService
from home_financial_backend.services.dashboard import DashboardService
from home_financial_backend.services.evaluation import EvaluationService
from home_financial_backend.services.expenses import ExpenseService
from home_financial_backend.services.insights import InsightsService, format_brl
from home_financial_backend.settings import DEFAULT_EVALUATION_DATASET_PATH

HEADER = "data,descricao,valor,forma_pagamento,estabelecimento,categoria,recorrente,observacoes\n"


@pytest.fixture
def captured_events(caplog, monkeypatch):
    monkeypatch.setattr(observability.logger, "propagate", True)
    caplog.set_level(logging.INFO, logger="home_financial")
    return caplog


def events(caplog) -> list[dict]:
    return [
        json.loads(record.getMessage())
        for record in caplog.records
        if record.name == "home_financial"
    ]


def build_import_stack():
    repositories = create_demo_repositories()
    classifier = ClassificationService(
        categories=repositories.categories,
        expenses=repositories.expenses,
        decisions=repositories.classification_decisions,
    )
    expense_service = ExpenseService(
        households=repositories.households,
        categories=repositories.categories,
        expenses=repositories.expenses,
        decisions=repositories.classification_decisions,
        classifier=classifier,
    )
    importer = CSVImportService(
        categories=repositories.categories,
        import_runs=repositories.import_runs,
        expenses=expense_service,
    )
    return repositories, importer


def test_fifty_row_import_and_dashboard_meet_latency_targets() -> None:
    repositories, importer = build_import_stack()
    rows = "".join(
        f"{(index % 28) + 1:02d}/10/2026,Compra no supermercado {index},"
        f'"{10 + index},00",debito,,,nao,\n'
        for index in range(50)
    )

    started = perf_counter()
    result = importer.import_text(DEMO_HOUSEHOLD.id, HEADER + rows)
    import_seconds = perf_counter() - started

    dashboard = DashboardService(
        repositories.households, repositories.categories, repositories.expenses
    )
    started = perf_counter()
    summary = dashboard.monthly(DEMO_HOUSEHOLD.id, "2026-10")
    dashboard_seconds = perf_counter() - started

    assert result.imported_rows == 50
    assert summary.expense_count == 50
    assert import_seconds < 5
    assert dashboard_seconds < 2


def test_golden_dataset_classification_meets_latency_target() -> None:
    repositories = create_demo_repositories()
    service = EvaluationService(
        repositories.households,
        repositories.categories,
        repositories.evaluation_runs,
        DEFAULT_EVALUATION_DATASET_PATH,
    )

    started = perf_counter()
    result = service.run(DEMO_HOUSEHOLD.id, None)
    elapsed = perf_counter() - started

    assert result.passed is True
    assert elapsed < 30


def test_insight_run_records_copilot_usage_without_inventing_a_usd_cost(
    monkeypatch, captured_events
) -> None:
    class FakeCrew:
        def kickoff(self, *, inputs):
            record_usage(ProviderUsage(1000, 200, 123.0))
            return SimpleNamespace(
                pydantic=InsightCard(
                    title="Resumo",
                    text=f"As despesas do mês somaram {format_brl(1250)}.",
                    source_refs=(inputs["source_groups"][0]["token"],),
                ),
                token_usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=200),
            )

    monkeypatch.setattr(adapters, "build_insight_crew", lambda llm: FakeCrew())
    repositories = create_demo_repositories()
    repositories.expenses.add(
        Expense(
            id="usage-expense",
            household_id=DEMO_HOUSEHOLD.id,
            date="2026-10-01",
            description="Conta de teste",
            amount_cents=1250,
            payment_method="debito",
            category_id="category-contas-da-casa",
            source="manual",
        )
    )
    service = InsightsService(
        DashboardService(repositories.households, repositories.categories, repositories.expenses),
        repositories.categories,
        repositories.expenses,
        repositories.insight_runs,
        generator=CrewAIInsightGenerator("test-llm"),
        model_name="account-supported-model",
    )

    started = perf_counter()
    run, _ = service.generate(DEMO_HOUSEHOLD.id, "2026-10")
    elapsed = perf_counter() - started

    assert run.provider_status == "used"
    assert run.provider == "copilot"
    assert run.model == "account-supported-model"
    assert run.latency_ms is not None and run.latency_ms >= 0
    assert (run.prompt_tokens, run.completion_tokens) == (1000, 200)
    assert run.estimated_cost_usd is None
    assert elapsed < 20
    logged = [event for event in events(captured_events) if event["event"] == "insight_generated"]
    assert logged[0]["fallback_used"] is False
    assert logged[0]["prompt_tokens"] == 1000
    assert logged[0]["copilot_nano_aiu"] == 123.0


def test_insight_without_provider_leaves_usage_fields_empty() -> None:
    repositories = create_demo_repositories()
    repositories.expenses.add(
        Expense(
            id="no-provider-expense",
            household_id=DEMO_HOUSEHOLD.id,
            date="2026-10-01",
            description="Conta de teste",
            amount_cents=1250,
            payment_method="debito",
            category_id="category-contas-da-casa",
            source="manual",
        )
    )
    service = InsightsService(
        DashboardService(repositories.households, repositories.categories, repositories.expenses),
        repositories.categories,
        repositories.expenses,
        repositories.insight_runs,
    )

    run, _ = service.generate(DEMO_HOUSEHOLD.id, "2026-10")

    assert run.model is None
    assert run.latency_ms is None
    assert run.estimated_cost_usd is None


def test_structured_logs_cover_import_and_classification_without_sensitive_text(
    captured_events,
) -> None:
    _, importer = build_import_stack()
    content = (
        HEADER + '01/10/2026,Segredo da Padaria Zeta,"12,00",debito,Padaria Zeta Privada,,nao,\n'
        '02/10/2026,Linha inválida,"10,00",pix,,,nao,\n'
    )

    importer.import_text(DEMO_HOUSEHOLD.id, content, "extrato-privado.csv")

    logged = events(captured_events)
    names = {event["event"] for event in logged}
    assert {"csv_import", "expense_classified"} <= names
    summary = next(event for event in logged if event["event"] == "csv_import")
    assert (summary["total_rows"], summary["imported_rows"], summary["rejected_rows"]) == (2, 1, 1)
    assert json.loads(summary["error_codes"])
    classified = next(event for event in logged if event["event"] == "expense_classified")
    assert classified["confidence_bucket"] in {"lt_0.50", "0.50_0.69", "0.70_0.89", "gte_0.90"}
    raw_output = captured_events.text
    for sensitive in ("Segredo da Padaria", "Padaria Zeta", "extrato-privado", "Linha inválida"):
        assert sensitive not in raw_output


@pytest.mark.parametrize(
    ("confidence", "bucket"),
    [(None, "none"), (0.0, "lt_0.50"), (0.69, "0.50_0.69"), (0.7, "0.70_0.89"), (0.9, "gte_0.90")],
)
def test_confidence_bucket_boundaries(confidence, bucket) -> None:
    assert observability.confidence_bucket(confidence) == bucket
