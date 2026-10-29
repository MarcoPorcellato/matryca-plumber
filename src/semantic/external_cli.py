"""Explicit local maintenance and query commands for the external semantic index."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from typing import Any

from .external import (
    ExternalSemanticError,
    index_graph,
    index_status,
    search_graph,
)
from .external_config import ExternalSemanticSettings


def build_parser() -> argparse.ArgumentParser:
    """Create the small, explicit external semantic CLI surface."""
    parser = argparse.ArgumentParser(prog="matryca-semantic-index")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "status", "search"):
        child = subparsers.add_parser(command)
        child.add_argument("--graph-root", required=True)
        if command == "search":
            child.add_argument("--query", required=True)
            child.add_argument("--limit", type=int, default=15)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one explicit build, status, or search operation."""
    args = build_parser().parse_args(argv)
    try:
        settings = ExternalSemanticSettings.from_env()
        if args.command == "status":
            result = index_status(args.graph_root, settings)
            _emit({"event": "status", **result})
            return 0
        if args.command == "build":
            if not settings.enabled:
                result = index_graph(args.graph_root, settings, _NeverEmbed())
            else:
                from .external_embedding import ExternalEmbeddingClient

                with ExternalEmbeddingClient(settings) as client:
                    result = index_graph(
                        args.graph_root,
                        settings,
                        client,
                        progress=lambda event: _emit({"event": "progress", **event}),
                    )
            _emit({"event": "result", **result})
            return 0 if result.get("snapshot_complete") is True else 2
        if args.command == "search":
            if not settings.enabled:
                result = search_graph(
                    args.graph_root,
                    args.query,
                    settings,
                    _NeverEmbed(),
                    limit=args.limit,
                )
            else:
                from .external_embedding import ExternalEmbeddingClient

                with ExternalEmbeddingClient(settings) as client:
                    result = search_graph(
                        args.graph_root,
                        args.query,
                        settings,
                        client,
                        limit=args.limit,
                    )
            _emit({"event": "result", **result})
            return 0
        raise AssertionError("unreachable command")
    except ExternalSemanticError as exc:
        _emit({"event": "error", "error_code": exc.code})
        return 2
    except Exception as exc:  # noqa: BLE001 - do not print transport/path details
        code = getattr(exc, "code", None)
        safe_code = (
            code
            if isinstance(code, str)
            and code
            and all(
                character.isascii() and (character.isalnum() or character in "_-")
                for character in code
            )
            else "semantic_operation_failed"
        )
        _emit({"event": "error", "error_code": safe_code})
        return 2


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    sys.stdout.flush()


class _NeverEmbed:
    """Sentinel passed only to disabled operations that must make no requests."""

    def embed_text(self, _text: str) -> list[float]:
        raise RuntimeError("embedding_backend_disabled")

    def count_tokens(self, _text: str, *, add_special: bool = True) -> int:
        raise RuntimeError("embedding_backend_disabled")


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_parser", "main"]
