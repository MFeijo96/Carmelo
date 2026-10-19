import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Callable
from secrets import token_urlsafe
from time import perf_counter
from typing import Literal

from home_financial_backend.domain.errors import (
    FallbackUnavailable,
    InsightRejected,
    PendingExpenseReview,
)
from home_financial_backend.domain.models import (
    Expense,
    InsightCard,
    InsightGroup,
    InsightRun,
    MonthlyDashboard,
    ProviderErrorCode,
    SafeClassificationContext,
)
from home_financial_backend.domain.repositories import (
    CategoryRepository,
    ExpenseRepository,
    InsightRunRepository,
)
from home_financial_backend.observability import log_event
from home_financial_backend.runtime.usage import ProviderUsage, take_usage
from home_financial_backend.services.dashboard import DashboardService
from home_financial_backend.services.merchant_context import MerchantContextService

InsightGenerator = Callable[
    [MonthlyDashboard, tuple[InsightGroup, ...], tuple[SafeClassificationContext, ...]],
    InsightCard,
]
BLOCKED_ADVICE = re.compile(
    r"\b(invista|investimento|investir|imposto|cr[eé]dito|financiamento|"
    r"pode pagar|pode assumir|deve cortar|deveria cortar|corte|economize|"
    r"economizar|reduza|recomendo|recomendamos)\b",
    re.IGNORECASE,
)
BRL_VALUE = re.compile(r"R\$\s*(\d[\d.]*,\d{2})", re.IGNORECASE)
PT_BR_MARKER = re.compile(
    r"\b(despesas|gastos|m[eê]s|categoria|categorias|foram|totalizou|"
    r"aumentou|diminuiu|registradas|pagamentos|recorrentes|compra|contas|casa|houve)\b",
    re.IGNORECASE,
)


def format_brl(amount_cents: int) -> str:
    whole, cents = divmod(amount_cents, 100)
    whole_text = f"{whole:,}".replace(",", ".")
    return f"R$ {whole_text},{cents:02d}"


