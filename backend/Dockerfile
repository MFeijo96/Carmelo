FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.33 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src ./src
COPY data ./data

RUN uv sync --frozen --no-dev \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app --no-create-home app \
    && chown -R app:app /app /opt/venv

USER app

EXPOSE 8000

CMD ["/opt/venv/bin/uvicorn", "home_financial_backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
