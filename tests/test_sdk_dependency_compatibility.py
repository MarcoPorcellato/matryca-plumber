"""Exercise the real structured-output and API SDKs over an in-memory transport."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from copy import deepcopy
from importlib import metadata, util
from typing import Any

import httpx
import instructor
import pytest
from openai import (
    APIConnectionError,
    APITimeoutError,
    BadRequestError,
    InternalServerError,
    OpenAI,
)
from openai.types.chat import ChatCompletion
from packaging.requirements import Requirement
from packaging.version import Version
from pydantic import BaseModel, ConfigDict, Field
from src.agent.context_compressor import ChatMessage
from src.agent.llm_client import (
    MAX_SELF_CORRECTION_RETRIES,
    AdaptiveStructuredOutputEngine,
    GrammarCapability,
    InstructorLLMClient,
    LlmBackendProfile,
    StructuredOutputExhaustedError,
    _to_sdk_messages,
    pydantic_to_strict_json_schema,
)
from src.agent.plumber_config import PlumberLintConfig
from src.semantic.embedding import OpenAICompatibleEmbeddingClient

_BASE_URL = "https://sdk.invalid/v1"
_MODEL = "synthetic-model"
_SYSTEM = "Preserve this caller instruction."
_PROMPT = "Return only synthetic fixture data."
_VALID_JSON = '{"label":"synthetic","detail":{"count":2}}'


class SdkDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int = Field(ge=1)


class SdkResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1)
    detail: SdkDetail


@contextmanager
def _sdk_client(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    max_retries: int = 0,
) -> Iterator[OpenAI]:
    with (
        httpx.Client(transport=httpx.MockTransport(handler), trust_env=False) as http_client,
        OpenAI(
            base_url=_BASE_URL,
            api_key="synthetic-not-a-credential",
            http_client=http_client,
            max_retries=max_retries,
            timeout=1.0,
        ) as client,
    ):
        yield client


def _engine(raw: OpenAI, capability: GrammarCapability) -> AdaptiveStructuredOutputEngine:
    # Inject a real SDK client without constructing filesystem-backed telemetry.
    # Fix only the capability selection; routing, SDK calls and parsing stay real.
    client = object.__new__(InstructorLLMClient)
    client._raw_client = raw
    client.base_url = _BASE_URL
    client.model = _MODEL
    client._runtime_lint_config = PlumberLintConfig()
    client.thermal_stop_event = None
    engine = AdaptiveStructuredOutputEngine(client)
    engine._backend_profile = LlmBackendProfile(
        base_url=_BASE_URL,
        model=_MODEL,
        grammar_capability=capability,
        probed_at=0.0,
    )
    return engine


def _complete(engine: AdaptiveStructuredOutputEngine) -> tuple[SdkResult, object]:
    return engine.completion_structured(
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _PROMPT},
        ],
        response_model=SdkResult,
        prompt=_PROMPT,
        started=0.0,
        use_history=False,
        stateless=False,
        telemetry_target=None,
        telemetry_operation=None,
        log_tokens=False,
        thermal_profile="none",
    )


def _chat_response(
    content: str | None,
    *,
    tool_name: str | None = None,
) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_name is not None:
        message["tool_calls"] = [
            {
                "id": "synthetic-tool-call",
                "type": "function",
                "function": {"name": tool_name, "arguments": _VALID_JSON},
            },
        ]
    return {
        "id": "synthetic-completion",
        "object": "chat.completion",
        "created": 0,
        "model": _MODEL,
        "choices": [
            {
                "index": 0,
                "finish_reason": "tool_calls" if tool_name is not None else "stop",
                "message": message,
            },
        ],
        "usage": {"prompt_tokens": 9, "completion_tokens": 8, "total_tokens": 17},
    }


def _assert_nested_schema(schema: dict[str, Any]) -> None:
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["label", "detail"]
    assert schema["properties"]["label"]["minLength"] == 1
    detail = schema["$defs"]["SdkDetail"]
    assert detail["additionalProperties"] is False
    assert detail["required"] == ["count"]
    assert detail["properties"]["count"]["minimum"] == 1


def test_sdk_message_boundary_preserves_roles_order_content_and_caller() -> None:
    messages: list[ChatMessage] = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": _PROMPT},
        {"role": "assistant", "content": "Synthetic prior response.\n"},
    ]
    original = deepcopy(messages)

    converted = _to_sdk_messages(messages)

    assert converted == original
    assert converted is not messages
    for sdk_message, message in zip(converted, messages, strict=True):
        assert sdk_message is not message
    converted[0]["content"] = "Synthetic SDK-side modification."
    assert messages == original


def test_sdk_message_boundary_rejects_unknown_roles() -> None:
    malformed: ChatMessage = json.loads('{"role":"tool","content":"synthetic"}')

    with pytest.raises(ValueError, match="^Unsupported chat message role$"):
        _to_sdk_messages([malformed])


def test_default_sdk_imports_and_wrapping_do_not_require_diskcache() -> None:
    assert util.find_spec("diskcache") is None
    assert Version("1.15.0") <= Version(metadata.version("instructor")) < Version("2")
    assert Version("2") <= Version(metadata.version("openai")) < Version("3")
    requirements = metadata.requires("instructor")
    assert requirements
    base_names = {
        requirement.name.lower().replace("_", "-")
        for raw in requirements
        if (requirement := Requirement(raw)).marker is None
        or requirement.marker.evaluate({"extra": ""})
    }
    assert "openai" in base_names
    assert "diskcache" not in base_names
    assert "pre-commit" not in base_names
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=_chat_response(_VALID_JSON))

    with _sdk_client(handle) as raw:
        wrapped = instructor.from_openai(raw, mode=instructor.Mode.MD_JSON)
        assert isinstance(wrapped, instructor.Instructor)
    assert not requests


def test_path_a_preserves_nested_strict_schema_and_raw_completion() -> None:
    requests: list[dict[str, Any]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/chat/completions"
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=_chat_response(_VALID_JSON))

    _assert_nested_schema(pydantic_to_strict_json_schema(SdkResult))
    with _sdk_client(handle) as raw:
        parsed, completion = _complete(_engine(raw, GrammarCapability.LOGITS_JSON_SCHEMA))
    assert parsed == SdkResult(label="synthetic", detail=SdkDetail(count=2))
    assert isinstance(completion, ChatCompletion)
    assert completion.id == "synthetic-completion"
    assert completion.usage is not None
    assert completion.usage.total_tokens == 17
    assert len(requests) == 1
    response_format = requests[0]["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "SdkResult"
    assert response_format["json_schema"]["strict"] is True
    _assert_nested_schema(response_format["json_schema"]["schema"])
    assert requests[0]["messages"] == [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": _PROMPT},
    ]


@pytest.mark.parametrize(
    "content",
    [
        "not-json",
        '{"label":"synthetic"}',
        '{"label":"synthetic","detail":{"count":0}}',
    ],
)
def test_path_a_rejects_malformed_incomplete_or_invalid_nested_payload(content: str) -> None:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=_chat_response(content))

    with _sdk_client(handle) as raw, pytest.raises(ValueError):
        _complete(_engine(raw, GrammarCapability.LOGITS_JSON_SCHEMA))
    assert len(requests) == 1


@pytest.mark.parametrize(
    "capability",
    [GrammarCapability.LEGACY_TEXT, GrammarCapability.INSTRUCTOR_TOOLS],
)
def test_path_b_real_wrapper_preserves_request_schema_and_raw_completion(
    capability: GrammarCapability,
) -> None:
    requests: list[dict[str, Any]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/chat/completions"
        requests.append(json.loads(request.content))
        reply = (
            _chat_response(None, tool_name="SdkResult")
            if capability == GrammarCapability.INSTRUCTOR_TOOLS
            else _chat_response(f"```json\n{_VALID_JSON}\n```")
        )
        return httpx.Response(200, json=reply)

    with _sdk_client(handle) as raw:
        parsed, completion = _complete(_engine(raw, capability))
    assert isinstance(parsed, SdkResult)
    assert isinstance(parsed.detail, SdkDetail)
    assert parsed.model_dump() == {"label": "synthetic", "detail": {"count": 2}}
    assert isinstance(completion, ChatCompletion)
    assert completion.id == "synthetic-completion"
    assert len(requests) == 1
    request = requests[0]
    if capability == GrammarCapability.INSTRUCTOR_TOOLS:
        function = request["tools"][0]["function"]
        assert function["name"] == "SdkResult"
        _assert_nested_schema(function["parameters"])
        assert request["tool_choice"]["function"]["name"] == "SdkResult"
        assert request["messages"][0]["content"] == _SYSTEM
    else:
        system = request["messages"][0]["content"]
        assert system.startswith(_SYSTEM + "\n\n")
        assert "Parse the content and return a JSON object matching this schema:" in system
        assert "Return a valid JSON instance, not the schema definition." in system
        assert '"$defs"' in system
        assert '"minimum": 1' in system
        assert '"label"' in system
        user = request["messages"][-1]["content"]
        assert _PROMPT in user
        assert "```json codeblock. not the JSON_SCHEMA" in user
        assert "tools" not in request


@pytest.mark.parametrize(
    "capability",
    [GrammarCapability.LEGACY_TEXT, GrammarCapability.INSTRUCTOR_TOOLS],
)
def test_path_b_converts_current_messages_after_correction(
    capability: GrammarCapability,
) -> None:
    requests: list[dict[str, Any]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/chat/completions"
        requests.append(json.loads(request.content))
        if len(requests) <= 2:
            return httpx.Response(200, json=_chat_response("not-json"))
        reply = (
            _chat_response(None, tool_name="SdkResult")
            if capability == GrammarCapability.INSTRUCTOR_TOOLS
            else _chat_response(f"```json\n{_VALID_JSON}\n```")
        )
        return httpx.Response(200, json=reply)

    with _sdk_client(handle) as raw:
        parsed, completion = _complete(_engine(raw, capability))

    assert isinstance(parsed, SdkResult)
    assert isinstance(parsed.detail, SdkDetail)
    assert parsed.model_dump() == {"label": "synthetic", "detail": {"count": 2}}
    assert isinstance(completion, ChatCompletion)
    assert len(requests) == 3
    assert requests[1]["response_format"] == {"type": "json_object"}
    retry_messages = requests[2]["messages"]
    assert retry_messages[0]["role"] == "system"
    assert retry_messages[0]["content"].startswith(_SYSTEM)
    assert any(
        message["role"] == "user" and _PROMPT in message["content"] for message in retry_messages
    )
    assert any(
        message["role"] == "user"
        and message["content"].startswith(
            "Your previous output failed validation with this error:\n",
        )
        for message in retry_messages
    )


@pytest.mark.parametrize("failure", ["invalid-json", "missing-tool", "wrong-tool"])
def test_path_b_rejects_invalid_replies_and_bounds_raw_salvage(failure: str) -> None:
    requests: list[dict[str, Any]] = []
    capability = (
        GrammarCapability.LEGACY_TEXT
        if failure == "invalid-json"
        else GrammarCapability.INSTRUCTOR_TOOLS
    )

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        tool_name = "WrongResult" if failure == "wrong-tool" else None
        return httpx.Response(200, json=_chat_response("not-json", tool_name=tool_name))

    with (
        _sdk_client(handle) as raw,
        pytest.raises(StructuredOutputExhaustedError, match="structured_output_exhausted"),
    ):
        _complete(_engine(raw, capability))
    # One real wrapper call and one unsuccessful raw salvage per production turn.
    assert len(requests) == 2 * MAX_SELF_CORRECTION_RETRIES
    for wrapper_request, salvage_request in zip(requests[::2], requests[1::2], strict=True):
        if capability == GrammarCapability.INSTRUCTOR_TOOLS:
            assert wrapper_request["tools"][0]["function"]["name"] == "SdkResult"
        else:
            assert "matching this schema" in wrapper_request["messages"][0]["content"]
        assert salvage_request["response_format"] == {"type": "json_object"}


def _embedding_client(raw: OpenAI) -> OpenAICompatibleEmbeddingClient:
    client = object.__new__(OpenAICompatibleEmbeddingClient)
    client._client = raw
    client._model = "synthetic-embedding"
    return client


def test_embedding_uses_real_sdk_request_and_parses_numeric_vector() -> None:
    requests: list[dict[str, Any]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/embeddings"
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "object": "list",
                "model": "synthetic-embedding",
                "data": [{"object": "embedding", "index": 0, "embedding": [0.25, -0.5, 1]}],
                "usage": {"prompt_tokens": 2, "total_tokens": 2},
            },
        )

    with _sdk_client(handle) as raw:
        assert _embedding_client(raw).embed_text("  synthetic input  ") == [0.25, -0.5, 1.0]
    assert len(requests) == 1
    assert requests[0]["model"] == "synthetic-embedding"
    assert requests[0]["input"] == "synthetic input"


def test_embedding_rejects_empty_input_before_sdk_request() -> None:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"data": []})

    with _sdk_client(handle) as raw, pytest.raises(ValueError, match="requires non-empty text"):
        _embedding_client(raw).embed_text(" \n\t ")
    assert not requests


def test_embedding_rejects_empty_sdk_response() -> None:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"data": [], "model": "synthetic-embedding"})

    with _sdk_client(handle) as raw, pytest.raises(ValueError, match="No embedding data received"):
        _embedding_client(raw).embed_text("synthetic input")
    assert len(requests) == 1


@pytest.mark.parametrize(
    ("failure", "error_type"),
    [("api", BadRequestError), ("timeout", APITimeoutError), ("transport", APIConnectionError)],
)
def test_embedding_preserves_sdk_failure_types_without_retry(
    failure: str,
    error_type: type[Exception],
) -> None:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("synthetic timeout", request=request)
        if failure == "transport":
            raise httpx.ConnectError("synthetic connection failure", request=request)
        return httpx.Response(400, json={"error": {"message": "synthetic invalid request"}})

    with _sdk_client(handle) as raw, pytest.raises(error_type):
        _embedding_client(raw).embed_text("synthetic input")
    assert len(requests) == 1


@pytest.mark.parametrize(
    ("failure", "error_type"),
    [
        ("api", InternalServerError),
        ("timeout", APITimeoutError),
        ("transport", APIConnectionError),
    ],
)
def test_path_a_bounds_production_transport_retries_without_real_sleep(
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    error_type: type[Exception],
) -> None:
    requests: list[httpx.Request] = []
    sleeps: list[float] = []
    monkeypatch.setenv("MATRYCA_LLM_TRANSPORT_RETRIES", "2")
    monkeypatch.setattr(time, "sleep", sleeps.append)

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("synthetic timeout", request=request)
        if failure == "transport":
            raise httpx.ConnectError("synthetic connection failure", request=request)
        return httpx.Response(503, json={"error": {"message": "synthetic unavailable"}})

    with _sdk_client(handle) as raw, pytest.raises(error_type):
        _complete(_engine(raw, GrammarCapability.LOGITS_JSON_SCHEMA))
    assert len(requests) == 2
    assert sleeps == [1.0]


def test_real_sdk_retry_budget_is_separate_from_application_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []
    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", sleeps.append)

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(503, json={"error": {"message": "synthetic unavailable"}})

    with _sdk_client(handle, max_retries=2) as raw, pytest.raises(InternalServerError):
        raw.chat.completions.create(
            model=_MODEL,
            messages=[{"role": "user", "content": _PROMPT}],
        )
    assert len(requests) == 3
    assert len(sleeps) == 2
    assert all(0 <= delay <= 60 for delay in sleeps)
