"""Assemble and validate Logseq ``#+BEGIN_QUERY`` … ``#+END_QUERY`` blocks (string-only).

Logseq evaluates the inner region as **EDN** (Clojure literals). This module does not
interpret Datalog; it validates fences, bracket balance (honoring double-quoted strings),
and requires a ``:query`` entry so obviously broken payloads fail before API writes.
"""

from __future__ import annotations

from typing import Final

_BEGIN: Final = "#+BEGIN_QUERY"
_END: Final = "#+END_QUERY"
_BRACKET_PAIRS: Final = {"(": ")", "[": "]", "{": "}"}


def _closing_bracket_matches(stack: list[str], closing: str) -> bool:
    return bool(stack) and _BRACKET_PAIRS[stack.pop()] == closing


def _balanced_brackets(inner: str) -> bool:
    """Check ``()``, ``[]``, ``{}`` nesting, ignoring brackets inside ``"..."`` strings."""
    stack: list[str] = []
    in_string = False
    escape = False
    for ch in inner:
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch in "([{":
            stack.append(ch)
        elif ch in ")]}" and not _closing_bracket_matches(stack, ch):
            return False
    return not stack and not in_string


def validate_advanced_query_edn(inner: str) -> str:
    """Return stripped inner EDN map text, or raise ``ValueError`` with a short reason."""
    body = inner.strip()
    if not body:
        msg = "advanced query body is empty"
        raise ValueError(msg)
    if ":query" not in body:
        msg = "advanced query body must contain a :query clause (substring `:query`)"
        raise ValueError(msg)
    if not _balanced_brackets(body):
        msg = "advanced query body has unbalanced brackets or an unterminated string"
        raise ValueError(msg)
    return body


def wrap_logseq_advanced_query(inner_edn: str) -> str:
    """Wrap validated inner EDN in Logseq advanced-query fences (no leading bullet)."""
    body = validate_advanced_query_edn(inner_edn)
    return f"{_BEGIN}\n{body}\n{_END}"


def resolve_advanced_query_preset(
    preset: str,
    *,
    tag: str | None = None,
) -> str:
    """Return inner EDN for a named preset (used when agents pick a template id).

    Raises:
        ValueError: Unknown preset or missing parameters.
    """
    from . import templates as tpl  # local import avoids circular import at module load

    key = preset.strip().lower().replace("-", "_")
    if key in {"open_markers", "open_tasks", "todos"}:
        return tpl.advanced_query_preset_open_markers()
    if key in {"pages_tagged", "tagged_pages"}:
        if not tag or not tag.strip():
            msg = "preset `pages_tagged` requires a non-empty `tag` argument"
            raise ValueError(msg)
        return tpl.advanced_query_preset_pages_tagged(tag.strip())
    msg = f"unknown advanced query preset: {preset!r}"
    raise ValueError(msg)


__all__ = [
    "resolve_advanced_query_preset",
    "validate_advanced_query_edn",
    "wrap_logseq_advanced_query",
]
