"""Defensive page-title normalization for MCP tool entrypoints (namespace / casing)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ..graph.alias_index import resolve_existing_page_title
from ..graph.page_path import (
    filename_to_page_title,
    page_title_from_path,
    page_title_to_filename,
)
from ..graph.path_sandbox import resolved_graph_root
from ..rag.matryca_hooks import resolve_logseq_page_md

_UNSAFE_PAGE_REF_MSG = "Invalid page reference: path traversal is not allowed."
_MULTI_SLASH_RE = re.compile(r"/{2,}")


@dataclass(frozen=True)
class NormalizedPageRef:
    """Canonical Logseq page title plus optional agent-facing resolution notes."""

    canonical_title: str
    resolution_notes: list[str] = field(default_factory=list)
    changed: bool = False


def _validate_page_ref_input(sanitized: str) -> None:
    """Reject path traversal and absolute paths before any filesystem lookup."""
    normalized = sanitized.strip().replace("\\", "/")
    if not normalized:
        return
    if normalized.startswith("/"):
        raise ValueError(_UNSAFE_PAGE_REF_MSG)
    if ".." in Path(normalized).parts:
        raise ValueError(_UNSAFE_PAGE_REF_MSG)


def _sanitize_raw_page_input(raw: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    t = raw.strip().replace("\\", "/")
    if t.startswith("pages/"):
        t = t.removeprefix("pages/")
        notes.append("Stripped `pages/` prefix from page reference.")
    while t.endswith(".md"):
        t = t.removesuffix(".md")
        notes.append("Stripped `.md` suffix from page reference.")
    if ".md/" in t or t.endswith(".md"):
        inline_parts = [segment.removesuffix(".md") for segment in t.split("/")]
        inline_clean = "/".join(part for part in inline_parts if part)
        if inline_clean and inline_clean != t:
            notes.append("Removed inline `.md` segments from page namespace.")
            t = inline_clean
    t = _MULTI_SLASH_RE.sub("/", t)
    if "//" in raw.replace("\\", "/") and "/" in t:
        notes.append("Collapsed repeated `/` in page namespace.")
    t = t.strip()
    if t:
        _validate_page_ref_input(t)
    return t, notes


def _semantic_title_candidates(sanitized: str) -> list[str]:
    """Build ordered unique semantic title candidates from agent input."""
    candidates: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        text = value.strip()
        if not text or text in seen:
            return
        seen.add(text)
        candidates.append(text)

    add(sanitized)
    if "___" in sanitized and "/" not in sanitized:
        add(sanitized.replace("___", "/"))
    if "/" in sanitized or "___" not in sanitized:
        add(filename_to_page_title(page_title_to_filename(sanitized)))
    return candidates


def normalize_page_ref(graph_root: Path | str, raw: str) -> NormalizedPageRef | None:
    """Resolve ``raw`` to a canonical on-disk page title when the page exists."""
    sanitized, notes = _sanitize_raw_page_input(raw)
    if not sanitized:
        return None

    root = resolved_graph_root(graph_root)
    for candidate in _semantic_title_candidates(sanitized):
        canonical = resolve_existing_page_title(root, candidate)
        if canonical is not None:
            extra = list(notes)
            if canonical.casefold() != sanitized.casefold():
                extra.append(
                    f"Normalized {raw!r} → {canonical!r} (namespace / case-insensitive match)."
                )
            return NormalizedPageRef(
                canonical_title=canonical,
                resolution_notes=extra,
                changed=bool(extra) or canonical != sanitized,
            )

    for candidate in _semantic_title_candidates(sanitized):
        try:
            path = resolve_logseq_page_md(root, candidate)
        except FileNotFoundError:
            continue
        canonical = page_title_from_path(root, path)
        extra = list(notes)
        extra.append(f"Resolved existing page file for {raw!r} → {canonical!r}.")
        return NormalizedPageRef(
            canonical_title=canonical,
            resolution_notes=extra,
            changed=True,
        )

    return None


def normalize_page_ref_or_raw(graph_root: Path | str, raw: str) -> NormalizedPageRef:
    """Normalize when the page exists; otherwise return sanitized input unchanged."""
    sanitized, notes = _sanitize_raw_page_input(raw)
    resolved = normalize_page_ref(graph_root, raw)
    if resolved is not None:
        return resolved
    return NormalizedPageRef(canonical_title=sanitized, resolution_notes=notes, changed=bool(notes))


def normalize_pipe_page_target(graph_root: Path | str, target: str) -> tuple[str, list[str]]:
    """Normalize the page segment in ``Page Title|block-ref`` targets."""
    parts = [segment.strip() for segment in target.split("|", 1)]
    if len(parts) != 2 or not parts[0]:
        return target, []
    page_norm = normalize_page_ref_or_raw(graph_root, parts[0])
    return f"{page_norm.canonical_title}|{parts[1]}", list(page_norm.resolution_notes)


def format_resolution_notes_footer(notes: list[str]) -> str:
    """Append human-readable normalization notes to MCP text responses."""
    if not notes:
        return ""
    lines = ["", "---", "**Page resolution notes:**"]
    lines.extend(f"- {note}" for note in notes)
    return "\n".join(lines) + "\n"


__all__ = [
    "NormalizedPageRef",
    "UNSAFE_PAGE_REF_MSG",
    "format_resolution_notes_footer",
    "normalize_page_ref",
    "normalize_page_ref_or_raw",
    "normalize_pipe_page_target",
]

UNSAFE_PAGE_REF_MSG = _UNSAFE_PAGE_REF_MSG
