from datetime import date

import pytest

from home_financial_backend.domain.errors import (
    AmbiguousCategoryLabel,
    CategoryNotFound,
    HouseholdNotFound,
    ParentCategoryNotAssignable,
    UnknownCategoryLabel,
)
from home_financial_backend.domain.models import Category, Expense, Household
from home_financial_backend.infrastructure.memory_repositories import create_demo_repositories

DEMO_HOUSEHOLD_ID = "demo-household"


def make_expense(
    *,
    household_id: str = DEMO_HOUSEHOLD_ID,
    category_id: str = "category-mercado",
) -> Expense:
    return Expense(
        id="expense-1",
        household_id=household_id,
        date=date(2026, 10, 1),
        description="Mercado semanal",
        amount_cents=12345,
        payment_method="debito",
        category_id=category_id,
        source="manual",
    )


def test_demo_repositories_seed_one_household_and_standard_taxonomy() -> None:
    repositories = create_demo_repositories()

    assert repositories.households.get_demo().id == DEMO_HOUSEHOLD_ID
    seeded = repositories.categories.list_by_household(DEMO_HOUSEHOLD_ID)
    assert len(seeded) == 16
    assert repositories.expenses.list_by_household(DEMO_HOUSEHOLD_ID) == ()
    assert repositories.categories.resolve_active_leaf(DEMO_HOUSEHOLD_ID, "  MERCÁDO ").id == (
        "category-mercado"
    )


def test_parent_categories_cannot_be_resolved_or_assigned() -> None:
    repositories = create_demo_repositories()

    with pytest.raises(ParentCategoryNotAssignable):
        repositories.categories.resolve_active_leaf(DEMO_HOUSEHOLD_ID, "Alimentação")
    with pytest.raises(ParentCategoryNotAssignable):
        repositories.expenses.add(make_expense(category_id="category-alimentacao"))


def test_expense_repository_enforces_household_and_active_leaf_scope() -> None:
    repositories = create_demo_repositories()
    added = repositories.expenses.add(make_expense())

    assert repositories.expenses.get_for_household(added.id, DEMO_HOUSEHOLD_ID) == added
    assert repositories.expenses.get_for_household(added.id, "other-household") is None
    assert repositories.expenses.list_by_household(DEMO_HOUSEHOLD_ID) == (added,)

    with pytest.raises(HouseholdNotFound):
        repositories.expenses.add(make_expense(household_id="other-household"))
    with pytest.raises(CategoryNotFound):
        repositories.expenses.add(make_expense(category_id="category-does-not-exist"))
    with pytest.raises(HouseholdNotFound):
        repositories.categories.list_by_household("other-household")
    assert repositories.households.get_by_id("other-household") is None


def test_unknown_category_label_is_not_silently_resolved() -> None:
    repositories = create_demo_repositories()

    with pytest.raises(UnknownCategoryLabel):
        repositories.categories.resolve_active_leaf(
            DEMO_HOUSEHOLD_ID,
            "Mercado e restaurante",
        )


def test_duplicate_category_labels_are_reported_as_ambiguous() -> None:
    repositories = create_demo_repositories()
    duplicate = Category(
        id="category-mercado-duplicate",
        household_id=DEMO_HOUSEHOLD_ID,
        canonical_key="mercado-duplicate",
        label="MERCADO",
        parent_category_id="category-alimentacao",
    )
    from home_financial_backend.infrastructure.memory_repositories import (
        InMemoryCategoryRepository,
    )

    duplicate_labels = InMemoryCategoryRepository(
        (*repositories.categories.list_by_household(DEMO_HOUSEHOLD_ID), duplicate),
        repositories.households,
    )
    with pytest.raises(AmbiguousCategoryLabel):
        duplicate_labels.resolve_active_leaf(DEMO_HOUSEHOLD_ID, "mercado")


def test_household_repository_requires_exactly_one_demo_household() -> None:
    from home_financial_backend.infrastructure.memory_repositories import (
        InMemoryHouseholdRepository,
    )

    household = Household(id="one", name="One", is_demo=True)
    another_demo = Household(id="two", name="Two", is_demo=True)

    with pytest.raises(ValueError, match="Exactly one demo household"):
        InMemoryHouseholdRepository((household, another_demo))
