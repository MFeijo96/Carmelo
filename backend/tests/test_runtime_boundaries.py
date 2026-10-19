import json
from datetime import date
from types import SimpleNamespace

from home_financial_backend.domain.models import (
    Expense,
    InsightCard,
    InsightGroup,
    MonthlyDashboard,
    PaymentAmount,
    SafeClassificationContext,
)
from home_financial_backend.domain.seed import DEMO_HOUSEHOLD
from home_financial_backend.infrastructure.memory_repositories import create_demo_repositories
from home_financial_backend.runtime import adapters
from home_financial_backend.runtime.adapters import (
    CrewAIClassificationFallback,
    CrewAIInsightGenerator,
)
from home_financial_backend.runtime.provider import create_llm
from home_financial_backend.services.classification import ClassificationService
from home_financial_backend.services.dashboard import DashboardService
from home_financial_backend.services.evaluation import EvaluationService
from home_financial_backend.services.expenses import ExpenseService
from home_financial_backend.services.insights import InsightsService
from home_financial_backend.settings import Settings


def test_copilot_provider_builds_without_a_token_or_external_request(monkeypatch) -> None:
    monkeypatch.delenv("COPILOT_GITHUB_TOKEN", raising=False)
    settings = Settings(
        _env_file=None,
        copilot_enabled=True,
        copilot_model="account-supported-model",
    )

    llm = create_llm(settings)

    assert llm is not None
    assert llm.model == "account-supported-model"
    assert llm.supports_function_calling() is False


def test_copilot_provider_can_be_disabled() -> None:
    settings = Settings(_env_file=None, copilot_enabled=False)

    assert create_llm(settings) is None


def test_insight_adapter_receives_only_aggregate_safe_context_and_opaque_sources(
    monkeypatch,
) -> None:
    observed = {}

    class FakeCrew:
        def kickoff(self, *, inputs):
            observed.update(inputs)
            return SimpleNamespace(
                pydantic=InsightCard(
                    title="Resumo",
                    text="As despesas do mês somaram R$ 12,50.",
                    source_refs=(inputs["source_groups"][0]["token"],),
                )
            )

    monkeypatch.setattr(adapters, "build_insight_crew", lambda llm: FakeCrew())
    summary = MonthlyDashboard(
        month="2026-10",
        total_cents=1250,
        expense_count=1,
        category_breakdown=(
            {
                "category_id": "private-category-id",
                "label": "Mercado",
                "amount_cents": 1250,
                "percentage": 100,
            },
        ),
        payment_breakdown=(PaymentAmount(payment_method="credito", amount_cents=1250),),
        recurring_cents=0,
    )
    group = InsightGroup(
        token="opaque-source-token",
        category_id="private-category-id",
        category_label="Mercado",
        amount_cents=1250,
        expense_count=1,
    )

    result = CrewAIInsightGenerator("test-llm")(summary, (group,))

    serialized = json.dumps(observed, ensure_ascii=False)
    assert result.source_refs == ("opaque-source-token",)
    assert "private-category-id" not in serialized
    assert "raw merchant" not in serialized
    assert "private description" not in serialized
    assert "opaque-source-token" in serialized
    assert observed["safe_context"] == {"merchant_contexts": []}


def test_insights_reject_unsafe_or_ungrounded_generator_output_and_fallback() -> None:
    repositories = create_demo_repositories()
    repositories.expenses.add(
        Expense(
            id="private-expense-id",
            household_id=DEMO_HOUSEHOLD.id,
            date=date(2026, 10, 1),
            description="private description",
            amount_cents=1250,
            payment_method="credito",
            category_id="category-mercado",
            merchant="raw merchant",
            source="manual",
        )
    )
    dashboard = DashboardService(
        repositories.households,
        repositories.categories,
        repositories.expenses,
    )

    def unsafe_generator(summary, groups, merchants):
        return InsightCard(
            title="Sugestão",
            text="Você deve cortar gastos e pode pagar R$ 99,99.",
            source_refs=(groups[0].token,),
        )

    service = InsightsService(
        dashboard,
        repositories.categories,
        repositories.expenses,
        repositories.insight_runs,
        generator=unsafe_generator,
    )
    run, source_map = service.generate(DEMO_HOUSEHOLD.id, "2026-10")

    assert run.provider_status == "failed"
    assert run.provider_error_code == "safety_rejection"
    assert run.safety_status == "fallback"
    assert "Você deve" not in run.cards[0].text
    assert run.cards[0].source_refs[0] in source_map
    assert source_map[run.cards[0].source_refs[0]] == ("private-expense-id",)


