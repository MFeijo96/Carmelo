import csv
import json
import re
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import StringIO
from time import perf_counter
from typing import cast
from uuid import uuid4

from home_financial_backend.api.contracts import ExpenseCreateRequest
from home_financial_backend.domain.errors import (
    AmbiguousCategoryLabel,
    CSVRowInvalid,
    CSVStructureError,
    ParentCategoryNotAssignable,
    UnknownCategoryLabel,
)
from home_financial_backend.domain.models import ImportRowError, ImportRun, PaymentMethod
from home_financial_backend.domain.repositories import (
    CategoryRepository,
    ImportRunRepository,
)
from home_financial_backend.observability import log_event
from home_financial_backend.services.expenses import ExpenseService

REQUIRED_COLUMNS = frozenset({"data", "descricao", "valor", "forma_pagamento"})
OPTIONAL_COLUMNS = frozenset({"estabelecimento", "categoria", "recorrente", "observacoes"})
ALLOWED_COLUMNS = REQUIRED_COLUMNS | OPTIONAL_COLUMNS
PAYMENT_METHODS = frozenset({"dinheiro", "debito", "credito"})
BRL_AMOUNT_PATTERN = re.compile(r"(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d{1,2})?\Z")
CSV_DATE_PATTERN = re.compile(r"\d{2}/\d{2}/\d{4}\Z")


