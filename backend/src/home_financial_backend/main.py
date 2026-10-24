from pathlib import Path
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from home_financial_backend.api.errors import (
    domain_error_handler,
    request_validation_error_handler,
)
from home_financial_backend.api.routes import router
from home_financial_backend.domain.errors import DomainError
from home_financial_backend.infrastructure.bootstrap import create_repositories
from home_financial_backend.observability import configure_logging
from home_financial_backend.runtime.adapters import (
    CrewAIClassificationFallback,
    CrewAIInsightGenerator,
)
from home_financial_backend.runtime.provider import create_llm
from home_financial_backend.services.categories import CategoryService
from home_financial_backend.services.classification import ClassificationService
from home_financial_backend.services.csv_import import CSVImportService
from home_financial_backend.services.dashboard import DashboardService
from home_financial_backend.services.evaluation import EvaluationService
from home_financial_backend.services.expenses import ExpenseService
from home_financial_backend.services.exports import ExportService
from home_financial_backend.services.insights import InsightsService
from home_financial_backend.services.merchant_context import MerchantContextService
from home_financial_backend.settings import settings

configure_logging()
app = FastAPI(title="Home Financial API", version="0.1.0")
app.add_exception_handler(DomainError, domain_error_handler)
app.add_exception_handler(RequestValidationError, request_validation_error_handler)
app.state.settings = settings
app.state.repositories = create_repositories(settings)
app.state.llm = create_llm(settings)
app.state.classification_fallback = (
    CrewAIClassificationFallback(
        app.state.llm,
        tracing_enabled=settings.crewai_tracing_enabled,
    )
    if app.state.llm is not None
    else None
)
app.state.insight_generator = (
    CrewAIInsightGenerator(
        app.state.llm,
        tracing_enabled=settings.crewai_tracing_enabled,
    )
    if app.state.llm is not None
    else None
)
app.state.merchant_context_service = MerchantContextService(
    app.state.repositories.merchant_contexts
)
app.state.classifier = ClassificationService(
    categories=app.state.repositories.categories,
    expenses=app.state.repositories.expenses,
    decisions=app.state.repositories.classification_decisions,
    fallback_classifier=app.state.classification_fallback,
)
app.state.expense_service = ExpenseService(
    households=app.state.repositories.households,
    categories=app.state.repositories.categories,
    expenses=app.state.repositories.expenses,
    decisions=app.state.repositories.classification_decisions,
    classifier=app.state.classifier,
    merchant_contexts=app.state.merchant_context_service,
)
app.state.csv_import_service = CSVImportService(
    categories=app.state.repositories.categories,
    import_runs=app.state.repositories.import_runs,
    expenses=app.state.expense_service,
)
app.state.category_service = CategoryService(
    households=app.state.repositories.households,
    categories=app.state.repositories.categories,
    expenses=app.state.repositories.expenses,
    decisions=app.state.repositories.classification_decisions,
)
app.state.dashboard_service = DashboardService(
    households=app.state.repositories.households,
    categories=app.state.repositories.categories,
    expenses=app.state.repositories.expenses,
)
app.state.insight_service = InsightsService(
    dashboard=app.state.dashboard_service,
    categories=app.state.repositories.categories,
    expenses=app.state.repositories.expenses,
    insight_runs=app.state.repositories.insight_runs,
    generator=app.state.insight_generator,
    merchant_contexts=app.state.merchant_context_service,
    model_name=settings.copilot_model,
)
app.state.export_service = ExportService(
    households=app.state.repositories.households,
    categories=app.state.repositories.categories,
    expenses=app.state.repositories.expenses,
    imports=app.state.repositories.import_runs,
    decisions=app.state.repositories.classification_decisions,
    insights=app.state.repositories.insight_runs,
    evaluations=app.state.repositories.evaluation_runs,
)
app.state.evaluation_service = EvaluationService(
    households=app.state.repositories.households,
    categories=app.state.repositories.categories,
    evaluations=app.state.repositories.evaluation_runs,
    dataset_path=settings.evaluation_dataset_path,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-Request-ID", "Idempotency-Key"],
)


@app.middleware("http")
async def add_request_id(request: Request, call_next) -> Response:
    request_id = uuid4().hex
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(router)


def run() -> None:
    uvicorn.run(
        "home_financial_backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=settings.app_env == "local",
        reload_dirs=[str(Path(__file__).resolve().parent)],
    )
