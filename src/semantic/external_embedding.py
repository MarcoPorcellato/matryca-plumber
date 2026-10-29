"""Local-only OpenAI-compatible embedding transport for external semantic search."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import threading
from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

import httpx

if TYPE_CHECKING:
    from .external_config import ExternalSemanticSettings

_TOKEN_CACHE_SIZE = 128
_MAX_TOKEN_RESPONSE_BYTES = 4 * 1024 * 1024
_MAX_TOKEN_IDS = 65_536
_MAX_TOKEN_SPECIAL_OVERHEAD = 2


class ExternalEmbeddingError(RuntimeError):
    """A content-free transport or response error."""

    def __init__(
        self,
        code: str,
        *,
        status_code: int | None = None,
        prompt_tokens: int | None = None,
        input_limit: int | None = None,
        input_bytes: int | None = None,
        input_byte_limit: int | None = None,
    ) -> None:
        self.code = code
        self.status_code = status_code
        self.prompt_tokens = prompt_tokens
        self.input_limit = input_limit
        self.input_bytes = input_bytes
        self.input_byte_limit = input_byte_limit
        details = [code]
        if status_code is not None:
            details.append(f"status={status_code}")
        if prompt_tokens is not None:
            details.append(f"prompt_tokens={prompt_tokens}")
        if input_limit is not None:
            details.append(f"input_limit={input_limit}")
        if input_bytes is not None:
            details.append(f"input_bytes={input_bytes}")
        if input_byte_limit is not None:
            details.append(f"input_byte_limit={input_byte_limit}")
        super().__init__(" ".join(details))


def _is_loopback_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        address = ipaddress.ip_address(parsed.hostname or "")
        _ = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme in {"http", "https"}
        and address.is_loopback
        and parsed.username is None
        and parsed.password is None
        and not parsed.query
        and not parsed.fragment
    )


def _int_field(mapping: Any, *names: str) -> int | None:
    if not isinstance(mapping, dict):
        return None
    for name in names:
        value = mapping.get(name)
        if type(value) is int and value >= 0:
            return value
    return None


def _reported_truncation(payload: dict[str, Any]) -> bool:
    scopes: list[Any] = [payload, payload.get("usage")]
    data = payload.get("data")
    if isinstance(data, list) and data and isinstance(data[0], dict):
        scopes.extend((data[0], data[0].get("usage"), data[0].get("metadata")))
    flags = ("truncated", "input_truncated", "was_truncated")
    return any(
        isinstance(scope, dict) and any(scope.get(name) is True for name in flags)
        for scope in scopes
    )


class ExternalEmbeddingClient:
    """Call only a configured loopback or filesystem UDS embeddings endpoint."""

    def __init__(self, settings: ExternalSemanticSettings) -> None:
        self._settings = settings
        self.last_prompt_tokens: int | None = None
        self.last_input_limit: int | None = None
        self._closed = False

        if not settings.enabled:
            raise ExternalEmbeddingError("embedding_backend_disabled")
        if not settings.model.strip() or settings.model_revision == "unconfigured":
            raise ExternalEmbeddingError("embedding_identity_unconfigured")
        if type(settings.dimensions) is not int or settings.dimensions < 1:
            raise ExternalEmbeddingError("embedding_dimensions_invalid")
        if type(settings.max_input_bytes) is not int or settings.max_input_bytes < 1:
            raise ExternalEmbeddingError("embedding_byte_limit_invalid")
        if type(settings.max_input_tokens) is not int or settings.max_input_tokens < 1:
            raise ExternalEmbeddingError("embedding_token_limit_invalid")
        if not math.isfinite(settings.timeout_seconds) or settings.timeout_seconds <= 0:
            raise ExternalEmbeddingError("embedding_timeout_invalid")
        if not _is_loopback_url(settings.base_url):
            raise ExternalEmbeddingError("embedding_endpoint_not_local")

        transport: httpx.HTTPTransport
        if settings.unix_socket is not None:
            socket_path = Path(settings.unix_socket)
            if not socket_path.is_absolute() or ".." in socket_path.parts:
                raise ExternalEmbeddingError("embedding_socket_path_invalid")
            transport = httpx.HTTPTransport(uds=str(socket_path), retries=0)
        else:
            transport = httpx.HTTPTransport(retries=0)

        timeout = httpx.Timeout(settings.timeout_seconds)
        self._http = httpx.Client(
            transport=transport,
            timeout=timeout,
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
            follow_redirects=False,
            trust_env=False,
            headers={
                "Accept": "application/json",
                "Authorization": "Bearer local",
                "Content-Type": "application/json",
            },
        )
        parsed_base_url = urlsplit(settings.base_url)
        self._tokenize_url = f"{parsed_base_url.scheme}://{parsed_base_url.netloc}/tokenize"
        self._max_token_response_bytes = min(
            _MAX_TOKEN_RESPONSE_BYTES,
            (settings.max_input_bytes + _MAX_TOKEN_SPECIAL_OVERHEAD) * 16,
        )
        self._url = settings.base_url.rstrip("/") + "/embeddings"
        self._token_cache: OrderedDict[bytes, int] = OrderedDict()
        self._token_cache_lock = threading.Lock()

    def __enter__(self) -> ExternalEmbeddingClient:
        if self._closed:
            raise ExternalEmbeddingError("embedding_client_closed")
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        self.close()

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._http.close()

    def count_tokens(self, text: str, *, add_special: bool = True) -> int:
        """Return the local llama.cpp token count without retaining the input text."""
        if self._closed:
            raise ExternalEmbeddingError("embedding_client_closed")
        if not isinstance(text, str) or type(add_special) is not bool:
            raise ExternalEmbeddingError("tokenizer_input_invalid")
        try:
            text_bytes = text.encode("utf-8")
        except UnicodeEncodeError:
            raise ExternalEmbeddingError("tokenizer_input_invalid") from None
        input_bytes = len(text_bytes)
        if input_bytes > self._settings.max_input_bytes:
            raise ExternalEmbeddingError(
                "tokenizer_input_too_long",
                input_bytes=input_bytes,
                input_byte_limit=self._settings.max_input_bytes,
            )

        cache_key = hashlib.sha256(
            (b"\x01" if add_special else b"\x00") + text_bytes,
        ).digest()
        with self._token_cache_lock:
            cached_count = self._token_cache.get(cache_key)
            if cached_count is not None:
                self._token_cache.move_to_end(cache_key)
                return cached_count

        try:
            with self._http.stream(
                "POST",
                self._tokenize_url,
                json={
                    "content": text,
                    "add_special": add_special,
                    "parse_special": True,
                    "with_pieces": False,
                },
            ) as response:
                if response.status_code < 200 or response.status_code >= 300:
                    raise ExternalEmbeddingError(
                        "tokenizer_request_rejected",
                        status_code=response.status_code,
                    )
                response_body = bytearray()
                for chunk in response.iter_bytes(chunk_size=4096):
                    if len(response_body) + len(chunk) > self._max_token_response_bytes:
                        raise ExternalEmbeddingError("tokenizer_response_too_large")
                    response_body.extend(chunk)
        except httpx.TimeoutException:
            raise ExternalEmbeddingError("tokenizer_timeout") from None
        except httpx.HTTPError:
            raise ExternalEmbeddingError("tokenizer_transport_error") from None

        try:
            payload = json.loads(response_body)
        except (ValueError, UnicodeDecodeError):
            raise ExternalEmbeddingError("tokenizer_response_invalid") from None
        if not isinstance(payload, dict):
            raise ExternalEmbeddingError("tokenizer_response_invalid")
        tokens = payload.get("tokens")
        if (
            not isinstance(tokens, list)
            or len(tokens) > _MAX_TOKEN_IDS
            or any(type(token) is not int or token < 0 for token in tokens)
        ):
            raise ExternalEmbeddingError("tokenizer_response_invalid")

        token_count = len(tokens)
        with self._token_cache_lock:
            self._token_cache[cache_key] = token_count
            self._token_cache.move_to_end(cache_key)
            if len(self._token_cache) > _TOKEN_CACHE_SIZE:
                self._token_cache.popitem(last=False)
        return token_count

    def embed_text(self, text: str) -> list[float]:
        if self._closed:
            raise ExternalEmbeddingError("embedding_client_closed")
        if not isinstance(text, str) or not text.strip():
            raise ExternalEmbeddingError("embedding_input_empty")
        try:
            input_bytes = len(text.encode("utf-8"))
        except UnicodeEncodeError as exc:
            raise ExternalEmbeddingError("embedding_input_invalid") from exc
        if input_bytes > self._settings.max_input_bytes:
            raise ExternalEmbeddingError(
                "embedding_input_too_long",
                input_bytes=input_bytes,
                input_byte_limit=self._settings.max_input_bytes,
            )

        self.last_prompt_tokens = None
        self.last_input_limit = None
        token_count = self.count_tokens(text, add_special=True)
        if token_count > self._settings.max_input_tokens:
            self.last_prompt_tokens = token_count
            self.last_input_limit = self._settings.max_input_tokens
            raise ExternalEmbeddingError(
                "embedding_input_too_many_tokens",
                prompt_tokens=token_count,
                input_limit=self._settings.max_input_tokens,
            )
        try:
            response = self._http.post(
                self._url,
                json={"model": self._settings.model, "input": text},
            )
        except httpx.TimeoutException as exc:
            raise ExternalEmbeddingError("embedding_timeout") from exc
        except httpx.HTTPError as exc:
            raise ExternalEmbeddingError("embedding_transport_error") from exc

        if response.status_code < 200 or response.status_code >= 300:
            raise ExternalEmbeddingError(
                "embedding_request_rejected",
                status_code=response.status_code,
            )

        try:
            payload = response.json()
        except (ValueError, httpx.DecodingError) as exc:
            raise ExternalEmbeddingError("embedding_response_invalid") from exc
        if not isinstance(payload, dict):
            raise ExternalEmbeddingError("embedding_response_invalid")

        usage = payload.get("usage")
        self.last_prompt_tokens = _int_field(usage, "prompt_tokens", "input_tokens")
        self.last_input_limit = _int_field(
            usage,
            "input_token_limit",
            "max_input_tokens",
            "context_length",
            "n_ctx",
        )
        if self.last_input_limit is None:
            self.last_input_limit = _int_field(
                payload,
                "input_token_limit",
                "max_input_tokens",
                "context_length",
                "n_ctx",
            )
        if _reported_truncation(payload) or (
            self.last_prompt_tokens is not None
            and self.last_input_limit is not None
            and self.last_prompt_tokens >= self.last_input_limit
        ):
            raise ExternalEmbeddingError(
                "embedding_input_truncated",
                prompt_tokens=self.last_prompt_tokens,
                input_limit=self.last_input_limit,
            )

        data = payload.get("data")
        if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
            raise ExternalEmbeddingError("embedding_response_invalid")
        vector = data[0].get("embedding")
        if not isinstance(vector, list) or not vector:
            raise ExternalEmbeddingError("embedding_vector_invalid")
        if len(vector) != self._settings.dimensions:
            raise ExternalEmbeddingError("embedding_dimension_mismatch")

        normalized: list[float] = []
        for value in vector:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ExternalEmbeddingError("embedding_vector_invalid")
            component = float(value)
            if not math.isfinite(component):
                raise ExternalEmbeddingError("embedding_non_finite")
            normalized.append(component)
        if not any(component != 0.0 for component in normalized):
            raise ExternalEmbeddingError("embedding_zero_norm")
        return normalized


__all__ = ["ExternalEmbeddingClient", "ExternalEmbeddingError"]