class CSVImportService:
    def __init__(
        self,
        categories: CategoryRepository,
        import_runs: ImportRunRepository,
        expenses: ExpenseService,
    ) -> None:
        self._categories = categories
        self._import_runs = import_runs
        self._expenses = expenses

    def import_text(
        self,
        household_id: str,
        content: str,
        source_name: str | None = None,
    ) -> ImportRun:
        headers, rows = self._read_structure(content)
        started = perf_counter()
        imported_count = 0
        row_errors: list[ImportRowError] = []
        for row_number, values in rows:
            try:
                request = self._parse_row(household_id, headers, values, row_number)
            except CSVRowInvalid as error:
                row_errors.extend(error.errors)
                continue
            self._expenses.create_imported(household_id, request)
            imported_count += 1

        import_run = ImportRun(
            id=uuid4().hex,
            household_id=household_id,
            source_name=source_name,
            total_rows=len(rows),
            imported_rows=imported_count,
            rejected_rows=len(rows) - imported_count,
            row_errors=tuple(row_errors),
            status="completed",
        )
        error_codes = Counter(error.code for error in row_errors)
        log_event(
            "csv_import",
            total_rows=import_run.total_rows,
            imported_rows=import_run.imported_rows,
            rejected_rows=import_run.rejected_rows,
            error_codes=json.dumps(error_codes, sort_keys=True),
            duration_ms=round((perf_counter() - started) * 1000),
        )
        return self._import_runs.add(import_run)

    @staticmethod
    def _read_structure(content: str) -> tuple[tuple[str, ...], list[tuple[int, dict[str, str]]]]:
        reader = csv.reader(StringIO(content.lstrip("\ufeff")), strict=True)
        try:
            raw_headers = next(reader)
        except StopIteration as error:
            raise CSVStructureError("O arquivo CSV está vazio.") from error
        except csv.Error as error:
            raise CSVStructureError("O cabeçalho do CSV não pôde ser lido.") from error

        headers = tuple(header.strip() for header in raw_headers)
        if not headers or any(not header for header in headers):
            raise CSVStructureError("O cabeçalho do CSV contém coluna vazia.")
        if len(set(headers)) != len(headers):
            raise CSVStructureError("O cabeçalho do CSV contém colunas duplicadas.")
        missing = REQUIRED_COLUMNS - set(headers)
        unknown = set(headers) - ALLOWED_COLUMNS
        if missing:
            raise CSVStructureError(f"Colunas obrigatórias ausentes: {', '.join(sorted(missing))}.")
        if unknown:
            raise CSVStructureError(f"Colunas não suportadas: {', '.join(sorted(unknown))}.")

        rows: list[tuple[int, dict[str, str]]] = []
        try:
            for values in reader:
                if not values:
                    continue
                if len(values) != len(headers):
                    raise CSVStructureError(
                        f"Linha {reader.line_num}: quantidade de campos diferente do cabeçalho."
                    )
                rows.append((reader.line_num, dict(zip(headers, values, strict=True))))
        except csv.Error as error:
            raise CSVStructureError("O conteúdo do CSV está malformado.") from error
        return headers, rows

    def _parse_row(
        self,
        household_id: str,
        headers: tuple[str, ...],
        values: dict[str, str],
        row_number: int,
    ) -> ExpenseCreateRequest:
        errors: list[ImportRowError] = []

        def invalid(field: str, code: str, message: str, raw_value: str | None) -> None:
            errors.append(
                ImportRowError(
                    row=row_number,
                    field=field,
                    code=code,
                    message=message,
                    value=raw_value,
                )
            )

        raw_date = values["data"].strip()
        parsed_date = None
        if not CSV_DATE_PATTERN.fullmatch(raw_date):
            invalid("data", "invalid_date", "Use a data no formato dd/mm/aaaa.", raw_date)
        else:
            try:
                parsed_date = datetime.strptime(raw_date, "%d/%m/%Y").date()
            except ValueError:
                invalid("data", "invalid_date", "Informe uma data válida.", raw_date)

        description = values["descricao"].strip()
        if not description:
            invalid("descricao", "required", "A descrição é obrigatória.", values["descricao"])
        elif len(description) > 120:
            invalid(
                "descricao",
                "too_long",
                "A descrição deve ter no máximo 120 caracteres.",
                values["descricao"],
            )

        raw_amount = values["valor"].strip()
        amount_cents = self._parse_amount(raw_amount)
        if amount_cents is None:
            invalid("valor", "invalid_brl_amount", "Informe um valor positivo em BRL.", raw_amount)

        payment_method = values["forma_pagamento"].strip().casefold()
        if payment_method not in PAYMENT_METHODS:
            invalid(
                "forma_pagamento",
                "invalid_payment_method",
                "Use dinheiro, debito ou credito.",
                values["forma_pagamento"],
            )

        recurring = False
        if "recorrente" in headers:
            raw_recurring = values["recorrente"].strip().casefold()
            if raw_recurring not in {"", "sim", "nao"}:
                invalid(
                    "recorrente",
                    "invalid_recurring_value",
                    "Use sim ou nao para indicar recorrência.",
                    values["recorrente"],
                )
            recurring = raw_recurring == "sim"

        category_id = None
        raw_category = values.get("categoria", "").strip()
        if raw_category:
            try:
                category_id = self._categories.resolve_active_leaf(
                    household_id,
                    raw_category,
                ).id
            except ParentCategoryNotAssignable:
                invalid(
                    "categoria",
                    "parent_category_not_assignable",
                    "Selecione uma categoria final, não um grupo.",
                    raw_category,
                )
            except (UnknownCategoryLabel, AmbiguousCategoryLabel):
                invalid(
                    "categoria",
                    "category_not_found_or_ambiguous",
                    "A categoria informada não corresponde a uma categoria final única.",
                    raw_category,
                )

        if errors or parsed_date is None or amount_cents is None:
            raise CSVRowInvalid(tuple(errors))

        return ExpenseCreateRequest(
            date=parsed_date,
            description=description,
            amount_cents=amount_cents,
            payment_method=cast(PaymentMethod, payment_method),
            category_id=category_id,
            recurring=recurring,
            merchant=self._optional_text(values.get("estabelecimento")),
            notes=self._optional_text(values.get("observacoes")),
        )

    @staticmethod
    def _optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @staticmethod
    def _parse_amount(value: str) -> int | None:
        amount_text = value.strip()
        if amount_text.upper().startswith("R$"):
            amount_text = amount_text[2:].strip()
        if not BRL_AMOUNT_PATTERN.fullmatch(amount_text):
            return None
        normalized = amount_text.replace(".", "").replace(",", ".")
        try:
            cents = Decimal(normalized) * 100
        except InvalidOperation:
            return None
        if cents <= 0 or cents != cents.to_integral_value():
            return None
        return int(cents)