def test_insights_reject_non_portuguese_generator_output() -> None:
    repositories = create_demo_repositories()
    repositories.expenses.add(
        Expense(
            id="english-insight-expense",
            household_id=DEMO_HOUSEHOLD.id,
            date=date(2026, 10, 1),
            description="Conta mensal",
            amount_cents=1000,
            payment_method="debito",
            category_id="category-contas-da-casa",
            source="manual",
        )
    )
    dashboard = DashboardService(
        repositories.households,
        repositories.categories,
        repositories.expenses,
    )
    service = InsightsService(
        dashboard,
        repositories.categories,
        repositories.expenses,
        repositories.insight_runs,
        generator=lambda summary, groups, merchants: InsightCard(
            title="Monthly summary",
            text="Spending was higher this month.",
            source_refs=(groups[0].token,),
        ),
    )

    run, _ = service.generate(DEMO_HOUSEHOLD.id, "2026-10")

    assert run.provider_status == "failed"
    assert run.provider_error_code == "safety_rejection"
    assert run.safety_status == "fallback"
    assert "foi registrada 1 despesa" in run.cards[0].text


def test_insight_timeout_uses_deterministic_fallback() -> None:
    repositories = create_demo_repositories()
    repositories.expenses.add(
        Expense(
            id="timeout-expense",
            household_id=DEMO_HOUSEHOLD.id,
            date=date(2026, 10, 1),
            description="Conta de teste",
            amount_cents=1250,
            payment_method="debito",
            category_id="category-contas-da-casa",
            source="manual",
        )
    )
    dashboard = DashboardService(
        repositories.households,
        repositories.categories,
        repositories.expenses,
    )

    def timed_out(summary, groups, merchants):
        raise TimeoutError("provider exceeded configured timeout")

    service = InsightsService(
        dashboard,
        repositories.categories,
        repositories.expenses,
        repositories.insight_runs,
        generator=timed_out,
    )
    run, _ = service.generate(DEMO_HOUSEHOLD.id, "2026-10")

    assert run.provider_status == "failed"
    assert run.provider_error_code == "timeout"
    assert run.safety_status == "fallback"
    assert "R$ 12,50" in run.cards[0].text


def test_manual_classification_fallback_receives_no_original_merchant_or_description() -> None:
    from home_financial_backend.api.contracts import ExpenseCreateRequest
    from home_financial_backend.runtime.contracts import ClassificationCandidate

    repositories = create_demo_repositories()
    observed = {}

    def fallback(context, categories):
        observed["context"] = context
        observed["categories"] = categories
        return ClassificationCandidate(
            category_id="category-outros",
            confidence=0.5,
            reason="Contexto insuficiente para uma sugestão firme.",
            source="llm_fallback",
            review_required=False,
        )

    classifier = ClassificationService(
        repositories.categories,
        repositories.expenses,
        repositories.classification_decisions,
        fallback_classifier=fallback,
        rules=(),
    )
    service = ExpenseService(
        repositories.households,
        repositories.categories,
        repositories.expenses,
        repositories.classification_decisions,
        classifier,
    )
    service.create_manual(
        DEMO_HOUSEHOLD.id,
        ExpenseCreateRequest(
            date=date(2026, 10, 1),
            description="Private detail 82731",
            amount_cents=1500,
            payment_method="credito",
            merchant="Private Merchant 92744",
        ),
    )

    context = observed["context"]
    assert context.merchant_alias.startswith("Estabelecimento ")
    assert context.merchant_alias != "Private Merchant 92744"
    assert "Private Merchant 92744" not in repr(context)
    assert "Private detail 82731" not in repr(context)


