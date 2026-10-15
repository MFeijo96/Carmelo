from home_financial_backend.domain.models import Category, Household

DEMO_HOUSEHOLD = Household(
    id="demo-household",
    name="Casa de demonstração",
    is_demo=True,
)


def build_demo_categories() -> tuple[Category, ...]:
    household_id = DEMO_HOUSEHOLD.id
    definitions = (
        ("moradia", "Moradia", None),
        ("alimentacao", "Alimentação", None),
        ("transporte", "Transporte", None),
        ("saude", "Saúde", None),
        ("educacao", "Educação", None),
        ("contas-da-casa", "Contas da casa", None),
        ("lazer", "Lazer", None),
        ("dividas", "Dívidas", None),
        ("pets", "Pets", None),
        ("impostos-taxas", "Impostos/taxas", None),
        ("cuidados-pessoais", "Cuidados pessoais", None),
        ("outros", "Outros", None),
        ("mercado", "Mercado", "alimentacao"),
        ("restaurantes", "Restaurantes", "alimentacao"),
        ("assinaturas", "Assinaturas", "lazer"),
    )
    return tuple(
        Category(
            id=f"category-{key}",
            household_id=household_id,
            canonical_key=key,
            label=label,
            parent_category_id=f"category-{parent}" if parent else None,
        )
        for key, label, parent in definitions
    )