class InsightsService:
    def __init__(
        self,
        dashboard: DashboardService,
        categories: CategoryRepository,
        expenses: ExpenseRepository,
        insight_runs: InsightRunRepository,
        generator: InsightGenerator | None = None,
        merchant_contexts: MerchantContextService | None = None,
        model_name: str | None = None,
    ) -> None:
        self._dashboard = dashboard
        self._categories = categories
        self._expenses = expenses
        self._insight_runs = insight_runs
        self._generator = generator
        self._merchant_contexts = merchant_contexts
        self._model_name = model_name

    def generate(
        self, household_id: str, month: str
    ) -> tuple[InsightRun, dict[str, tuple[str, ...]]]:
        summary = self._dashboard.monthly(household_id, month)
        month_expenses = tuple(
            expense
            for expense in self._expenses.list_by_household(household_id)
            if expense.date.strftime("%Y-%m") == month
        )
        pending_reviews = sum(expense.review_required for expense in month_expenses)
        if pending_reviews:
            raise PendingExpenseReview(
                f"Revise as {pending_reviews} despesas pendentes antes de gerar os insights do mês."
            )
        groups, sources = self._source_groups(household_id, month_expenses)
        summary_payload = summary.model_dump(mode="json")
        summary_hash = hashlib.sha256(
            json.dumps(summary_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()

        provider_status: Literal["used", "unavailable", "failed", "not_configured"]
        provider_status = "not_configured"
        provider_error_code: ProviderErrorCode | None = None
        safety_status: Literal["accepted", "fallback"] = "fallback"
        cards: tuple[InsightCard, ...] = ()
        latency_ms: int | None = None
        usage: ProviderUsage | None = None
        if groups:
            if self._generator is not None:
                started = perf_counter()
                take_usage()
                try:
                    projection = (
                        self._merchant_contexts.insight_projection(household_id, month_expenses)
                        if self._merchant_contexts is not None
                        else ()
                    )
                    generated = self._generator(summary, groups, projection)
                    self._validate_card(generated, summary, groups)
                    cards = (generated,)
                    provider_status = "used"
                    safety_status = "accepted"
                except (FallbackUnavailable, InsightRejected, ValueError, OSError) as error:
                    provider_status = "failed"
                    provider_error_code = self._provider_error_code(error)
                latency_ms = round((perf_counter() - started) * 1000)
                usage = take_usage()
            if not cards:
                cards = (self._fallback_card(summary, groups),)

        run = InsightRun(
            id=token_urlsafe(18),
            household_id=household_id,
            month=month,
            summary_version="1.0",
            summary_hash=summary_hash,
            cards=cards,
            provider="copilot" if provider_status == "used" else None,
            provider_status=provider_status,
            provider_error_code=provider_error_code,
            safety_status=safety_status,
            model=self._model_name if latency_ms is not None else None,
            latency_ms=latency_ms,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
            estimated_cost_usd=None,
        )
        log_event(
            "insight_generated",
            provider_status=provider_status,
            provider_error_code=provider_error_code,
            safety_status=safety_status,
            fallback_used=safety_status == "fallback",
            latency_ms=latency_ms,
            prompt_tokens=run.prompt_tokens,
            completion_tokens=run.completion_tokens,
            estimated_cost_usd=run.estimated_cost_usd,
            copilot_nano_aiu=usage.copilot_nano_aiu if usage else None,
        )
        return self._insight_runs.add(run), sources

    @staticmethod
    def _provider_error_code(error: Exception) -> ProviderErrorCode:
        if isinstance(error, InsightRejected):
            return "safety_rejection"

        cause: BaseException | None = error
        while cause is not None:
            error_type = type(cause).__name__.lower()
            if "auth" in error_type or "permission" in error_type:
                return "authentication"
            if "rate" in error_type or "quota" in error_type:
                return "rate_limit"
            if isinstance(cause, TimeoutError) or "timeout" in error_type:
                return "timeout"
            if isinstance(cause, ValueError) and not isinstance(cause, FallbackUnavailable):
                return "invalid_response"
            cause = cause.__cause__

        return "provider_error"

    def _source_groups(
        self,
        household_id: str,
        expenses: tuple[Expense, ...],
    ) -> tuple[tuple[InsightGroup, ...], dict[str, tuple[str, ...]]]:
        category_labels = {
            category.id: category.label
            for category in self._categories.list_by_household(household_id)
        }
        grouped: dict[str, list[Expense]] = defaultdict(list)
        for expense in expenses:
            grouped[expense.category_id].append(expense)
        groups: list[InsightGroup] = []
        source_map: dict[str, tuple[str, ...]] = {}
        for category_id, items in sorted(grouped.items()):
            token = token_urlsafe(18)
            groups.append(
                InsightGroup(
                    token=token,
                    category_id=category_id,
                    category_label=category_labels.get(category_id, "Outros"),
                    amount_cents=sum(item.amount_cents for item in items),
                    expense_count=len(items),
                )
            )
            source_map[token] = tuple(item.id for item in items)
        return tuple(groups), source_map

    @staticmethod
    def _fallback_card(
        summary: MonthlyDashboard,
        groups: tuple[InsightGroup, ...],
    ) -> InsightCard:
        source_refs = tuple(group.token for group in groups)
        count_sentence = (
            "foi registrada 1 despesa"
            if summary.expense_count == 1
            else f"foram registradas {summary.expense_count} despesas"
        )
        month_label = f"{summary.month[5:]}/{summary.month[:4]}"
        text = (
            f"No mês {month_label}, {count_sentence}, "
            f"com total de {format_brl(summary.total_cents)}."
        )
        if groups:
            largest = max(groups, key=lambda item: item.amount_cents)
            text += f" A maior categoria por valor foi {largest.category_label}."
        return InsightCard(
            title="Resumo do mês",
            text=text,
            source_refs=source_refs,
        )

    @staticmethod
    def _validate_card(
        card: InsightCard,
        summary: MonthlyDashboard,
        groups: tuple[InsightGroup, ...],
    ) -> None:
        tokens = {group.token for group in groups}
        if not card.source_refs or not set(card.source_refs).issubset(tokens):
            raise InsightRejected("Insight references a source outside the supplied groups")
        if not PT_BR_MARKER.search(card.text):
            raise InsightRejected("Insight text must be written in pt-BR")
        if BLOCKED_ADVICE.search(card.text):
            raise InsightRejected("Insight violates the educational safety policy")
        allowed_values = {
            format_brl(value)
            for value in (
                summary.total_cents,
                summary.recurring_cents,
                summary.previous_month_total_cents,
                *(group.amount_cents for group in groups),
            )
            if value is not None
        }
        if any(f"R$ {value}" not in allowed_values for value in BRL_VALUE.findall(card.text)):
            raise InsightRejected("Insight contains an unsupported currency value")
