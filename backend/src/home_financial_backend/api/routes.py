from datetime import date
from time import perf_counter
from typing import Literal

from fastapi import APIRouter, Query, Request, Response, status

from home_financial_backend.api.contracts import (
    ArchiveResultData,
    CategoryCorrectionRequest,
    CategoryCreateRequest,
    CategoryListData,
    CategoryMergeRequest,
    CategoryRenameRequest,
    CategoryResultData,
    DashboardResultData,
    DeletionResultData,
    EvaluationRequest,
    EvaluationResultData,
    ExpenseCreateRequest,
    ExpenseListData,
    ExpenseResultData,
    HealthData,
    HouseholdData,
    ImportResultData,
    InsightResultData,
    InsightSourceExpense,
    MonthlyInsightsRequest,
)
from home_financial_backend.api.models import ApiEnvelope, ApiMeta
from home_financial_backend.domain.errors import CSVStructureError
from home_financial_backend.observability import log_event
from home_financial_backend.services.categories import delete_demo_data

router = APIRouter()
MAX_CSV_BYTES = 2_000_000


def _envelope(request: Request, data):
    return ApiEnvelope(data=data, errors=[], meta=ApiMeta(request_id=request.state.request_id))


@router.get("/health", response_model=ApiEnvelope[HealthData])
def health(request: Request) -> ApiEnvelope[HealthData]:
    return _envelope(
        request,
        HealthData(
            status="ok",
            provider_configured=request.app.state.llm is not None,
            persistence_mode=request.app.state.settings.persistence_mode,
        ),
    )


@router.get("/households/demo", response_model=ApiEnvelope[HouseholdData])
def get_demo_household(request: Request) -> ApiEnvelope[HouseholdData]:
    household = request.app.state.repositories.households.get_demo()
    return _envelope(request, HouseholdData(household=household))


@router.post(
    "/imports/csv",
    response_model=ApiEnvelope[ImportResultData],
    status_code=status.HTTP_201_CREATED,
)
async def import_csv(
    request: Request,
    source_name: str | None = Query(default=None, max_length=255),
) -> ApiEnvelope[ImportResultData]:
    content_type = request.headers.get("content-type", "").split(";", maxsplit=1)[0].strip()
    if content_type not in {"text/csv", "text/plain"}:
        raise CSVStructureError("Envie o arquivo como text/csv ou text/plain.")
    payload = await request.body()
    if len(payload) > MAX_CSV_BYTES:
        raise CSVStructureError("O arquivo CSV excede o limite de 2 MB.")
    try:
        content = payload.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise CSVStructureError("O arquivo CSV deve estar codificado em UTF-8.") from error
    household_id = request.app.state.repositories.households.get_demo().id
    result = request.app.state.csv_import_service.import_text(
        household_id,
        content,
        source_name,
    )
    return _envelope(request, ImportResultData(import_run=result))


@router.post(
    "/expenses",
    response_model=ApiEnvelope[ExpenseResultData],
    status_code=status.HTTP_201_CREATED,
)
def create_expense(
    body: ExpenseCreateRequest,
    request: Request,
) -> ApiEnvelope[ExpenseResultData]:
    household_id = request.app.state.repositories.households.get_demo().id
    expense = request.app.state.expense_service.create_manual(household_id, body)
    return _envelope(request, ExpenseResultData(expense=expense))


