from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    copilot_nano_aiu: float | None = None

    def __add__(self, other: "ProviderUsage") -> "ProviderUsage":
        return ProviderUsage(
            prompt_tokens=(
                self.prompt_tokens + other.prompt_tokens
                if self.prompt_tokens is not None and other.prompt_tokens is not None
                else None
            ),
            completion_tokens=(
                self.completion_tokens + other.completion_tokens
                if self.completion_tokens is not None and other.completion_tokens is not None
                else None
            ),
            copilot_nano_aiu=(
                self.copilot_nano_aiu + other.copilot_nano_aiu
                if self.copilot_nano_aiu is not None and other.copilot_nano_aiu is not None
                else None
            ),
        )


_last_usage: ContextVar[ProviderUsage | None] = ContextVar("provider_usage", default=None)


def record_usage(usage: ProviderUsage | None) -> None:
    previous = _last_usage.get()
    _last_usage.set(previous + usage if previous is not None and usage is not None else usage)


def take_usage() -> ProviderUsage | None:
    usage = _last_usage.get()
    _last_usage.set(None)
    return usage
