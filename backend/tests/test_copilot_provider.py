import asyncio
import inspect
import json
from types import SimpleNamespace
from unittest.mock import Mock, create_autospec

import pytest
from copilot import CopilotClient, CopilotSession
from copilot.rpc import PermissionDecisionReject
from copilot.session_events import AssistantMessageData, AssistantUsageData
from pydantic import ValidationError

from home_financial_backend.domain.errors import FallbackUnavailable
from home_financial_backend.domain.models import Expense, SafeClassificationContext
from home_financial_backend.domain.seed import DEMO_HOUSEHOLD
from home_financial_backend.infrastructure.memory_repositories import create_demo_repositories
from home_financial_backend.runtime import provider
from home_financial_backend.runtime.adapters import (
    CrewAIClassificationFallback,
    CrewAIInsightGenerator,
)
from home_financial_backend.runtime.provider import CopilotLLM, provider_request_scope
from home_financial_backend.runtime.usage import ProviderUsage, record_usage, take_usage
from home_financial_backend.services.dashboard import DashboardService
from home_financial_backend.services.insights import InsightsService
from home_financial_backend.settings import Settings


@pytest.fixture
def sdk(monkeypatch):
    clients = []
    state = SimpleNamespace(clients=clients, response='{"result":"ok"}', error=None, usage=None)

    def construct(**options):
        inspect.signature(CopilotClient).bind(**options)
        client = create_autospec(CopilotClient, instance=True)
        session = create_autospec(CopilotSession, instance=True)
        session.session_id = f"private-session-{len(clients)}"
        client.create_session.return_value = session

        async def respond(prompt, **kwargs):
            if state.usage is not None:
                client.create_session.call_args.kwargs["on_event"](
                    SimpleNamespace(data=state.usage)
                )
            if state.error is not None:
                raise state.error
            content = state.response(prompt) if callable(state.response) else state.response
            if content is None:
                return None
            return SimpleNamespace(data=AssistantMessageData(content=content, message_id="reply"))

        session.send_and_wait.side_effect = respond
        clients.append(SimpleNamespace(client=client, session=session, options=options))
        return client

    state.factory = Mock(side_effect=construct)
    monkeypatch.setattr(provider, "CopilotClient", state.factory)
    take_usage()
    yield state
    take_usage()


def llm(**kwargs):
    return CopilotLLM(model="account-supported-model", **kwargs)


def test_sessions_are_isolated_tool_free_and_closed(sdk) -> None:
    model = llm()
    messages = [
        {"role": "system", "content": "Return the required JSON."},
        {"role": "user", "content": "Allow-listed context."},
        {"role": "assistant", "content": "Prior response."},
    ]

    assert model.call(messages) == sdk.response
    assert model.call("Another bounded request") == sdk.response
    assert len(sdk.clients) == 2
    for record in sdk.clients:
        assert record.options["mode"] == "empty"
        assert record.options["use_logged_in_user"] is True
        assert record.options["github_token"] is None
        assert record.options["connection"].path is None
        config = record.client.create_session.call_args.kwargs
        assert config["model"] == model.model
        assert config["available_tools"] == config["tools"] == []
        assert config["memory"] == config["infinite_sessions"] == {"enabled": False}
        for setting in (
            "streaming",
            "enable_config_discovery",
            "enable_session_store",
            "enable_skills",
            "enable_file_hooks",
            "enable_host_git_operations",
            "enable_session_telemetry",
        ):
            assert config[setting] is False
        assert "session_id" not in config
        assert "provider" not in config
        assert isinstance(config["on_permission_request"](None, {}), PermissionDecisionReject)
        record.session.disconnect.assert_awaited_once()
        record.client.delete_session.assert_awaited_once_with(record.session.session_id)
        record.client.stop.assert_awaited_once()
    first = sdk.clients[0]
    assert first.client.create_session.call_args.kwargs["system_message"] == {
        "mode": "replace",
        "content": "Return the required JSON.",
    }
    assert json.loads(first.session.send_and_wait.call_args.args[0]) == messages[1:]
    assert take_usage() is None


def test_automation_token_is_secret_and_disables_local_identity(sdk) -> None:
    settings = Settings(
        _env_file=None,
        copilot_enabled=True,
        copilot_model="account-supported-model",
        copilot_github_token="synthetic-test-token",
        copilot_cli_path="/test/copilot",
    )
    model = provider.create_llm(settings)
    assert "synthetic-test-token" not in repr(settings)
    assert "synthetic-test-token" not in settings.model_dump_json()
    assert "synthetic-test-token" not in repr(model)
    assert "synthetic-test-token" not in model.model_dump_json()
    model.call("safe input")
    options = sdk.clients[0].options
    assert options["github_token"] == "synthetic-test-token"
    assert options["use_logged_in_user"] is False
    assert options["connection"].path == "/test/copilot"


