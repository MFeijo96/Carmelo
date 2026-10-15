import csv
from datetime import UTC, date, datetime
from io import StringIO
from typing import Any

from home_financial_backend.domain.errors import HouseholdNotFound
from home_financial_backend.domain.repositories import (
    CategoryRepository,
    ClassificationDecisionRepository,
    EvaluationRunRepository,
    ExpenseRepository,
    HouseholdRepository,
    ImportRunRepository,
    InsightRunRepository,
)


class ExportService:
    def __init__(
        self,
        households: HouseholdRepository,
        categories: CategoryRepository,
        expenses: ExpenseRepository,
        imports: ImportRunRepository,
        decisions: ClassificationDecisionRepository,
        insights: InsightRunRepository,
        evaluations: EvaluationRunRepository,
    ) -> None:
        self._households = households
        self._categories = categories
        self._expenses = expenses
        self._imports = imports
        self._decisions = decisions
        self._insights = insights
        self._evaluations = evaluations

    def csv_expenses(
        self,
        household_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> tuple[str, datetime]:
        self._require_demo(household_id)
        if start_date and end_date and start_date > end_date:
            raise ValueError("start_date must be on or before end_date")
        category_labels = {
            category.id: category.label
            for category in self._categories.list_by_household(household_id)
        }
        expenses = [
            expense
            for expense in self._expenses.list_by_household(household_id)
            if (start_date is None or expense.date >= start_date)
            and (end_date is None or expense.date <= end_date)
        ]
        output = StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(
            (
                "data",
                "descricao",
                "valor",
                "forma_pagamento",
                "estabelecimento",
                "categoria",
                "recorrente",
                "observacoes",
            )
        )
        for expense in expenses:
            amount = f"{expense.amount_cents // 100},{expense.amount_cents % 100:02d}"
            writer.writerow(
                (
                    expense.date.strftime("%d/%m/%Y"),
                    expense.description,
                    amount,
                    expense.payment_method,
                    expense.merchant or "",
                    category_labels.get(expense.category_id, ""),
                    "sim" if expense.recurring else "nao",
                    expense.notes or "",
                )
            )
        return output.getvalue(), datetime.now(UTC)

    def archive(
        self,
        household_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        household = self._require_demo(household_id)
        if start_date and end_date and start_date > end_date:
            raise ValueError("start_date must be on or before end_date")
        expenses = [
            expense
            for expense in self._expenses.list_by_household(household_id)
            if (start_date is None or expense.date >= start_date)
            and (end_date is None or expense.date <= end_date)
        ]
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "household_id": household.id,
            "date_range": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
            },
            "schema_version": "1.0",
            "expenses": [item.model_dump(mode="json") for item in expenses],
            "categories": [
                item.model_dump(mode="json")
                for item in self._categories.list_by_household(household_id)
            ],
            "imports": [
                item.model_dump(mode="json")
                for item in self._imports.list_by_household(household_id)
            ],
            "classification_decisions": [
                item.model_dump(mode="json")
                for item in self._decisions.list_by_household(household_id)
            ],
            "insights": [
                item.model_dump(mode="json")
                for item in self._insights.list_by_household(household_id)
            ],
            "evaluations": [
                item.model_dump(mode="json")
                for item in self._evaluations.list_by_household(household_id)
            ],
        }

    def _require_demo(self, household_id: str):
        household = self._households.get_by_id(household_id)
        if household is None or not household.is_demo:
            raise HouseholdNotFound("Demo household not found")
        return household
