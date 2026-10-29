"""External local embedding transport contract tests."""

from __future__ import annotations

import errno
import json
import socket
import socketserver
import threading
import time
import traceback
from collections.abc import Iterator
from contextlib import suppress
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Protocol, cast

import httpx
import pytest
from src.semantic.external_config import ExternalSemanticSettings
from src.semantic.external_embedding import ExternalEmbeddingClient, ExternalEmbeddingError


class _EmbeddingHTTPHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        server = cast(_EmbeddingUnixServer, self.server)
        length = int(self.headers.get("Content-Length", "0"))
        server.requests.append(json.loads(self.rfile.read(length)))
        server.paths.append(self.path)
        server.auth_headers.append(self.headers.get("Authorization"))
        server.secret_headers.append(self.headers.get("X-Secret"))
        if server.delay_seconds and self.path == "/v1/embeddings":
            time.sleep(server.delay_seconds)
        response_body = (
            {"tokens": [11, 12, 13]} if self.path == "/tokenize" else server.response_body
        )
        body = json.dumps(response_body).encode("utf-8")
        self.send_response(server.status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        with suppress(BrokenPipeError):
            self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


class _EmbeddingUnixServer(socketserver.UnixStreamServer):
    def __init__(
        self,
        path: str,
        response_body: dict[str, Any],
        *,
        status_code: int = 200,
        delay_seconds: float = 0,
    ) -> None:
        self.response_body = response_body
        self.status_code = status_code
        self.delay_seconds = delay_seconds
        self.requests: list[dict[str, Any]] = []
        self.paths: list[str] = []
        self.auth_headers: list[str | None] = []
        self.secret_headers: list[str | None] = []
        super().__init__(path, _EmbeddingHTTPHandler)


def _settings(
    socket_path: str | None,
    *,
    base_url: str = "http://127.0.0.1/v1",
    timeout_seconds: float = 1.0,
) -> ExternalSemanticSettings:
    return ExternalSemanticSettings(
        enabled=True,
        cache_root=Path("/tmp/semantic-embedding-test-cache"),
        model="bge-m3-test",
        model_revision="fixture-sha256",
        base_url=base_url,
        unix_socket=Path(socket_path) if socket_path else None,
        dimensions=2,
        timeout_seconds=timeout_seconds,
    )


def _response(
    vector: list[float | int],
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "object": "list",
        "data": [{"object": "embedding", "embedding": vector, "index": 0}],
        "model": "bge-m3-test",
        "usage": {"prompt_tokens": 3, "total_tokens": 3},
    }
    if extra:
        response.update(extra)
    return response


class _UnixEmbeddingServerFactory(Protocol):
    def __call__(
        self,
        response_body: dict[str, Any],
        *,
        status_code: int = 200,
        delay_seconds: float = 0,
    ) -> tuple[_EmbeddingUnixServer, threading.Thread, str]: ...


class _MockEmbeddingTransportFactory(Protocol):
    def __call__(
        self,
        response_body: dict[str, Any],
        *,
        status_code: int = 200,
        tokenizer_response_body: dict[str, Any] | None = None,
        tokenizer_status_code: int = 200,
        tokenizer_response_content: bytes | None = None,
        tokenizer_error: bool = False,
    ) -> list[httpx.Request]: ...


@pytest.fixture
def unix_embedding_server(tmp_path: Path) -> Iterator[_UnixEmbeddingServerFactory]:
    def start(
        response_body: dict[str, Any],
        *,
        status_code: int = 200,
        delay_seconds: float = 0,
    ) -> tuple[_EmbeddingUnixServer, threading.Thread, str]:
        path = str(tmp_path / "embeddings.sock")
        probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            probe.bind(str(tmp_path / "uds-permission-probe.sock"))
        except OSError as exc:
            if exc.errno in {errno.EPERM, errno.EACCES}:
                pytest.skip("sandbox policy forbids binding a local Unix socket")
            raise
        finally:
            probe.close()
            (tmp_path / "uds-permission-probe.sock").unlink(missing_ok=True)
        server = _EmbeddingUnixServer(
            path,
            response_body,
            status_code=status_code,
            delay_seconds=delay_seconds,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread, path

    yield start


@pytest.fixture
def mock_embedding_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> _MockEmbeddingTransportFactory:
    def install(
        response_body: dict[str, Any],
        *,
        status_code: int = 200,
        tokenizer_response_body: dict[str, Any] | None = None,
        tokenizer_status_code: int = 200,
        tokenizer_response_content: bytes | None = None,
        tokenizer_error: bool = False,
    ) -> list[httpx.Request]:
        requests: list[httpx.Request] = []

        def respond(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.url.path == "/tokenize":
                if tokenizer_error:
                    raise httpx.ConnectError(request.content.decode(), request=request)
                token_content = tokenizer_response_content
                if token_content is None:
                    token_content = json.dumps(
                        (
                            tokenizer_response_body
                            if tokenizer_response_body is not None
                            else {"tokens": [11, 12, 13]}
                        ),
                    ).encode("utf-8")
                return httpx.Response(
                    tokenizer_status_code,
                    content=token_content,
                    headers={"Content-Type": "application/json"},
                )
            return httpx.Response(
                status_code,
                content=json.dumps(response_body, allow_nan=True).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )

        def transport_factory(**_kwargs: Any) -> httpx.MockTransport:
            return httpx.MockTransport(respond)

        monkeypatch.setattr(httpx, "HTTPTransport", transport_factory)
        return requests

    return install


def test_client_posts_local_input_through_unix_socket(
    unix_embedding_server: _UnixEmbeddingServerFactory,
) -> None:
    server, thread, path = unix_embedding_server(_response([0.6, 0.8]))
    text = "synthetic local embedding probe"
    try:
        with ExternalEmbeddingClient(_settings(path)) as client:
            assert client.embed_text(text) == [0.6, 0.8]
        assert server.requests == [
            {
                "add_special": True,
                "content": text,
                "parse_special": True,
                "with_pieces": False,
            },
            {"input": text, "model": "bge-m3-test"},
        ]
        assert server.paths == ["/tokenize", "/v1/embeddings"]
        assert server.auth_headers == ["Bearer local", "Bearer local"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


@pytest.mark.parametrize(
    ("vector", "expected_code"),
    [
        ([1.0], "embedding_dimension_mismatch"),
        ([0.0, 0.0], "embedding_zero_norm"),
        ([float("nan"), 1.0], "embedding_non_finite"),
        ([True, 1.0], "embedding_vector_invalid"),
    ],
)
def test_client_rejects_invalid_embedding_vectors(
    mock_embedding_transport: _MockEmbeddingTransportFactory,
    vector: list[float | int],
    expected_code: str,
) -> None:
    mock_embedding_transport(_response(vector))
    with (
        ExternalEmbeddingClient(_settings("/tmp/fixture-embedding.sock")) as client,
        pytest.raises(ExternalEmbeddingError) as caught,
    ):
        client.embed_text("synthetic input")
    assert caught.value.code == expected_code


def test_client_reports_server_truncation_without_echoing_input(
    mock_embedding_transport: _MockEmbeddingTransportFactory,
) -> None:
    secret_text = "graph text must not appear in transport errors"
    mock_embedding_transport(
        _response([0.6, 0.8], extra={"truncated": True}),
    )
    with (
        ExternalEmbeddingClient(_settings("/tmp/fixture-embedding.sock")) as client,
        pytest.raises(ExternalEmbeddingError) as caught,
    ):
        client.embed_text(secret_text)
    assert caught.value.code == "embedding_input_truncated"
    assert caught.value.prompt_tokens == 3
    assert secret_text not in str(caught.value)


def test_client_rejects_input_at_reported_server_token_limit(
    mock_embedding_transport: _MockEmbeddingTransportFactory,
) -> None:
    mock_embedding_transport(
        _response(
            [0.6, 0.8],
            extra={"usage": {"prompt_tokens": 3, "input_token_limit": 3}},
        ),
    )
    with (
        ExternalEmbeddingClient(_settings("/tmp/fixture-embedding.sock")) as client,
        pytest.raises(ExternalEmbeddingError) as caught,
    ):
        client.embed_text("synthetic input")
    assert caught.value.code == "embedding_input_truncated"
    assert caught.value.prompt_tokens == 3
    assert caught.value.input_limit == 3


def test_client_does_not_retry_rejected_request_or_echo_response(
    mock_embedding_transport: _MockEmbeddingTransportFactory,
) -> None:
    secret_text = "private synthetic request string"
    requests = mock_embedding_transport(
        {"error": {"message": secret_text}},
        status_code=400,
    )
    with (
        ExternalEmbeddingClient(_settings("/tmp/fixture-embedding.sock")) as client,
        pytest.raises(ExternalEmbeddingError) as caught,
    ):
        client.embed_text(secret_text)
    assert caught.value.code == "embedding_request_rejected"
    assert caught.value.status_code == 400
    assert [request.url.path for request in requests] == ["/tokenize", "/v1/embeddings"]
    assert secret_text not in str(caught.value)


def test_client_requires_an_explicit_local_or_unix_socket_endpoint() -> None:
    remote = _settings("/tmp/unused-embedding.sock").model_copy(
        update={"base_url": "https://api.example.com/v1"},
    )
    with pytest.raises(ExternalEmbeddingError) as caught:
        ExternalEmbeddingClient(remote)
    assert caught.value.code == "embedding_endpoint_not_local"


def test_client_can_use_only_an_explicit_loopback_http_endpoint(
    mock_embedding_transport: _MockEmbeddingTransportFactory,
) -> None:
    requests = mock_embedding_transport(_response([0.6, 0.8]))
    settings = _settings(None, base_url="http://127.0.0.1:8081/v1")
    with ExternalEmbeddingClient(settings) as client:
        assert client.embed_text("synthetic loopback probe") == [0.6, 0.8]
    assert [str(request.url) for request in requests] == [
        "http://127.0.0.1:8081/tokenize",
        "http://127.0.0.1:8081/v1/embeddings",
    ]
    assert json.loads(requests[0].content) == {
        "content": "synthetic loopback probe",
        "add_special": True,
        "parse_special": True,
        "with_pieces": False,
    }


def test_client_rejects_overlong_utf8_input_before_sending(
    mock_embedding_transport: _MockEmbeddingTransportFactory,
) -> None:
    requests = mock_embedding_transport(_response([0.6, 0.8]))
    settings = _settings(None).model_copy(
        update={"max_input_bytes": 8, "max_input_tokens": 480},
    )
    with (
        ExternalEmbeddingClient(settings) as client,
        pytest.raises(ExternalEmbeddingError) as caught,
    ):
        client.embed_text("é" * 5)
    assert caught.value.code == "embedding_input_too_long"
    assert requests == []


def test_client_checks_actual_token_count_before_embedding_request(
    mock_embedding_transport: _MockEmbeddingTransportFactory,
) -> None:
    requests = mock_embedding_transport(_response([0.6, 0.8]))
    settings = _settings(None).model_copy(
        update={"max_input_bytes": 32768, "max_input_tokens": 2},
    )
    with (
        ExternalEmbeddingClient(settings) as client,
        pytest.raises(ExternalEmbeddingError) as caught,
    ):
        client.embed_text("synthetic input")
    assert caught.value.code == "embedding_input_too_many_tokens"
    assert caught.value.prompt_tokens == 3
    assert caught.value.input_limit == 2
    assert [request.url.path for request in requests] == ["/tokenize"]


def test_client_accepts_token_count_above_utf8_bytes_after_normalization(
    mock_embedding_transport: _MockEmbeddingTransportFactory,
) -> None:
    sample_text = "ﷺ"
    requests = mock_embedding_transport(
        _response([0.6, 0.8]),
        tokenizer_response_body={"tokens": [1, 2, 3, 4, 5, 6]},
    )
    with ExternalEmbeddingClient(_settings(None)) as client:
        assert len(sample_text.encode("utf-8")) == 3
        assert client.count_tokens(sample_text) == 6
    assert [request.url.path for request in requests] == ["/tokenize"]


def test_client_enforces_input_limit_with_expanded_token_count(
    mock_embedding_transport: _MockEmbeddingTransportFactory,
) -> None:
    sample_text = "ﷺ"
    requests = mock_embedding_transport(
        _response([0.6, 0.8]),
        tokenizer_response_body={"tokens": list(range(481))},
    )
    with (
        ExternalEmbeddingClient(_settings(None)) as client,
        pytest.raises(ExternalEmbeddingError) as caught,
    ):
        client.embed_text(sample_text)
    assert caught.value.code == "embedding_input_too_many_tokens"
    assert caught.value.prompt_tokens == 481
    assert caught.value.input_limit == 480
    assert [request.url.path for request in requests] == ["/tokenize"]


@pytest.mark.parametrize(
    "tokens",
    [[True], [-1], ["11"], [None]],
)
def test_client_rejects_malformed_token_ids(
    mock_embedding_transport: _MockEmbeddingTransportFactory,
    tokens: list[Any],
) -> None:
    requests = mock_embedding_transport(
        _response([0.6, 0.8]),
        tokenizer_response_body={"tokens": tokens},
    )
    with (
        ExternalEmbeddingClient(_settings(None)) as client,
        pytest.raises(ExternalEmbeddingError) as caught,
    ):
        client.count_tokens("synthetic input")
    assert caught.value.code == "tokenizer_response_invalid"
    assert [request.url.path for request in requests] == ["/tokenize"]


def test_client_rejects_implausibly_long_token_id_array(
    mock_embedding_transport: _MockEmbeddingTransportFactory,
) -> None:
    requests = mock_embedding_transport(
        _response([0.6, 0.8]),
        tokenizer_response_body={"tokens": [1] * 65_537},
    )
    with (
        ExternalEmbeddingClient(_settings(None)) as client,
        pytest.raises(ExternalEmbeddingError) as caught,
    ):
        client.count_tokens("x")
    assert caught.value.code == "tokenizer_response_invalid"
    assert [request.url.path for request in requests] == ["/tokenize"]


def test_client_does_not_fallback_when_tokenizer_returns_404(
    mock_embedding_transport: _MockEmbeddingTransportFactory,
) -> None:
    requests = mock_embedding_transport(
        _response([0.6, 0.8]),
        tokenizer_status_code=404,
    )
    with (
        ExternalEmbeddingClient(_settings(None)) as client,
        pytest.raises(ExternalEmbeddingError) as caught,
    ):
        client.embed_text("synthetic input")
    assert caught.value.code == "tokenizer_request_rejected"
    assert caught.value.status_code == 404
    assert [request.url.path for request in requests] == ["/tokenize"]


def test_client_does_not_fallback_when_tokenizer_transport_fails(
    mock_embedding_transport: _MockEmbeddingTransportFactory,
) -> None:
    sample_text = "private tokenizer request"
    requests = mock_embedding_transport(
        _response([0.6, 0.8]),
        tokenizer_error=True,
    )
    with (
        ExternalEmbeddingClient(_settings(None)) as client,
        pytest.raises(ExternalEmbeddingError) as caught,
    ):
        client.embed_text(sample_text)
    assert caught.value.code == "tokenizer_transport_error"
    assert sample_text not in str(caught.value)
    assert sample_text not in "".join(traceback.format_exception(caught.value))
    assert [request.url.path for request in requests] == ["/tokenize"]


def test_client_rejects_oversized_tokenizer_response_body(
    mock_embedding_transport: _MockEmbeddingTransportFactory,
) -> None:
    requests = mock_embedding_transport(
        _response([0.6, 0.8]),
        tokenizer_response_content=b" " * (1024 * 1024),
    )
    with (
        ExternalEmbeddingClient(_settings(None)) as client,
        pytest.raises(ExternalEmbeddingError) as caught,
    ):
        client.count_tokens("probe")
    assert caught.value.code == "tokenizer_response_too_large"
    assert [request.url.path for request in requests] == ["/tokenize"]


def test_client_token_cache_is_hashed_bounded_and_lru(
    mock_embedding_transport: _MockEmbeddingTransportFactory,
) -> None:
    requests = mock_embedding_transport(_response([0.6, 0.8]))
    sample_text = "private note content"
    with ExternalEmbeddingClient(_settings(None)) as client:
        assert client.count_tokens(sample_text) == 3
        assert client.count_tokens(sample_text) == 3
        assert sample_text not in repr(client._token_cache)
        for index in range(127):
            client.count_tokens(f"cache item {index}")
        assert client.count_tokens(sample_text) == 3
        client.count_tokens("cache item 127")
        assert len(client._token_cache) == 128
        assert client.count_tokens(sample_text) == 3
        client.count_tokens("cache item 0")
        assert len(client._token_cache) == 128
    assert len(requests) == 130
    assert all(request.url.path == "/tokenize" for request in requests)


def test_client_token_cache_separates_special_token_flags(
    mock_embedding_transport: _MockEmbeddingTransportFactory,
) -> None:
    requests = mock_embedding_transport(_response([0.6, 0.8]))
    with ExternalEmbeddingClient(_settings(None)) as client:
        assert client.count_tokens("same content", add_special=True) == 3
        assert client.count_tokens("same content", add_special=False) == 3
    assert [json.loads(request.content)["add_special"] for request in requests] == [
        True,
        False,
    ]


def test_client_rejects_tokenizer_input_over_byte_limit_before_request(
    mock_embedding_transport: _MockEmbeddingTransportFactory,
) -> None:
    requests = mock_embedding_transport(_response([0.6, 0.8]))
    settings = _settings(None).model_copy(
        update={"max_input_bytes": 3, "max_input_tokens": 480},
    )
    with (
        ExternalEmbeddingClient(settings) as client,
        pytest.raises(ExternalEmbeddingError) as caught,
    ):
        client.count_tokens("éé")
    assert caught.value.code == "tokenizer_input_too_long"
    assert requests == []


def test_client_does_not_use_proxy_or_openai_secret_environment(
    mock_embedding_transport: _MockEmbeddingTransportFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests = mock_embedding_transport(_response([0.6, 0.8]))
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")
    monkeypatch.setenv("OPENAI_CUSTOM_HEADERS", "X-Secret: must-not-be-sent")
    with ExternalEmbeddingClient(_settings("/tmp/fixture-embedding.sock")) as client:
        assert client.embed_text("synthetic local probe") == [0.6, 0.8]
    assert requests[0].headers["authorization"] == "Bearer local"
    assert "x-secret" not in requests[0].headers


def test_client_uses_configured_timeout_and_closes_on_context_exit(
    mock_embedding_transport: _MockEmbeddingTransportFactory,
) -> None:
    mock_embedding_transport(_response([0.6, 0.8]))
    client = ExternalEmbeddingClient(_settings("/tmp/fixture-embedding.sock", timeout_seconds=60))
    assert client._http.timeout.read == 60
    with client:
        assert client.embed_text("synthetic input") == [0.6, 0.8]
    with pytest.raises(ExternalEmbeddingError) as closed:
        client.embed_text("synthetic input")
    assert closed.value.code == "embedding_client_closed"


def test_client_timeout_is_enforced_by_real_unix_transport(
    unix_embedding_server: _UnixEmbeddingServerFactory,
) -> None:
    server, thread, path = unix_embedding_server(
        _response([0.6, 0.8]),
        delay_seconds=1.2,
    )
    try:
        with (
            ExternalEmbeddingClient(_settings(path, timeout_seconds=1.0)) as client,
            pytest.raises(ExternalEmbeddingError) as caught,
        ):
            client.embed_text("synthetic input")
        assert caught.value.code == "embedding_timeout"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)
