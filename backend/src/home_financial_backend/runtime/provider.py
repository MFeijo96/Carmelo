from crewai import LLM

from home_financial_backend.settings import Settings


def create_openai_llm(settings: Settings) -> LLM | None:
    if not settings.openai_api_key:
        return None
    return LLM(
        model=settings.openai_model,
        provider="openai",
        api_key=settings.openai_api_key,
        temperature=settings.openai_temperature,
        max_tokens=settings.openai_max_tokens,
        timeout=settings.openai_timeout_seconds,
    )
