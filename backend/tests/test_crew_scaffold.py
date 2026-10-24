from home_financial_backend.domain.models import InsightCard
from home_financial_backend.runtime.contracts import ClassificationCandidate
from home_financial_backend.runtime.crew import (
    build_classification_crew,
    build_insight_crew,
)
from home_financial_backend.settings import Settings


def test_crews_are_single_task_typed_and_construct_without_provider_calls() -> None:
    classification_crew = build_classification_crew("placeholder-llm")
    insight_crew = build_insight_crew("placeholder-llm")

    assert len(classification_crew.tasks) == 1
    assert classification_crew.tasks[0].output_pydantic is ClassificationCandidate
    assert len(insight_crew.tasks) == 1
    assert insight_crew.tasks[0].output_pydantic is InsightCard
    assert classification_crew.tracing is False
    assert insight_crew.tracing is False


def test_amp_tracing_is_opt_in_and_applied_to_both_crews(monkeypatch) -> None:
    monkeypatch.delenv("CREWAI_TRACING_ENABLED", raising=False)
    assert Settings(_env_file=None).crewai_tracing_enabled is False
    assert Settings(_env_file=None, crewai_tracing_enabled=True).crewai_tracing_enabled is True

    classification_crew = build_classification_crew(
        "placeholder-llm",
        tracing_enabled=True,
    )
    insight_crew = build_insight_crew("placeholder-llm", tracing_enabled=True)

    assert classification_crew.tracing is True
    assert insight_crew.tracing is True
