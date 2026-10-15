import json
from pathlib import Path

from home_financial_backend.domain.seed import DEMO_HOUSEHOLD
from home_financial_backend.infrastructure.memory_repositories import create_demo_repositories
from home_financial_backend.services.evaluation import EvaluationService


def test_golden_dataset_meets_deterministic_acceptance_without_llm() -> None:
    repositories = create_demo_repositories()
    dataset_path = Path(__file__).parents[1] / "data" / "golden-expenses.json"
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    service = EvaluationService(
        households=repositories.households,
        categories=repositories.categories,
        evaluations=repositories.evaluation_runs,
        dataset_path=str(dataset_path),
    )

    result = service.run(DEMO_HOUSEHOLD.id, dataset["version"])

    assert 30 <= result.total_count <= 50
    assert result.total_count == len(dataset["records"])
    assert result.accuracy == result.correct_count / result.total_count
    assert result.passed is (result.accuracy >= 0.70)
    assert result.passed is True
    assert result.total_count == sum(item.count for item in result.confusion_details)
