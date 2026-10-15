from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderUsage:
    prompt_tokens: int
    completion_tokens: int


_last_usage: ContextVar[ProviderUsage | None] = ContextVar("provider_usage", default=None)


def record_usage(usage: ProviderUsage | None) -> None:
    _last_usage.set(usage)


def take_usage() -> ProviderUsage | None:
    usage = _last_usage.get()
    _last_usage.set(None)
    return usage
