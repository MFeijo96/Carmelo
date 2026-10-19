from home_financial_backend.domain.models import ImportRowError


class DomainError(ValueError):
    """Base class for invalid domain or repository operations."""


class HouseholdNotFound(DomainError):
    pass


class CategoryNotFound(DomainError):
    pass


class ExpenseNotFound(DomainError):
    pass


class CategoryAlreadyExists(DomainError):
    pass


class UnknownCategoryLabel(DomainError):
    pass


class AmbiguousCategoryLabel(DomainError):
    pass


class ParentCategoryNotAssignable(DomainError):
    pass


class DuplicateRecord(DomainError):
    pass


class CSVStructureError(DomainError):
    pass


class FallbackUnavailable(DomainError):
    pass


class EvaluationUnavailable(DomainError):
    pass


class InsightRejected(DomainError):
    pass


class PendingExpenseReview(DomainError):
    pass


class IdempotencyConflict(DomainError):
    pass


class CSVRowInvalid(DomainError):
    def __init__(self, errors: tuple[ImportRowError, ...]) -> None:
        self.errors = errors
        super().__init__("CSV row contains invalid fields")
