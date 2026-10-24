import json
from pathlib import Path

import pytest

from home_financial_backend.domain.errors import EvaluationUnavailable
from home_financial_backend.domain.seed import DEMO_HOUSEHOLD
from home_financial_backend.infrastructure.memory_repositories import create_demo_repositories
from home_financial_backend.services.classification import ClassificationService
from home_financial_backend.services.evaluation import EvaluationService


def test_golden_dataset_meets_deterministic_acceptance_without_llm(monkeypatch) -> None:
    repositories = create_demo_repositories()
    dataset_path = Path(__file__).parents[1] / "data" / "golden-expenses.json"
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    fallback_states = []
    original_fallback = ClassificationService._llm_fallback

    def track_fallback(self, item, household_categories):
        fallback_states.append(self._fallback_classifier)
        return original_fallback(self, item, household_categories)

    monkeypatch.setattr(ClassificationService, "_llm_fallback", track_fallback)
    service = EvaluationService(
        households=repositories.households,
        categories=repositories.categories,
        evaluations=repositories.evaluation_runs,
        dataset_path=str(dataset_path),
    )

    result = service.run(DEMO_HOUSEHOLD.id, dataset["version"])

    assert 30 <= result.total_count <= 50
    assert result.total_count == len(dataset["records"])
    assert result.total_count == 50
    assert result.accuracy == result.correct_count / result.total_count
    assert result.passed is (result.accuracy >= 0.70)
    assert result.passed is True
    assert result.total_count == sum(item.count for item in result.confusion_details)
    assert fallback_states
    assert all(fallback is None for fallback in fallback_states)
    assert {record["payment_method"] for record in dataset["records"]} == {
        "dinheiro",
        "debito",
        "credito",
    }
    assert {record["recurring"] for record in dataset["records"]} == {True, False}


@pytest.mark.parametrize(
    ("incorrect_count", "expected_accuracy", "expected_pass"),
    [(3, 0.70, True), (4, 0.60, False)],
)
def test_evaluation_enforces_threshold_at_and_below_boundary(
    tmp_path,
    incorrect_count,
    expected_accuracy,
    expected_pass,
) -> None:
    repositories = create_demo_repositories()
    dataset_path = tmp_path / "golden.json"
    dataset_path.write_text(
        json.dumps(
            {
                "version": "threshold-v1",
                "records": [
                    {
                        "date": f"2026-10-{index + 1:02d}",
                        "description": "Compra no supermercado",
                        "amount_cents": 1000 + index,
                        "payment_method": "debito",
                        "recurring": False,
                        "expected_category_id": (
                            "category-restaurantes"
                            if index >= 10 - incorrect_count
                            else "category-mercado"
                        ),
                    }
                    for index in range(10)
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

    result = service.run(DEMO_HOUSEHOLD.id)

    assert result.accuracy == expected_accuracy
    assert result.passed is expected_pass


def test_evaluation_report_is_repeatable_except_for_run_metadata(tmp_path) -> None:
    repositories = create_demo_repositories()
    dataset_path = Path(__file__).parents[1] / "data" / "golden-expenses.json"
    service = EvaluationService(
        repositories.households,
        repositories.categories,
        repositories.evaluation_runs,
        str(dataset_path),
    )

    first = service.run(DEMO_HOUSEHOLD.id)
    second = service.run(DEMO_HOUSEHOLD.id)

    assert first.id != second.id
    assert first.model_dump(exclude={"id", "created_at"}) == second.model_dump(
        exclude={"id", "created_at"}
    )


@pytest.mark.parametrize("category_id", ["category-does-not-exist", "category-lazer"])
def test_evaluation_rejects_invalid_expected_category_without_saving_result(
    tmp_path,
    category_id,
) -> None:
    repositories = create_demo_repositories()
    dataset_path = tmp_path / "golden.json"
    dataset_path.write_text(
        json.dumps(
            {
                "version": "invalid-category-v1",
                "records": [
                    {
                        "date": "2026-10-01",
                        "description": "Compra de teste",
                        "amount_cents": 1000,
                        "payment_method": "debito",
                        "recurring": False,
                        "expected_category_id": category_id,
                    }
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

    with pytest.raises(EvaluationUnavailable, match="invalid expected category"):
        service.run(DEMO_HOUSEHOLD.id)

    assert repositories.evaluation_runs.list_by_household(DEMO_HOUSEHOLD.id) == ()


def test_evaluation_rejects_unavailable_dataset_version(tmp_path) -> None:
    repositories = create_demo_repositories()
    dataset_path = tmp_path / "golden.json"
    dataset_path.write_text(
        json.dumps(
            {
                "version": "v1",
                "records": [
                    {
                        "date": "2026-10-01",
                        "description": "Compra no supermercado",
                        "amount_cents": 1000,
                        "payment_method": "debito",
                        "recurring": False,
                        "expected_category_id": "category-mercado",
                    }
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

    with pytest.raises(EvaluationUnavailable, match="version is not available"):
        service.run(DEMO_HOUSEHOLD.id, "v2")
