from home_financial_backend.domain.models import InsightCard
from home_financial_backend.runtime.contracts import ClassificationCandidate
from home_financial_backend.runtime.crew import (
    build_classification_crew,
    build_insight_crew,
)


def test_crews_are_single_task_typed_and_construct_without_provider_calls() -> None:
    classification_crew = build_classification_crew("placeholder-llm")
    insight_crew = build_insight_crew("placeholder-llm")

    assert len(classification_crew.tasks) == 1
    assert classification_crew.tasks[0].output_pydantic is ClassificationCandidate
    assert len(insight_crew.tasks) == 1
    assert insight_crew.tasks[0].output_pydantic is InsightCard