def test_classifier_prompt_uses_opaque_category_options_and_maps_result(monkeypatch) -> None:
    from home_financial_backend.runtime.contracts import ClassificationCandidate

    observed = {}

    class FakeCrew:
        def kickoff(self, *, inputs):
            observed.update(inputs)
            return SimpleNamespace(
                pydantic=ClassificationCandidate(
                    category_id=inputs["active_leaf_taxonomy"][0]["category_id"],
                    confidence=0.8,
                    reason="Sugestão compatível com o contexto seguro.",
                    source="llm_fallback",
                    review_required=False,
                )
            )

    monkeypatch.setattr(adapters, "build_classification_crew", lambda llm: FakeCrew())
    category = create_demo_repositories().categories.require_active_leaf(
        DEMO_HOUSEHOLD.id,
        "category-mercado",
    )
    candidate = CrewAIClassificationFallback("test-llm")(
        SafeClassificationContext(merchant_alias="Estabelecimento fictício"),
        (category,),
    )

    assert candidate.category_id == category.id
    assert observed["active_leaf_taxonomy"][0]["category_id"] != category.id
    assert category.id not in json.dumps(observed, ensure_ascii=False)


def test_insight_crew_kickoff_failure_uses_fallback_and_reports_provider_failure(
    monkeypatch,
) -> None:
    calls = []

    class FailedCrew:
        def kickoff(self, *, inputs):
            calls.append(inputs)
            raise AuthenticationError("secret API key rejected")

    class AuthenticationError(Exception):
        pass

    monkeypatch.setattr(adapters, "build_insight_crew", lambda llm: FailedCrew())
    repositories = create_demo_repositories()
    repositories.expenses.add(
        Expense(
            id="kickoff-failure-expense",
            household_id=DEMO_HOUSEHOLD.id,
            date=date(2026, 10, 1),
            description="Conta mensal",
            amount_cents=1250,
            payment_method="debito",
            category_id="category-contas-da-casa",
            source="manual",
        )
    )
    dashboard = DashboardService(
        repositories.households,
        repositories.categories,
        repositories.expenses,
    )
    service = InsightsService(
        dashboard,
        repositories.categories,
        repositories.expenses,
        repositories.insight_runs,
        generator=CrewAIInsightGenerator("test-llm"),
    )

    run, _ = service.generate(DEMO_HOUSEHOLD.id, "2026-10")

    assert calls
    assert calls[0]["monthly_summary"]["total_cents"] == 1250
    assert run.provider_status == "failed"
    assert run.provider_error_code == "authentication"
    assert run.safety_status == "fallback"
    assert "R$ 12,50" in run.cards[0].text


def test_configured_golden_dataset_evaluation_is_deterministic_and_llm_free(tmp_path) -> None:
    repositories = create_demo_repositories()
    dataset_path = tmp_path / "golden.json"
    dataset_path.write_text(
        json.dumps(
            {
                "version": "test-v1",
                "records": [
                    {
                        "date": "2026-10-01",
                        "description": "Compra no supermercado",
                        "amount_cents": 1000,
                        "payment_method": "debito",
                        "recurring": False,
                        "expected_category_id": "category-mercado",
                    },
                    {
                        "date": "2026-10-02",
                        "description": "Jantar em restaurante",
                        "amount_cents": 2500,
                        "payment_method": "credito",
                        "recurring": False,
                        "expected_category_id": "category-restaurantes",
                    },
                    {
                        "date": "2026-10-03",
                        "description": "Despesa sem regra",
                        "amount_cents": 500,
                        "payment_method": "dinheiro",
                        "recurring": False,
                        "expected_category_id": "category-outros",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    service = EvaluationService(
        repositories.households,
        repositories.categories,
        repositories.evaluation_runs,
        str(dataset_path),
    )

    result = service.run(DEMO_HOUSEHOLD.id, "test-v1")

    assert result.total_count == 3
    assert result.correct_count == 3
    assert result.accuracy == 1
    assert result.passed is True
    assert len(result.confusion_details) == 3
