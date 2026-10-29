"""Explicit, local-only settings for the external semantic read cache."""

from __future__ import annotations

import ipaddress
import os
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ExternalSemanticSettings(BaseModel):
    """Validated settings; constructing them never initializes the cache."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    enabled: bool = False
    cache_root: Path = Field(default_factory=lambda: Path.home() / ".cache" / "matryca-plumber")
    model: str = Field(default="bge-m3", min_length=1, max_length=256)
    model_revision: str = Field(default="unconfigured", min_length=1, max_length=256)
    dimensions: int = Field(default=1024, ge=1, le=8192)
    target_tokens: int = Field(default=320, ge=16, le=8192)
    max_input_tokens: int = Field(default=480, ge=32, le=8192)
    context_tokens: int = Field(default=64, ge=0, le=512)
    overlap_tokens: int = Field(default=32, ge=0, le=512)
    max_input_bytes: int = Field(default=32768, ge=256, le=262144)
    base_url: str = "http://127.0.0.1:8081/v1"
    unix_socket: Path | None = None
    timeout_seconds: float = Field(default=60.0, ge=1.0, le=300.0)

    @field_validator("cache_root", "unix_socket")
    @classmethod
    def absolute_path(cls, value: Path | None) -> Path | None:
        if value is not None and (not value.is_absolute() or ".." in value.parts):
            raise ValueError("external semantic paths must be absolute without parent traversal")
        return value

    @field_validator("base_url")
    @classmethod
    def loopback_endpoint(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path.rstrip("/") != "/v1"
        ):
            raise ValueError("embedding endpoint must be a local /v1 URL without credentials")
        try:
            address = ipaddress.ip_address(parsed.hostname or "")
            _ = parsed.port
        except ValueError as exc:
            raise ValueError("embedding endpoint must use a literal loopback address") from exc
        if not address.is_loopback:
            raise ValueError("embedding endpoint must use a literal loopback address")
        return value.rstrip("/")

    @field_validator("model", "model_revision")
    @classmethod
    def nonempty_identity(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or any(ord(character) < 32 for character in cleaned):
            raise ValueError("embedding identity must be a nonempty single-line value")
        return cleaned

    @model_validator(mode="after")
    def configured_revision(self) -> ExternalSemanticSettings:
        if self.enabled and self.model_revision == "unconfigured":
            raise ValueError("enabled external semantic backend requires a model revision")
        if self.target_tokens > self.max_input_tokens:
            raise ValueError("target_tokens must not exceed max_input_tokens")
        if self.context_tokens >= self.target_tokens:
            raise ValueError("context_tokens must leave content space within target_tokens")
        if self.overlap_tokens >= self.target_tokens - self.context_tokens:
            raise ValueError("overlap_tokens must leave space for forward progress")
        return self

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> ExternalSemanticSettings:
        """Resolve only this backend's settings, without inheriting chat credentials."""
        if env is None:
            env = os.environ
        enabled_raw = env.get("MATRYCA_EXTERNAL_SEMANTIC_ENABLED", "false").strip().lower()
        if enabled_raw in {"", "0", "false", "no", "off"}:
            return cls()
        if enabled_raw not in {"1", "true", "yes", "on"}:
            raise ValueError("invalid external semantic enabled boolean")
        cache = env.get("MATRYCA_EXTERNAL_SEMANTIC_CACHE_PATH", "").strip()
        model = env.get("MATRYCA_EXTERNAL_SEMANTIC_MODEL", "").strip()
        revision = env.get("MATRYCA_EXTERNAL_SEMANTIC_MODEL_REVISION", "").strip()
        dimensions = env.get("MATRYCA_EXTERNAL_SEMANTIC_DIMENSIONS", "").strip()
        if not all((cache, model, revision, dimensions)):
            raise ValueError(
                "external semantic cache path, model, revision and dimensions required"
            )
        socket = env.get("MATRYCA_EXTERNAL_SEMANTIC_UNIX_SOCKET", "").strip()
        return cls(
            enabled=True,
            cache_root=Path(cache),
            model=model,
            model_revision=revision,
            dimensions=int(dimensions),
            target_tokens=int(env.get("MATRYCA_EXTERNAL_SEMANTIC_TARGET_TOKENS", "320") or "320"),
            max_input_tokens=int(
                env.get("MATRYCA_EXTERNAL_SEMANTIC_MAX_INPUT_TOKENS", "480") or "480"
            ),
            context_tokens=int(env.get("MATRYCA_EXTERNAL_SEMANTIC_CONTEXT_TOKENS", "64") or "64"),
            overlap_tokens=int(env.get("MATRYCA_EXTERNAL_SEMANTIC_OVERLAP_TOKENS", "32") or "32"),
            max_input_bytes=int(
                env.get("MATRYCA_EXTERNAL_SEMANTIC_MAX_INPUT_BYTES", "32768") or "32768"
            ),
            base_url=env.get("MATRYCA_EXTERNAL_SEMANTIC_BASE_URL", "").strip()
            or "http://127.0.0.1:8081/v1",
            unix_socket=Path(socket) if socket else None,
            timeout_seconds=float(
                env.get("MATRYCA_EXTERNAL_SEMANTIC_TIMEOUT_SECONDS", "60") or "60"
            ),
        )