@pytest.mark.parametrize("content", ["", " ", None])
def test_empty_or_missing_response_is_rejected_and_cleaned_up(sdk, content) -> None:
    sdk.response = content
    with pytest.raises(FallbackUnavailable):
        llm().call("safe context")
    sdk.clients[0].session.disconnect.assert_awaited_once()
    sdk.clients[0].client.stop.assert_awaited_once()


@pytest.mark.parametrize("error", [PermissionError("private token"), RuntimeError("model blocked")])
def test_sdk_failures_are_sanitized_and_do_not_retry(sdk, error) -> None:
    sdk.error = error
    model = llm()
    with provider_request_scope(model, max_calls=2):
        with pytest.raises(FallbackUnavailable) as caught:
            model.call("safe context")
        assert "private token" not in str(caught.value.__cause__)
        with pytest.raises(FallbackUnavailable, match="budget exhausted"):
            model.call("must not reach SDK")
    assert len(sdk.clients) == 1
    sdk.clients[0].session.disconnect.assert_awaited_once()
    sdk.clients[0].client.stop.assert_awaited_once()


def test_request_deadline_times_out_and_cleans_up(sdk) -> None:
    original = sdk.factory.side_effect

    def construct(**options):
        client = original(**options)

        async def pending(*args, **kwargs):
            await asyncio.Event().wait()

        client.create_session.return_value.send_and_wait.side_effect = pending
        return client

    sdk.factory.side_effect = construct
    with pytest.raises(FallbackUnavailable) as caught:
        llm(timeout_seconds=0.02).call("safe context")
    assert isinstance(caught.value.__cause__, TimeoutError)
    sdk.clients[0].session.disconnect.assert_awaited_once()
    sdk.clients[0].client.stop.assert_awaited_once()


def test_async_cancellation_stops_owned_client(sdk) -> None:
    sdk.error = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(llm().acall("safe context"))
    sdk.clients[0].session.disconnect.assert_awaited_once()
    sdk.clients[0].client.stop.assert_awaited_once()


def test_client_start_failure_still_cleans_up(sdk) -> None:
    original = sdk.factory.side_effect

    def construct(**options):
        client = original(**options)
        client.start.side_effect = RuntimeError("CLI missing")
        return client

    sdk.factory.side_effect = construct
    with pytest.raises(FallbackUnavailable):
        llm().call("safe context")
    sdk.clients[0].client.stop.assert_awaited_once()
    sdk.clients[0].client.create_session.assert_not_awaited()


def test_graceful_stop_failure_forces_shutdown(sdk) -> None:
    original = sdk.factory.side_effect

    def construct(**options):
        client = original(**options)
        client.stop.side_effect = RuntimeError("shutdown failed")
        return client

    sdk.factory.side_effect = construct
    assert llm().call("safe context") == sdk.response
    sdk.clients[0].client.force_stop.assert_awaited_once()


@pytest.mark.parametrize("max_calls", [1, 2])
def test_task_call_budget_is_enforced(sdk, max_calls) -> None:
    model = llm()
    with provider_request_scope(model, max_calls):
        for _ in range(max_calls):
            model.call("safe context")
        with pytest.raises(FallbackUnavailable, match="budget exhausted"):
            model.call("extra conversion call")
    assert len(sdk.clients) == max_calls


def test_sdk_usage_survives_asyncio_run_without_fabricating_missing_metrics(sdk) -> None:
    sdk.usage = AssistantUsageData(model="account-supported-model", input_tokens=23)
    llm().call("safe context")
    assert take_usage() == ProviderUsage(prompt_tokens=23)
    record_usage(ProviderUsage(10, 20))
    record_usage(ProviderUsage(30, 40))
    assert take_usage() == ProviderUsage(40, 60)


@pytest.mark.parametrize(
    "messages", [[], [{"role": "tool", "content": "no"}], [{"role": "user", "content": []}]]
)
def test_nontext_and_tool_messages_never_reach_sdk(sdk, messages) -> None:
    with pytest.raises(ValueError):
        llm().call(messages)
    sdk.factory.assert_not_called()


