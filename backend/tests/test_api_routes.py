from fastapi.testclient import TestClient

from home_financial_backend.main import app

client = TestClient(app)
DEMO_HOUSEHOLD_ID = "demo-household"


def test_rest_workflow_routes_share_one_demo_household_and_envelope() -> None:
    household_response = client.get("/households/demo")
    assert household_response.status_code == 200
    assert household_response.json()["data"]["household"]["id"] == DEMO_HOUSEHOLD_ID

    created = client.post(
        "/expenses",
        json={
            "date": "2026-10-12",
            "description": "Compra de teste",
            "amount_cents": 12550,
            "payment_method": "credito",
            "category_id": "category-mercado",
            "recurring": True,
        },
    )
    assert created.status_code == 201
    expense = created.json()["data"]["expense"]
    expense_id = expense["id"]

    listing = client.get("/expenses?month=2026-10&payment_method=credito")
    assert listing.status_code == 200
    assert listing.json()["data"]["total_count"] == 1

    dashboard = client.get("/dashboard/monthly?month=2026-10")
    dashboard_data = dashboard.json()["data"]["dashboard"]
    assert dashboard_data["total_cents"] == 12550
    assert dashboard_data["recurring_cents"] == 12550
    assert dashboard_data["category_breakdown"][0]["label"] == "Mercado"

    insight_response = client.post("/insights/monthly", json={"month": "2026-10"})
    insight_data = insight_response.json()["data"]
    assert insight_response.status_code == 200
    assert insight_data["insight_run"]["provider_status"] == "not_configured"
    insight_card = insight_data["insight_run"]["cards"][0]
    assert insight_card["source_refs"]
    assert set(insight_card["source_refs"]).issubset(insight_data["sources"])

    csv_export = client.get("/exports/expenses.csv")
    assert csv_export.status_code == 200
    assert "text/csv" in csv_export.headers["content-type"]
    assert csv_export.headers["X-Household-Id"] == DEMO_HOUSEHOLD_ID
    assert '12/10/2026,Compra de teste,"125,50",credito' in csv_export.text

    archive = client.get("/exports/archive.json")
    assert archive.status_code == 200
    assert len(archive.json()["data"]["archive"]["expenses"]) == 1

    categories = client.get("/categories")
    assert categories.status_code == 200
    created_category = client.post(
        "/categories",
        json={"label": "Refeições fora", "parent_category_id": "category-alimentacao"},
    )
    assert created_category.status_code == 201
    custom_id = created_category.json()["data"]["category"]["id"]
    renamed = client.patch(
        f"/categories/{custom_id}",
        json={"label": "Refeições e lanches"},
    )
    assert renamed.status_code == 200

    custom_expense = client.post(
        "/expenses",
        json={
            "date": "2026-10-13",
            "description": "Refeição fora",
            "amount_cents": 2200,
            "payment_method": "dinheiro",
            "category_id": custom_id,
        },
    )
    assert custom_expense.status_code == 201
    merged = client.post(
        "/categories/merge",
        json={
            "source_category_id": custom_id,
            "target_category_id": "category-restaurantes",
        },
    )
    assert merged.status_code == 200
    assert client.get("/expenses?month=2026-10").json()["data"]["total_count"] == 2
    corrected = client.patch(
        f"/expenses/{expense_id}/category",
        json={"category_id": "category-restaurantes"},
    )
    assert corrected.json()["data"]["expense"]["user_override"] is True
    assert client.get(f"/expenses?category_id={custom_id}").json()["data"]["total_count"] == 0
    assert client.get("/expenses?month=2026-10").status_code == 200

    imported = client.post(
        "/imports/csv?source_name=demo.csv",
        content=('data,descricao,valor,forma_pagamento\n14/10/2026,Conta de luz,"89,90",debito\n'),
        headers={"Content-Type": "text/csv"},
    )
    assert imported.status_code == 201
    assert imported.json()["data"]["import_run"]["imported_rows"] == 1

    deleted = client.delete(f"/households/{DEMO_HOUSEHOLD_ID}/demo-data")
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted_expense_count"] == 3
    assert client.get("/households/demo").status_code == 200
    assert client.get("/expenses").json()["data"]["total_count"] == 0


def test_request_validation_returns_shared_pt_br_error_envelope() -> None:
    response = client.post("/expenses", json={"amount_cents": -2})

    assert response.status_code == 422
    body = response.json()
    assert body["data"] is None
    assert body["errors"][0]["code"] == "invalid_request"
    assert body["errors"][0]["message"] == "Os dados enviados são inválidos."
    assert body["meta"]["request_id"] == response.headers["X-Request-ID"]


def test_evaluation_route_runs_the_deterministic_golden_dataset() -> None:
    response = client.post("/evaluation/categorization", json={})

    assert response.status_code == 200
    result = response.json()["data"]["evaluation"]
    assert result["total_count"] == 30
    assert result["correct_count"] >= 21
    assert result["accuracy"] >= 0.70
    assert result["passed"] is True
