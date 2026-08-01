"""Fail-closed runtime graph write policy and cache configuration."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from ..path_sandbox import resolved_graph_root

_BOOL_TRUE_TOKENS = frozenset({"1", "true", "yes", "on"})
_BOOL_FALSE_TOKENS = frozenset({"0", "false", "no", "off"})
MATRYCA_READ_ONLY_ENV = "MATRYCA_READ_ONLY"
MATRYCA_CACHE_PATH_ENV = "MATRYCA_CACHE_PATH"


class GraphReadOnlyError(PermissionError):
    """Blocked graph write operation under strict read-only policy."""

    code: ClassVar[str] = "graph_read_only"

    def __init__(
        self,
        operation: str,
        *,
        path: str | Path | None = None,
        reason: str,
    ) -> None:
        self.operation = operation
        self.path = None if path is None else str(path)
        self.reason = reason
        super().__init__(f"{operation} blocked by graph read-only policy ({reason})")


@dataclass(frozen=True, slots=True)
class RuntimeWritePolicy:
    """Typed runtime contract for graph-root write decisions."""

    graph_root: Path
    read_only: bool = False
    cache_path: Path | None = None

    def __post_init__(self) -> None:
        try:
            graph_root = resolved_graph_root(self.graph_root)
        except (OSError, RuntimeError) as exc:
            raise GraphReadOnlyError(
                "graph_root",
                path=self.graph_root,
                reason="graph_root_unresolvable",
            ) from exc
        object.__setattr__(self, "graph_root", graph_root)

        if self.cache_path is None:
            return

        expanded_cache = Path(self.cache_path).expanduser()
        if not expanded_cache.is_absolute():
            raise GraphReadOnlyError(
                "cache_path",
                path=self.cache_path,
                reason="cache_path_not_absolute",
            )

        resolved_cache = self._resolve_canonical_path(
            expanded_cache,
            operation="cache_path",
            reason="cache_path_unresolvable",
        )
        if resolved_cache.is_relative_to(graph_root):
            raise GraphReadOnlyError(
                "cache_path",
                path=resolved_cache,
                reason="cache_path_inside_graph",
            )
        object.__setattr__(self, "cache_path", resolved_cache)

    @classmethod
    def from_env(
        cls,
        graph_root: str | Path,
        env: Mapping[str, str] | None = None,
    ) -> RuntimeWritePolicy:
        """Build the policy from environment-backed configuration."""

        if env is None:
            read_only = is_graph_read_only()
            cache_raw = os.environ.get(MATRYCA_CACHE_PATH_ENV, "").strip()
        else:
            read_only = _mapping_bool(env, MATRYCA_READ_ONLY_ENV, default=False)
            cache_raw = env.get(MATRYCA_CACHE_PATH_ENV, "").strip()

        cache_path = None if not cache_raw else Path(cache_raw)
        return cls(graph_root=Path(graph_root), read_only=read_only, cache_path=cache_path)

    def ensure_write_allowed(self, path: str | Path, *, operation: str = "write") -> Path:
        """Return the canonical target path or fail closed under read-only mode."""

        resolved = self._resolve_canonical_path(
            path, operation=operation, reason="path_unresolvable"
        )
        if self.read_only and resolved.is_relative_to(self.graph_root):
            raise GraphReadOnlyError(
                operation,
                path=resolved,
                reason="graph_root_mutation_blocked",
            )
        return resolved

    @staticmethod
    def _resolve_canonical_path(path: str | Path, *, operation: str, reason: str) -> Path:
        try:
            return Path(path).expanduser().resolve(strict=False)
        except (OSError, RuntimeError) as exc:
            raise GraphReadOnlyError(operation, path=path, reason=reason) from exc


def _mapping_bool(env: Mapping[str, str], key: str, *, default: bool) -> bool:
    raw = env.get(key, "").strip().lower()
    if not raw:
        return default
    if raw in _BOOL_TRUE_TOKENS:
        return True
    if raw in _BOOL_FALSE_TOKENS:
        return False
    raise ValueError(f"invalid boolean token for {key}: {env.get(key)!r}")


def is_graph_read_only(env: Mapping[str, str] | None = None) -> bool:
    """Return the validated runtime read-only setting without touching the graph path."""

    source = os.environ if env is None else env
    return _mapping_bool(source, MATRYCA_READ_ONLY_ENV, default=False)


def ensure_graph_write_allowed(
    graph_root: str | Path,
    *,
    operation: str,
) -> None:
    """Apply the environment-backed policy to a graph-root write request."""

    policy = RuntimeWritePolicy.from_env(graph_root)
    policy.ensure_write_allowed(policy.graph_root, operation=operation)


__all__ = [
    "GraphReadOnlyError",
    "RuntimeWritePolicy",
    "ensure_graph_write_allowed",
    "is_graph_read_only",
]