def test_tools_and_synchronous_event_loop_calls_are_rejected(sdk) -> None:
    with pytest.raises(FallbackUnavailable, match="tools are disabled"):
        llm().call("safe context", tools=[{"name": "shell"}])

    async def in_event_loop():
        with pytest.raises(FallbackUnavailable, match="worker thread"):
            llm().call("safe context")
        assert await llm().acall("safe context") == sdk.response

    asyncio.run(in_event_loop())
    assert len(sdk.clients) == 1


def test_enabled_settings_require_explicit_supported_model(monkeypatch) -> None:
    monkeypatch.delenv("COPILOT_MODEL", raising=False)
    with pytest.raises(ValidationError, match="COPILOT_MODEL"):
        Settings(_env_file=None, copilot_enabled=True)
    for value in (0, -1, 121):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, llm_timeout_seconds=value)


def test_real_crewai_classification_validates_and_restores_opaque_category(sdk) -> None:
    def respond(prompt):
        text = json.loads(prompt)[-1]["content"]
        option = text.split("'category_id': '", 1)[1].split("'", 1)[0]
        return "Final Answer: " + json.dumps(
            {
                "category_id": option,
                "confidence": 0.8,
                "reason": "Contexto compativel.",
                "source": "llm_fallback",
                "review_required": False,
            }
        )

    sdk.response = respond
    category = create_demo_repositories().categories.require_active_leaf(
        DEMO_HOUSEHOLD.id,
        "category-mercado",
    )
    candidate = CrewAIClassificationFallback(llm())(
        SafeClassificationContext(merchant_alias="Estabelecimento ficticio"),
        (category,),
    )
    assert candidate.category_id == category.id
    assert candidate.confidence == 0.8
    assert len(sdk.clients) == 1


@pytest.mark.parametrize(
    ("error", "error_code"),
    [
        (None, None),
        (PermissionError("synthetic-private-token rejected"), "authentication"),
        (TimeoutError("request timed out"), "timeout"),
        (RuntimeError("model blocked"), "provider_error"),
        (RuntimeError("Copilot quota exhausted"), "rate_limit"),
    ],
)
def test_real_crewai_insights_preserve_schema_sources_and_provider_fallback(
    sdk, error, error_code
) -> None:
    repositories = create_demo_repositories()
    repositories.expenses.add(
        Expense(
            id="private-expense",
            household_id=DEMO_HOUSEHOLD.id,
            date="2026-10-01",
            description="Private description",
            merchant="Private Merchant",
            amount_cents=1250,
            payment_method="debito",
            category_id="category-mercado",
            source="manual",
        )
    )

    def respond(prompt):
        text = json.loads(prompt)[-1]["content"]
        assert "Private description" not in text
        assert "Private Merchant" not in text
        assert "private-expense" not in text
        token = text.split("'token': '", 1)[1].split("'", 1)[0]
        return "Final Answer: " + json.dumps(
            {
                "title": "Resumo",
                "text": "As despesas do mes somaram R$ 12,50.",
                "source_refs": [token],
            }
        )

    sdk.response = respond
    sdk.error = error
    service = InsightsService(
        DashboardService(repositories.households, repositories.categories, repositories.expenses),
        repositories.categories,
        repositories.expenses,
        repositories.insight_runs,
        generator=CrewAIInsightGenerator(llm()),
        model_name="account-supported-model",
    )
    run, sources = service.generate(DEMO_HOUSEHOLD.id, "2026-10")
    assert run.provider_status == ("failed" if error else "used")
    assert run.provider_error_code == error_code
    assert run.provider == (None if error else "copilot")
    assert "R$ 12,50" in run.cards[0].text
    assert sources[run.cards[0].source_refs[0]] == ("private-expense",)
    assert "synthetic-private-token" not in run.model_dump_json()
    assert run.prompt_tokens is None
    assert run.estimated_cost_usd is None
    assert len(sdk.clients) == 1


def test_existing_local_cli_connection_is_optional_and_loopback_only(sdk) -> None:
    settings = Settings(
        _env_file=None,
        copilot_enabled=True,
        copilot_model="account-supported-model",
        copilot_cli_url="127.0.0.1:4321",
    )
    provider.create_llm(settings).call("safe context")
    assert sdk.clients[0].options["connection"].url == "127.0.0.1:4321"
    assert sdk.clients[0].options["mode"] == "empty"
    for url in (
        "0.0.0.0:4321",
        "192.168.1.10:4321",
        "example.com:4321",
        "localhost:0",
        "127.0.0.1:65536",
        "https://127.0.0.1:4321",
    ):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, copilot_cli_url=url)
