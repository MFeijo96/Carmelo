import json
from datetime import date
from types import SimpleNamespace

from home_financial_backend.api.contracts import ExpenseCreateRequest
from home_financial_backend.domain.models import InsightCard
from home_financial_backend.domain.seed import DEMO_HOUSEHOLD
from home_financial_backend.infrastructure.memory_repositories import create_demo_repositories
from home_financial_backend.runtime import adapters
from home_financial_backend.runtime.adapters import CrewAIInsightGenerator
from home_financial_backend.services.categories import delete_demo_data
from home_financial_backend.services.classification import ClassificationService
from home_financial_backend.services.dashboard import DashboardService
from home_financial_backend.services.expenses import ExpenseService
from home_financial_backend.services.insights import InsightsService
from home_financial_backend.services.merchant_context import MerchantContextService

RAW_MERCHANT = "Padaria Segredo 7788"
RAW_DESCRIPTION = "Pao de queijo privado 5521"


def _services():
    repositories = create_demo_repositories()
    contexts = MerchantContextService(repositories.merchant_contexts)
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
        merchant_contexts=contexts,
    )
    return repositories, contexts, expenses


def _create(expenses: ExpenseService, day: int, *, recurring: bool = False) -> None:
    expenses.create_manual(
        DEMO_HOUSEHOLD.id,
        ExpenseCreateRequest(
            date=date(2026, 10, day),
            description=RAW_DESCRIPTION,
            amount_cents=1000 + day,
            payment_method="debito",
            category_id="category-mercado",
            recurring=recurring,
            merchant=RAW_MERCHANT,
        ),
    )


def test_alias_is_stable_per_merchant_and_records_hints_and_recurrence() -> None:
    repositories, _, expenses = _services()
    _create(expenses, 1, recurring=True)
    _create(expenses, 2, recurring=True)
    _create(expenses, 3)

    stored = repositories.merchant_contexts.list_by_household(DEMO_HOUSEHOLD.id)

    assert len(stored) == 1
    assert stored[0].original_value == RAW_MERCHANT
    assert stored[0].alias.startswith("Estabelecimento ")
    assert stored[0].category_hints == ("Mercado",)
    assert stored[0].recurring_count == 2


def test_projection_exposes_only_alias_context_hints_and_recurrence() -> None:
    repositories, contexts, expenses = _services()
    _create(expenses, 1, recurring=True)
    month_expenses = repositories.expenses.list_by_household(DEMO_HOUSEHOLD.id)

    projection = contexts.insight_projection(DEMO_HOUSEHOLD.id, month_expenses)

    assert len(projection) == 1
    dumped = json.dumps([item.model_dump(mode="json") for item in projection])
    assert RAW_MERCHANT not in dumped
    assert RAW_DESCRIPTION not in dumped
    assert projection[0].category_hints == ("Mercado",)
    assert projection[0].recurring_count == 1


def test_insight_prompt_carries_projection_but_never_raw_values(monkeypatch) -> None:
    repositories, contexts, expenses = _services()
    _create(expenses, 1, recurring=True)
    observed = {}

    class FakeCrew:
        def kickoff(self, *, inputs):
            observed.update(inputs)
            return SimpleNamespace(
                pydantic=InsightCard(
                    title="Resumo",
                    text="As despesas do mês somaram R$ 10,01.",
                    source_refs=(inputs["source_groups"][0]["token"],),
                )
            )

    monkeypatch.setattr(
        adapters,
        "build_insight_crew",
        lambda llm, *, tracing_enabled=False: FakeCrew(),
    )
    service = InsightsService(
        DashboardService(repositories.households, repositories.categories, repositories.expenses),
        repositories.categories,
        repositories.expenses,
        repositories.insight_runs,
        generator=CrewAIInsightGenerator("test-llm"),
        merchant_contexts=contexts,
    )

    run, _ = service.generate(DEMO_HOUSEHOLD.id, "2026-10")

    prompt = json.dumps(observed, ensure_ascii=False)
    assert run.provider_status == "used"
    assert observed["safe_context"]["merchant_contexts"][0]["category_hints"] == ["Mercado"]
    assert RAW_MERCHANT not in prompt
    assert RAW_DESCRIPTION not in prompt
    assert "category-mercado" not in prompt


def test_demo_data_deletion_clears_the_alias_map() -> None:
    repositories, _, expenses = _services()
    _create(expenses, 1)

    delete_demo_data(
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

    assert repositories.merchant_contexts.list_by_household(DEMO_HOUSEHOLD.id) == ()
