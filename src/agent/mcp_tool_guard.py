"""Outer error boundaries for MCP tool handlers (no raw tracebacks to clients)."""

from __future__ import annotations

import functools
import inspect
from collections.abc import Awaitable, Callable
from typing import Any, cast

from loguru import logger

from ..daemon.config_layer import append_identity_to_mcp_payload
from ..graph.path_sandbox import PathTraversalSecurityError
from ..graph.safety.write_policy import GraphReadOnlyError
from .mcp_telemetry import _matryca_debug_enabled


def _tool_returns_text(fn: Callable[..., Any]) -> bool:
    ann = inspect.signature(fn).return_annotation
    if ann is inspect.Signature.empty:
        return False
    if ann is str:
        return True
    return isinstance(ann, str) and ann.split("[", 1)[0].strip() == "str"


def _public_tool_error_message(exc: Exception) -> str:
    """Return a client-safe error string (full detail only when ``MATRYCA_DEBUG=true``)."""
    if _matryca_debug_enabled():
        return str(exc).strip() or exc.__class__.__name__
    if isinstance(exc, GraphReadOnlyError):
        return str(exc).strip() or exc.__class__.__name__
    if isinstance(exc, PathTraversalSecurityError):
        return str(exc).strip() or exc.__class__.__name__
    if isinstance(exc, ValueError):
        return str(exc).strip() or exc.__class__.__name__
    if isinstance(exc, (OSError, FileNotFoundError)):
        return "Filesystem error; verify LOGSEQ_GRAPH_PATH and file permissions."
    if isinstance(exc, (RuntimeError, ImportError)):
        return f"{exc.__class__.__name__}: operation failed"
    return exc.__class__.__name__


def format_tool_error(
    exc: Exception,
    *,
    as_text: bool,
    code: str = "tool_error",
    hint: str = "Check inputs and environment, then retry.",
) -> str | dict[str, Any]:
    """Map an exception to a concise MCP tool response."""
    message = _public_tool_error_message(exc)
    if as_text:
        return f"Tool failed: {message}"
    return {
        "ok": False,
        "code": code,
        "error": message,
        "hint": hint,
    }


def guard_mcp_tool[F: Callable[..., Awaitable[Any]]](fn: F) -> F:
    """Catch unhandled domain errors and return LLM-safe tool output."""

    returns_text = _tool_returns_text(fn)

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            result = await fn(*args, **kwargs)
            if fn.__name__ == "store_fact":
                return result
            if isinstance(result, (str, dict)):
                return append_identity_to_mcp_payload(result)
            return result
        except PathTraversalSecurityError as exc:
            logger.bind(tool=fn.__name__).warning("MCP tool security error: {}", exc)
            return format_tool_error(
                exc,
                as_text=returns_text,
                code="security_violation",
                hint="Stay within LOGSEQ_GRAPH_PATH and retry with a valid page reference.",
            )
        except GraphReadOnlyError as exc:
            logger.bind(tool=fn.__name__).warning("MCP tool read-only error: {}", exc)
            return format_tool_error(
                exc,
                as_text=returns_text,
                code=exc.code,
                hint="Unset MATRYCA_READ_ONLY or retry with a dry-run-only action.",
            )
        except ValueError as exc:
            logger.bind(tool=fn.__name__).warning("MCP tool validation error: {}", exc)
            return format_tool_error(exc, as_text=returns_text)
        except (OSError, RuntimeError, FileNotFoundError, ImportError) as exc:
            logger.bind(tool=fn.__name__).warning("MCP tool domain error: {}", exc)
            return format_tool_error(exc, as_text=returns_text)
        except Exception as exc:
            logger.bind(tool=fn.__name__).exception("Unhandled MCP tool error")
            return format_tool_error(exc, as_text=returns_text)

    return cast(F, wrapper)


__all__ = ["append_identity_to_mcp_payload", "format_tool_error", "guard_mcp_tool"]
