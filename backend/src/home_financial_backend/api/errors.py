from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from home_financial_backend.api.models import ApiEnvelope, ApiError, ApiMeta
from home_financial_backend.domain.errors import (
    CategoryAlreadyExists,
    CategoryNotFound,
    CSVStructureError,
    DomainError,
    EvaluationUnavailable,
    ExpenseNotFound,
    HouseholdNotFound,
)


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    field: str | None = None,
) -> JSONResponse:
    envelope = ApiEnvelope[dict[str, str]](
        data=None,
        errors=[ApiError(code=code, message=message, field=field)],
        meta=ApiMeta(request_id=request.state.request_id),
    )
    return JSONResponse(status_code=status_code, content=envelope.model_dump(mode="json"))


async def domain_error_handler(request: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, DomainError):
        raise error
    if isinstance(error, EvaluationUnavailable):
        status_code = 503
    elif isinstance(error, CategoryAlreadyExists):
        status_code = 409
    elif isinstance(error, (CategoryNotFound, ExpenseNotFound, HouseholdNotFound)):
        status_code = 404
    elif isinstance(error, CSVStructureError):
        status_code = 422
    else:
        status_code = 422
    return _error_response(
        request,
        status_code=status_code,
        code=type(error).__name__,
        message=str(error),
    )


async def request_validation_error_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    if not isinstance(error, RequestValidationError):
        raise error
    details = error.errors()
    first = details[0] if details else {}
    location = first.get("loc", ())
    field = str(location[-1]) if location else None
    return _error_response(
        request,
        status_code=422,
        code="invalid_request",
        message="Os dados enviados são inválidos.",
        field=field,
    )