@router.get("/expenses", response_model=ApiEnvelope[ExpenseListData])
def list_expenses(
    request: Request,
    month: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    category_id: str | None = None,
    confidence_min: float | None = Query(default=None, ge=0, le=1),
    payment_method: Literal["dinheiro", "debito", "credito"] | None = None,
    source: Literal["manual", "csv"] | None = None,
    review_required: bool | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> ApiEnvelope[ExpenseListData]:
    household_id = request.app.state.repositories.households.get_demo().id
    expenses = request.app.state.repositories.expenses.list_by_household(household_id)
    filtered = tuple(
        expense
        for expense in expenses
        if (month is None or expense.date.strftime("%Y-%m") == month)
        and (category_id is None or expense.category_id == category_id)
        and (confidence_min is None or (expense.confidence or 0) >= confidence_min)
        and (payment_method is None or expense.payment_method == payment_method)
        and (source is None or expense.source == source)
        and (review_required is None or expense.review_required is review_required)
    )
    page = filtered[offset : offset + limit]
    return _envelope(request, ExpenseListData(expenses=page, total_count=len(filtered)))


@router.patch(
    "/expenses/{expense_id}/category",
    response_model=ApiEnvelope[ExpenseResultData],
)
def correct_expense_category(
    expense_id: str,
    body: CategoryCorrectionRequest,
    request: Request,
) -> ApiEnvelope[ExpenseResultData]:
    household_id = request.app.state.repositories.households.get_demo().id
    expense = request.app.state.expense_service.correct_category(
        household_id,
        expense_id,
        body.category_id,
    )
    return _envelope(request, ExpenseResultData(expense=expense))


@router.get("/categories", response_model=ApiEnvelope[CategoryListData])
def list_categories(request: Request) -> ApiEnvelope[CategoryListData]:
    household_id = request.app.state.repositories.households.get_demo().id
    categories = request.app.state.category_service.list(household_id)
    return _envelope(request, CategoryListData(categories=categories))


@router.post(
    "/categories",
    response_model=ApiEnvelope[CategoryResultData],
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    body: CategoryCreateRequest,
    request: Request,
) -> ApiEnvelope[CategoryResultData]:
    household_id = request.app.state.repositories.households.get_demo().id
    category = request.app.state.category_service.create(
        household_id,
        body.label,
        body.parent_category_id,
    )
    return _envelope(request, CategoryResultData(category=category))


@router.patch(
    "/categories/{category_id}",
    response_model=ApiEnvelope[CategoryResultData],
)
def rename_category(
    category_id: str,
    body: CategoryRenameRequest,
    request: Request,
) -> ApiEnvelope[CategoryResultData]:
    household_id = request.app.state.repositories.households.get_demo().id
    category = request.app.state.category_service.rename(
        household_id,
        category_id,
        body.label,
    )
    return _envelope(request, CategoryResultData(category=category))


@router.post(
    "/categories/merge",
    response_model=ApiEnvelope[CategoryResultData],
)
def merge_categories(
    body: CategoryMergeRequest,
    request: Request,
) -> ApiEnvelope[CategoryResultData]:
    household_id = request.app.state.repositories.households.get_demo().id
    category = request.app.state.category_service.merge(
        household_id,
        body.source_category_id,
        body.target_category_id,
    )
    return _envelope(request, CategoryResultData(category=category))


@router.get("/dashboard/monthly", response_model=ApiEnvelope[DashboardResultData])
def monthly_dashboard(
    request: Request,
    month: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
) -> ApiEnvelope[DashboardResultData]:
    household_id = request.app.state.repositories.households.get_demo().id
    started = perf_counter()
    dashboard = request.app.state.dashboard_service.monthly(household_id, month)
    log_event(
        "dashboard_aggregated",
        expense_count=dashboard.expense_count,
        latency_ms=round((perf_counter() - started) * 1000),
    )
    return _envelope(request, DashboardResultData(dashboard=dashboard))


@router.post("/insights/monthly", response_model=ApiEnvelope[InsightResultData])
def monthly_insights(
    body: MonthlyInsightsRequest,
    request: Request,
) -> ApiEnvelope[InsightResultData]:
    household_id = request.app.state.repositories.households.get_demo().id
    insight_run, source_map = request.app.state.insight_service.generate(
        household_id,
        body.month,
    )
    expense_repository = request.app.state.repositories.expenses
    category_repository = request.app.state.repositories.categories
    category_labels = {
        category.id: category.label
        for category in category_repository.list_by_household(household_id)
    }
    sources = {
        token: tuple(
            InsightSourceExpense(
                expense_id=expense.id,
                category_label=category_labels.get(expense.category_id, "Outros"),
                date=expense.date,
                amount_cents=expense.amount_cents,
            )
            for expense_id in expense_ids
            if (expense := expense_repository.get_for_household(expense_id, household_id))
        )
        for token, expense_ids in source_map.items()
    }
    return _envelope(
        request,
        InsightResultData(insight_run=insight_run, sources=sources),
    )


@router.get("/exports/expenses.csv")
def export_csv(
    request: Request,
    start_date: date | None = None,
    end_date: date | None = None,
) -> Response:
    household_id = request.app.state.repositories.households.get_demo().id
    content, generated_at = request.app.state.export_service.csv_expenses(
        household_id,
        start_date,
        end_date,
    )
    log_event("export", kind="csv")
    date_range = f"{start_date or ''}:{end_date or ''}"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="home-financial-expenses.csv"',
            "X-Generated-At": generated_at.isoformat(),
            "X-Household-Id": household_id,
            "X-Date-Range": date_range,
            "X-Schema-Version": "1.0",
        },
    )


@router.get("/exports/archive.json", response_model=ApiEnvelope[ArchiveResultData])
def export_archive(
    request: Request,
    start_date: date | None = None,
    end_date: date | None = None,
) -> ApiEnvelope[ArchiveResultData]:
    household_id = request.app.state.repositories.households.get_demo().id
    archive = request.app.state.export_service.archive(household_id, start_date, end_date)
    log_event("export", kind="json")
    return _envelope(request, ArchiveResultData(archive=archive))


@router.delete(
    "/households/{household_id}/demo-data",
    response_model=ApiEnvelope[DeletionResultData],
)
def delete_household_data(
    household_id: str,
    request: Request,
) -> ApiEnvelope[DeletionResultData]:
    repositories = request.app.state.repositories
    deleted_count = delete_demo_data(
        household_id,
        households=repositories.households,
        categories=repositories.categories,
        expenses=repositories.expenses,
        decisions=repositories.classification_decisions,
        import_runs=repositories.import_runs,
        insight_runs=repositories.insight_runs,
        evaluation_runs=repositories.evaluation_runs,
        merchant_contexts=repositories.merchant_contexts,
    )
    log_event("demo_data_deleted", deleted_expense_count=deleted_count)
    return _envelope(
        request,
        DeletionResultData(household_id=household_id, deleted_expense_count=deleted_count),
    )


@router.post("/evaluation/categorization", response_model=ApiEnvelope[EvaluationResultData])
def evaluate_categorization(
    body: EvaluationRequest,
    request: Request,
) -> ApiEnvelope[EvaluationResultData]:
    household_id = request.app.state.repositories.households.get_demo().id
    started = perf_counter()
    evaluation = request.app.state.evaluation_service.run(household_id, body.dataset_version)
    log_event(
        "evaluation_run",
        correct_count=evaluation.correct_count,
        total_count=evaluation.total_count,
        accuracy=evaluation.accuracy,
        passed=evaluation.passed,
        duration_ms=round((perf_counter() - started) * 1000),
    )
    return _envelope(request, EvaluationResultData(evaluation=evaluation))
