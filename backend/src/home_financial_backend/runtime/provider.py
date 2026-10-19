import asyncio
import json
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Any

from copilot import CopilotClient, CopilotSession, RuntimeConnection
from copilot._jsonrpc import JsonRpcError
from copilot.rpc import PermissionDecisionReject
from copilot.session_events import AssistantMessageData, AssistantUsageData, SessionEvent
from crewai import BaseLLM
from pydantic import Field, SecretStr

from home_financial_backend.domain.errors import FallbackUnavailable
from home_financial_backend.runtime.usage import ProviderUsage, record_usage
from home_financial_backend.settings import Settings


@dataclass
class RequestBudget:
    deadline: float
    calls_remaining: int
    failed: bool = False
    failure: Exception | None = None


_budget: ContextVar[RequestBudget | None] = ContextVar("copilot_budget", default=None)


class CopilotRateLimitError(RuntimeError):
    pass


@contextmanager
def provider_request_scope(llm: Any, max_calls: int) -> Iterator[None]:
    if not isinstance(llm, CopilotLLM):
        yield
        return
    token = _budget.set(RequestBudget(monotonic() + llm.timeout_seconds, max_calls))
    try:
        yield
    finally:
        _budget.reset(token)


class CopilotLLM(BaseLLM):
    provider: str = "copilot"
    timeout_seconds: float = 15
    github_token: SecretStr | None = Field(default=None, exclude=True, repr=False)
    cli_path: str | None = None
    cli_url: str | None = None

    def supports_function_calling(self) -> bool:
        return False

    def supports_stop_words(self) -> bool:
        return False

    def call(
        self,
        messages: Any,
        tools: Any = None,
        callbacks: Any = None,
        available_functions: Any = None,
        from_task: Any = None,
        from_agent: Any = None,
        response_model: Any = None,
    ) -> str:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            text, usage = asyncio.run(self._generate(messages, tools, available_functions))
            if usage is not None:
                record_usage(usage)
            return text
        raise FallbackUnavailable("Synchronous Copilot calls require a worker thread")

    async def acall(
        self,
        messages: Any,
        tools: Any = None,
        callbacks: Any = None,
        available_functions: Any = None,
        from_task: Any = None,
        from_agent: Any = None,
        response_model: Any = None,
    ) -> str:
        text, usage = await self._generate(messages, tools, available_functions)
        if usage is not None:
            record_usage(usage)
        return text

    async def _generate(
        self, messages: Any, tools: Any, available_functions: Any
    ) -> tuple[str, ProviderUsage | None]:
        if tools or available_functions:
            raise FallbackUnavailable("Copilot tools are disabled")
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        if not isinstance(messages, list) or not messages:
            raise ValueError("Copilot requires non-empty text messages")
        system_messages: list[str] = []
        conversation: list[dict[str, str]] = []
        for message in messages:
            role, content = message.get("role"), message.get("content")
            if role not in {"system", "user", "assistant"} or not isinstance(content, str):
                raise ValueError("Copilot accepts only system, user and assistant text")
            if role == "system":
                system_messages.append(content)
            else:
                conversation.append({"role": role, "content": content})
        client: CopilotClient | None = None
        session: CopilotSession | None = None
        usage: ProviderUsage | None = None
        budget = _budget.get()
        timeout = self.timeout_seconds
        if budget is not None:
            timeout = min(timeout, budget.deadline - monotonic())
            if budget.failed or budget.calls_remaining <= 0 or timeout <= 0:
                raise FallbackUnavailable("Copilot request budget exhausted") from budget.failure
            budget.calls_remaining -= 1

        def on_event(event: SessionEvent) -> None:
            nonlocal usage
            if isinstance(event.data, AssistantUsageData):
                reported = ProviderUsage(
                    prompt_tokens=event.data.input_tokens,
                    completion_tokens=event.data.output_tokens,
                    copilot_nano_aiu=(
                        event.data.copilot_usage.total_nano_aiu
                        if event.data.copilot_usage is not None
                        else None
                    ),
                )
                usage = usage + reported if usage is not None else reported

        try:
            async with asyncio.timeout(timeout):
                client = CopilotClient(
                    connection=(
                        RuntimeConnection.for_uri(self.cli_url)
                        if self.cli_url
                        else RuntimeConnection.for_stdio(path=self.cli_path)
                    ),
                    mode="empty",
                    base_directory=str(Path.home() / ".copilot"),
                    github_token=self.github_token.get_secret_value()
                    if self.github_token
                    else None,
                    use_logged_in_user=not bool(self.github_token),
                    log_level="none",
                )
                await client.start()
                session = await client.create_session(
                    model=self.model,
                    github_token=self.github_token.get_secret_value()
                    if self.github_token
                    else None,
                    available_tools=[],
                    tools=[],
                    memory={"enabled": False},
                    infinite_sessions={"enabled": False},
                    streaming=False,
                    enable_config_discovery=False,
                    enable_session_store=False,
                    enable_skills=False,
                    enable_file_hooks=False,
                    enable_host_git_operations=False,
                    enable_session_telemetry=False,
                    on_event=on_event,
                    on_permission_request=lambda request, invocation: PermissionDecisionReject(),
                    system_message={"mode": "replace", "content": "\n\n".join(system_messages)},
                )
                response = await session.send_and_wait(
                    json.dumps(conversation, ensure_ascii=False),
                    timeout=self.timeout_seconds,
                )
                if (
                    response is None
                    or not isinstance(response.data, AssistantMessageData)
                    or not response.data.content.strip()
                ):
                    raise ValueError("Copilot returned no assistant text")
                return response.data.content, usage
        except (OSError, RuntimeError, ValueError, JsonRpcError) as error:
            if budget is not None:
                budget.failed = True
            if isinstance(error, TimeoutError):
                cause: Exception = TimeoutError("Copilot request timed out")
            elif isinstance(error, PermissionError) or any(
                marker in str(error).lower()
                for marker in ("authentication", "not authenticated", "unauthorized", "401", "403")
            ):
                cause = PermissionError("Copilot authentication unavailable")
            elif isinstance(error, ValueError):
                cause = ValueError("Copilot returned an invalid response")
            elif any(
                marker in str(error).lower()
                for marker in ("rate limit", "quota", "429", "credits exhausted", "allowance")
            ):
                cause = CopilotRateLimitError("Copilot usage allowance unavailable")
            else:
                cause = RuntimeError("Copilot provider unavailable")
            if budget is not None:
                budget.failure = cause
            raise FallbackUnavailable("Copilot generation failed") from cause
        except asyncio.CancelledError:
            if budget is not None:
                budget.failed = True
            raise
        finally:
            if client is not None:
                await self._cleanup(client, session)

    @staticmethod
    async def _cleanup(client: CopilotClient, session: CopilotSession | None) -> None:
        with suppress(Exception):
            async with asyncio.timeout(1):
                if session is not None:
                    await session.disconnect()
                    await client.delete_session(session.session_id)
        stopped = False
        with suppress(Exception):
            async with asyncio.timeout(1):
                await client.stop()
                stopped = True
        if not stopped:
            with suppress(Exception):
                async with asyncio.timeout(1):
                    await client.force_stop()
                    stopped = True
        if not stopped:
            raise FallbackUnavailable("Copilot runtime cleanup failed")


def create_llm(settings: Settings) -> CopilotLLM | None:
    if not settings.copilot_enabled:
        return None
    assert settings.copilot_model is not None
    return CopilotLLM(
        model=settings.copilot_model,
        github_token=settings.copilot_github_token,
        cli_path=settings.copilot_cli_path,
        cli_url=settings.copilot_cli_url,
        timeout_seconds=settings.llm_timeout_seconds,
    )
