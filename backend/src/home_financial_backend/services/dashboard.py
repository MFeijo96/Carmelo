from collections import Counter, defaultdict
from datetime import date

from home_financial_backend.domain.errors import HouseholdNotFound
from home_financial_backend.domain.models import (
    CategoryAmount,
    MonthlyDashboard,
    PaymentAmount,
    PaymentMethod,
)
from home_financial_backend.domain.repositories import (
    CategoryRepository,
    ExpenseRepository,
    HouseholdRepository,
)


class DashboardService:
    def __init__(
        self,
        households: HouseholdRepository,
        categories: CategoryRepository,
        expenses: ExpenseRepository,
    ) -> None:
        self._households = households
        self._categories = categories
        self._expenses = expenses

    def monthly(self, household_id: str, month: str) -> MonthlyDashboard:
        if self._households.get_by_id(household_id) is None:
            raise HouseholdNotFound("Household not found")
        selected = date.fromisoformat(f"{month}-01")
        previous = (
            date(selected.year - 1, 12, 1)
            if selected.month == 1
            else date(
                selected.year,
                selected.month - 1,
                1,
            )
        )
        all_expenses = self._expenses.list_by_household(household_id)
        month_expenses = [
            expense
            for expense in all_expenses
            if expense.date.year == selected.year and expense.date.month == selected.month
        ]
        previous_expenses = [
            expense
            for expense in all_expenses
            if expense.date.year == previous.year and expense.date.month == previous.month
        ]
        total = sum(expense.amount_cents for expense in month_expenses)
        previous_total = sum(expense.amount_cents for expense in previous_expenses)
        categories: dict[str, int] = defaultdict(int)
        category_labels = {
            category.id: category.label
            for category in self._categories.list_by_household(household_id)
        }
        payments: Counter[PaymentMethod] = Counter()
        for expense in month_expenses:
            categories[expense.category_id] += expense.amount_cents
            payments[expense.payment_method] += expense.amount_cents
        category_breakdown = tuple(
            CategoryAmount(
                category_id=category_id,
                label=category_labels.get(category_id, "Outros"),
                amount_cents=amount,
                percentage=round(amount * 100 / total, 2) if total else 0,
            )
            for category_id, amount in sorted(categories.items())
        )
        payment_breakdown = tuple(
            PaymentAmount(payment_method=method, amount_cents=amount)
            for method, amount in sorted(payments.items())
        )
        change = total - previous_total if previous_expenses else None
        change_percentage = (
            round(change * 100 / previous_total, 2)
            if change is not None and previous_total
            else None
        )
        return MonthlyDashboard(
            month=month,
            total_cents=total,
            expense_count=len(month_expenses),
            category_breakdown=category_breakdown,
            payment_breakdown=payment_breakdown,
            recurring_cents=sum(
                expense.amount_cents for expense in month_expenses if expense.recurring
            ),
            previous_month_total_cents=previous_total if previous_expenses else None,
            change_cents=change,
            change_percentage=change_percentage,
        )
