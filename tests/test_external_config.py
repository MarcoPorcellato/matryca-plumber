"""Explicit local-only configuration for external read-only semantic retrieval."""

from pathlib import Path

import pytest
from pydantic import ValidationError
from src.semantic.external_config import ExternalSemanticSettings


def test_disabled_backend_needs_no_external_settings() -> None:
    settings = ExternalSemanticSettings.from_env(
        {"MATRYCA_LM_BASE_URL": "https://example.org/v1", "OPENAI_API_KEY": "ignored"}
    )
    assert not settings.enabled
    assert settings.base_url == "http://127.0.0.1:8081/v1"


def test_enabled_backend_requires_explicit_identity_and_external_path() -> None:
    with pytest.raises(ValueError, match="required"):
        ExternalSemanticSettings.from_env({"MATRYCA_EXTERNAL_SEMANTIC_ENABLED": "true"})


def test_explicit_profile_resolves_without_creating_directory(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    settings = ExternalSemanticSettings.from_env(
        {
            "MATRYCA_EXTERNAL_SEMANTIC_ENABLED": "true",
            "MATRYCA_EXTERNAL_SEMANTIC_CACHE_PATH": str(cache),
            "MATRYCA_EXTERNAL_SEMANTIC_MODEL": "bge-m3",
            "MATRYCA_EXTERNAL_SEMANTIC_MODEL_REVISION": "sha256:fixture",
            "MATRYCA_EXTERNAL_SEMANTIC_DIMENSIONS": "1024",
            "MATRYCA_EXTERNAL_SEMANTIC_UNIX_SOCKET": str(tmp_path / "embed.sock"),
        }
    )
    assert settings.enabled and settings.dimensions == 1024
    assert settings.cache_root == cache
    assert settings.unix_socket == tmp_path / "embed.sock"
    assert not cache.exists()


@pytest.mark.parametrize(
    "url",
    [
        "https://api.openai.com/v1",
        "http://192.168.1.3/v1",
        "http://localhost.evil.example/v1",
        "http://secret@127.0.0.1/v1",
        "http://127.0.0.1/v1?key=secret",
        "ftp://127.0.0.1/v1",
    ],
)
def test_endpoint_must_be_explicit_loopback_without_credentials(url: str) -> None:
    with pytest.raises(ValidationError):
        ExternalSemanticSettings(base_url=url)


@pytest.mark.parametrize("url", ["http://127.0.0.1:8081/v1", "http://[::1]:8081/v1"])
def test_literal_loopback_endpoints_are_supported(url: str) -> None:
    assert ExternalSemanticSettings(base_url=url).base_url == url


@pytest.mark.parametrize(
    "name,value",
    [
        ("dimensions", 0),
        ("max_input_tokens", 0),
        ("timeout_seconds", float("nan")),
        ("cache_root", Path("relative")),
        ("unix_socket", Path("relative.sock")),
    ],
)
def test_invalid_limits_and_paths_rejected(name: str, value: object) -> None:
    with pytest.raises(ValidationError):
        ExternalSemanticSettings.model_validate({name: value})


def test_unconfigured_revision_cannot_enable_backend() -> None:
    with pytest.raises(ValidationError, match="revision"):
        ExternalSemanticSettings(enabled=True)


def test_invalid_enabled_token_fails_closed() -> None:
    with pytest.raises(ValueError, match="boolean"):
        ExternalSemanticSettings.from_env({"MATRYCA_EXTERNAL_SEMANTIC_ENABLED": "maybe"})


def test_block_chunk_defaults_use_tokens_and_independent_byte_guard() -> None:
    settings = ExternalSemanticSettings()
    assert settings.target_tokens == 320
    assert settings.max_input_tokens == 480
    assert settings.context_tokens == 64
    assert settings.overlap_tokens == 32
    assert settings.max_input_bytes == 32768


@pytest.mark.parametrize(
    "values",
    [
        {"target_tokens": 600, "max_input_tokens": 480},
        {"context_tokens": 480},
        {"overlap_tokens": 320},
        {"max_input_tokens": 0},
        {"max_input_bytes": 0},
    ],
)
def test_invalid_block_chunk_budgets_are_rejected(values: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        ExternalSemanticSettings.model_validate(values)


def test_token_budgets_resolve_from_explicit_environment(tmp_path: Path) -> None:
    settings = ExternalSemanticSettings.from_env(
        {
            "MATRYCA_EXTERNAL_SEMANTIC_ENABLED": "true",
            "MATRYCA_EXTERNAL_SEMANTIC_CACHE_PATH": str(tmp_path / "cache"),
            "MATRYCA_EXTERNAL_SEMANTIC_MODEL": "bge-m3",
            "MATRYCA_EXTERNAL_SEMANTIC_MODEL_REVISION": "fixture",
            "MATRYCA_EXTERNAL_SEMANTIC_DIMENSIONS": "1024",
            "MATRYCA_EXTERNAL_SEMANTIC_TARGET_TOKENS": "256",
            "MATRYCA_EXTERNAL_SEMANTIC_MAX_INPUT_TOKENS": "448",
            "MATRYCA_EXTERNAL_SEMANTIC_CONTEXT_TOKENS": "48",
            "MATRYCA_EXTERNAL_SEMANTIC_OVERLAP_TOKENS": "24",
            "MATRYCA_EXTERNAL_SEMANTIC_MAX_INPUT_BYTES": "16384",
        }
    )
    assert (
        settings.target_tokens,
        settings.max_input_tokens,
        settings.context_tokens,
        settings.overlap_tokens,
        settings.max_input_bytes,
    ) == (256, 448, 48, 24, 16384)
