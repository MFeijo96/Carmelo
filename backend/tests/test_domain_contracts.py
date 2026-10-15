import pytest
from pydantic import ValidationError

from home_financial_backend.api.contracts import ExpenseCreateRequest
from home_financial_backend.domain.models import EvaluationRun, Expense, ImportRun


def test_expense_contract_uses_positive_integer_brl_cents() -> None:
    request = ExpenseCreateRequest.model_validate(
        {
            "date": "2026-10-01",
            "description": "  Mercado  ",
            "amount_cents": 12345,
            "payment_method": "credito",
            "recurring": True,
        }
    )

    assert request.amount_cents == 12345
    assert request.description == "Mercado"
    assert request.payment_method == "credito"
    assert request.recurring is True
    with pytest.raises(ValidationError):
        ExpenseCreateRequest.model_validate(
            {
                "date": "2026-10-01",
                "description": "Mercado",
                "amount_cents": 12.34,
                "payment_method": "credito",
            }
        )
    with pytest.raises(ValidationError):
        ExpenseCreateRequest.model_validate(
            {
                "date": "2026-10-01",
                "description": "   ",
                "amount_cents": 123,
                "payment_method": "credito",
            }
        )


def test_expense_domain_rejects_invalid_payment_and_blank_description() -> None:
    with pytest.raises(ValidationError):
        Expense(
            id="expense-1",
            household_id="demo-household",
            date="2026-10-01",
            description="  ",
            amount_cents=100,
            payment_method="pix",
            category_id="category-outros",
            source="manual",
        )


def test_import_counts_and_evaluation_metrics_are_consistent() -> None:
    with pytest.raises(ValidationError):
        ImportRun(
            id="import-1",
            household_id="demo-household",
            total_rows=3,
            imported_rows=2,
            rejected_rows=0,
            status="completed",
        )

    with pytest.raises(ValidationError):
        EvaluationRun(
            id="evaluation-1",
            household_id="demo-household",
            dataset_version="v1",
            taxonomy_version="v1",
            total_count=10,
            correct_count=7,
            accuracy=0.6,
            confusion_details=(),
            passed=True,
        )
