from secrets import token_urlsafe
from typing import Any

from home_financial_backend.domain.errors import FallbackUnavailable
from home_financial_backend.domain.models import (
    Category,
    InsightCard,
    InsightGroup,
    MonthlyDashboard,
    SafeClassificationContext,
)
from home_financial_backend.runtime.contracts import ClassificationCandidate
from home_financial_backend.runtime.crew import build_classification_crew, build_insight_crew
from home_financial_backend.runtime.provider import provider_request_scope


class CrewAIClassificationFallback:
    def __init__(self, llm: Any, *, tracing_enabled: bool = False) -> None:
        self._llm = llm
        self._tracing_enabled = tracing_enabled

    def __call__(
        self,
        safe_context: SafeClassificationContext,
        active_leaf_taxonomy: tuple[Category, ...],
    ) -> ClassificationCandidate:
        try:
            category_options = {token_urlsafe(12): category for category in active_leaf_taxonomy}
            crew = build_classification_crew(
                self._llm,
                tracing_enabled=self._tracing_enabled,
            )
            with provider_request_scope(self._llm, max_calls=1):
                output = crew.kickoff(
                    inputs={
                        "safe_context": safe_context.model_dump(mode="json"),
                        "active_leaf_taxonomy": [
                            {"category_id": token, "label": category.label}
                            for token, category in category_options.items()
                        ],
                    }
                )
            candidate = getattr(output, "pydantic", None)
            if not isinstance(candidate, ClassificationCandidate):
                raise FallbackUnavailable("Classifier did not return its required schema")
            category = category_options.get(candidate.category_id)
            if category is None:
                raise FallbackUnavailable(
                    "Classifier selected a category outside the supplied options"
                )
            return candidate.model_copy(update={"category_id": category.id})
        except FallbackUnavailable:
            raise
        except Exception as error:
            raise FallbackUnavailable("Classifier provider failed") from error


class CrewAIInsightGenerator:
    def __init__(self, llm: Any, *, tracing_enabled: bool = False) -> None:
        self._llm = llm
        self._tracing_enabled = tracing_enabled

    def __call__(
        self,
        summary: MonthlyDashboard,
        groups: tuple[InsightGroup, ...],
        merchant_contexts: tuple[SafeClassificationContext, ...] = (),
    ) -> InsightCard:
        try:
            crew = build_insight_crew(
                self._llm,
                tracing_enabled=self._tracing_enabled,
            )
            safe_summary = {
                "month": summary.month,
                "total_cents": summary.total_cents,
                "expense_count": summary.expense_count,
                "category_breakdown": [
                    {
                        "label": item.label,
                        "amount_cents": item.amount_cents,
                        "percentage": item.percentage,
                    }
                    for item in summary.category_breakdown
                ],
                "payment_breakdown": [
                    {
                        "payment_method": item.payment_method,
                        "amount_cents": item.amount_cents,
                    }
                    for item in summary.payment_breakdown
                ],
                "recurring_cents": summary.recurring_cents,
                "previous_month_total_cents": summary.previous_month_total_cents,
                "change_cents": summary.change_cents,
            }
            safe_groups = [
                {
                    "token": item.token,
                    "category_label": item.category_label,
                    "amount_cents": item.amount_cents,
                    "expense_count": item.expense_count,
                }
                for item in groups
            ]
            with provider_request_scope(self._llm, max_calls=2):
                output = crew.kickoff(
                    inputs={
                        "monthly_summary": safe_summary,
                        "safe_context": {
                            "merchant_contexts": [
                                context.model_dump(mode="json") for context in merchant_contexts
                            ]
                        },
                        "source_groups": safe_groups,
                    }
                )
            card = getattr(output, "pydantic", None)
            if not isinstance(card, InsightCard):
                raise FallbackUnavailable("Insight agent did not return its required schema")
            return card
        except FallbackUnavailable:
            raise
        except Exception as error:
            raise FallbackUnavailable("Insight provider failed") from error
