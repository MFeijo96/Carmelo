from home_financial_backend.domain.models import Category, Household

DEMO_HOUSEHOLD = Household(
    id="demo-household",
    name="Casa de demonstração",
    is_demo=True,
)


def build_demo_categories() -> tuple[Category, ...]:
    household_id = DEMO_HOUSEHOLD.id
    definitions = (
        ("moradia", "Moradia"),
        ("alimentacao", "Alimentação"),
        ("transporte", "Transporte"),
        ("saude", "Saúde"),
        ("educacao", "Educação"),
        ("contas-da-casa", "Contas da casa"),
        ("lazer", "Lazer"),
        ("dividas", "Dívidas"),
        ("pets", "Pets"),
        ("cuidados-pessoais", "Cuidados pessoais"),
        ("entretenimento", "Entretenimento"),
        ("mercado", "Mercado"),
        ("restaurantes", "Restaurantes"),
        ("assinaturas", "Assinaturas"),
        ("outros", "Outros"),
    )
    return tuple(
        Category(
            id=f"category-{key}",
            household_id=household_id,
            canonical_key=key,
            label=label,
        )
        for key, label in definitions
    )
