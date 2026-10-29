"""Bounded, read-only extraction of indexable Logseq block text."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from logseq_matryca_parser.logseq_markdown import detect_tab_size_from_markdown

from ..graph.bounded_page_parse import parse_page_text_bounded
from ..graph.markdown_io import mmap_graph_page
from ..graph.page_path import page_title_from_graph_relpath
from ..graph.path_sandbox import assert_path_within_graph, resolved_graph_root
from .external_chunks import SemanticChunk, TokenCounter, build_block_chunks
from .external_config import ExternalSemanticSettings

MAX_SOURCE_PAGE_BYTES = 16 * 1024 * 1024


class ExternalExtractionError(ValueError):
    """Content-free failure while reading or parsing one source page."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SourceSnapshot:
    """Exact UTF-8 source snapshot plus metadata, with body excluded from repr."""

    relative_path: str
    title: str
    source_hash: str
    byte_count: int
    mtime_ns: int
    text: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ExtractedBlock:
    """A parsed block and its complete token-bounded semantic chunks."""

    block_key: str
    citation_id: str
    persisted_uuid: str | None
    block_ordinal: int
    properties: dict[str, Any]
    parent_citation_id: str | None
    ancestor_citation_ids: tuple[str, ...]
    block_content_hash: str
    content: str = field(repr=False)
    chunks: tuple[SemanticChunk, ...] = field(repr=False)


@dataclass(frozen=True, slots=True)
class ExtractedPage:
    """All indexable blocks from one successfully parsed source snapshot."""

    source: SourceSnapshot
    blocks: tuple[ExtractedBlock, ...]
    block_count: int


def split_utf8_chunks(text: str, *, max_bytes: int) -> list[str]:
    """Split text at Unicode character boundaries without dropping any bytes."""
    if max_bytes <= 0:
        raise ValueError("chunk_limit_must_be_positive")
    if not text.strip():
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_bytes = 0
    for character in text:
        character_bytes = len(character.encode("utf-8"))
        if character_bytes > max_bytes:
            raise ValueError("chunk_limit_too_small_for_character")
        if current and current_bytes + character_bytes > max_bytes:
            chunks.append("".join(current))
            current.clear()
            current_bytes = 0
        current.append(character)
        current_bytes += character_bytes
    if current:
        chunks.append("".join(current))
    return chunks


def read_source_snapshot(
    source_path: Path,
    graph_root: str | Path,
    *,
    max_bytes: int = MAX_SOURCE_PAGE_BYTES,
) -> SourceSnapshot:
    """Read one sandboxed Markdown file with original UTF-8 newline bytes intact."""
    root = resolved_graph_root(graph_root)
    try:
        lexical_path = Path(os.path.abspath(source_path.expanduser()))
        relative_path = lexical_path.relative_to(root).as_posix()
    except (OSError, ValueError) as exc:
        raise ExternalExtractionError("source_path_invalid") from exc
    safe_path = assert_path_within_graph(lexical_path, root)
    if safe_path.suffix.lower() != ".md" or not safe_path.is_file():
        raise ExternalExtractionError("source_file_unavailable")
    try:
        stat_before = safe_path.stat()
        if stat_before.st_size > max_bytes:
            raise ExternalExtractionError("source_page_too_large")
        # mmap_graph_page applies the graph path sandbox and preserves CRLF/LF bytes
        # through strict UTF-8 decode/re-encode. The byte limit is checked first.
        if stat_before.st_size == 0:
            text = ""
        else:
            with mmap_graph_page(safe_path, root) as view:
                text = view.decode_utf8(errors="strict")
        raw_bytes = text.encode("utf-8")
        if len(raw_bytes) > max_bytes:
            raise ExternalExtractionError("source_page_too_large")
        stat_after = safe_path.stat()
    except ExternalExtractionError:
        raise
    except (OSError, UnicodeError, ValueError) as exc:
        raise ExternalExtractionError("source_read_error") from exc
    if (stat_before.st_size, stat_before.st_mtime_ns) != (
        stat_after.st_size,
        stat_after.st_mtime_ns,
    ):
        raise ExternalExtractionError("source_changed_during_read")
    try:
        title = page_title_from_graph_relpath(relative_path)
    except (OSError, ValueError) as exc:
        raise ExternalExtractionError("source_path_invalid") from exc
    return SourceSnapshot(
        relative_path=relative_path,
        title=title,
        source_hash=hashlib.sha256(raw_bytes).hexdigest(),
        byte_count=len(raw_bytes),
        mtime_ns=stat_after.st_mtime_ns,
        text=text,
    )


def extract_page_blocks(
    source: SourceSnapshot,
    graph_root: str | Path,
    *,
    settings: ExternalSemanticSettings,
    tokenizer: TokenCounter,
) -> ExtractedPage:
    """Parse one exact source snapshot and chunk every nonempty parsed block."""
    root = resolved_graph_root(graph_root)
    relative_path = Path(source.relative_path)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ExternalExtractionError("source_path_invalid")
    assert_path_within_graph(root / relative_path, root)
    parser_text = source.text.removeprefix("\ufeff")
    parsed = parse_page_text_bounded(
        parser_text,
        mode="stack",
        page_title=source.title,
        tab_size=detect_tab_size_from_markdown(parser_text),
    )
    if not parsed.ok or parsed.page is None:
        failure = "parse_timeout" if parsed.timed_out else "parse_error"
        raise ExternalExtractionError(failure)

    blocks: list[ExtractedBlock] = []
    ordinal = 0
    root_nodes = list(getattr(parsed.page, "root_nodes", []) or [])
    for node, ancestors in _walk_nodes(root_nodes):
        properties, persisted_uuid, citation_id = _node_identity(node)
        content = str(getattr(node, "content", "") or "")
        ancestor_rows = [_node_identity(ancestor) for ancestor in reversed(ancestors)]
        ancestor_citation_ids = tuple(row[2] for row in ancestor_rows)
        ancestor_texts = tuple(
            str(getattr(ancestor, "content", "") or "") for ancestor in reversed(ancestors[-2:])
        )
        chunks = (
            build_block_chunks(
                content,
                page_title=source.title,
                ancestor_texts=ancestor_texts,
                tokenizer=tokenizer,
                settings=settings,
            )
            if content.strip()
            else ()
        )
        if chunks:
            block_key = hashlib.sha256(f"{citation_id}\0{ordinal}".encode()).hexdigest()
            blocks.append(
                ExtractedBlock(
                    block_key=block_key,
                    citation_id=citation_id,
                    persisted_uuid=persisted_uuid,
                    block_ordinal=ordinal,
                    properties=properties,
                    parent_citation_id=(
                        ancestor_citation_ids[0] if ancestor_citation_ids else None
                    ),
                    ancestor_citation_ids=ancestor_citation_ids,
                    block_content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                    content=content,
                    chunks=chunks,
                )
            )
        ordinal += 1
    return ExtractedPage(source=source, blocks=tuple(blocks), block_count=ordinal)


def _walk_nodes(nodes: list[Any]) -> Iterator[tuple[Any, tuple[Any, ...]]]:
    """Depth-first traversal with ancestor nodes from the same parsed AST."""
    pending: list[tuple[Any, tuple[Any, ...]]] = [(node, ()) for node in reversed(nodes)]
    while pending:
        node, ancestors = pending.pop()
        yield node, ancestors
        children = getattr(node, "children", None)
        if children:
            pending.extend((child, ancestors + (node,)) for child in reversed(list(children)))


def _node_identity(node: Any) -> tuple[dict[str, Any], str | None, str]:
    """Copy parser properties and resolve the persisted or synthetic citation ID."""
    props = getattr(node, "properties", None)
    raw_properties: Mapping[str, Any] = props if isinstance(props, Mapping) else {}
    properties = dict(raw_properties)
    raw_persisted = properties.get("id") or getattr(node, "source_uuid", None)
    persisted_value = str(raw_persisted).strip() if raw_persisted else ""
    persisted_uuid = persisted_value or None
    parser_uuid = str(getattr(node, "uuid", "") or "").strip()
    if not parser_uuid and not persisted_uuid:
        raise ExternalExtractionError("block_identity_missing")
    citation_id = persisted_uuid or f"synthetic:{parser_uuid}"
    return properties, persisted_uuid, citation_id


__all__ = [
    "MAX_SOURCE_PAGE_BYTES",
    "ExtractedBlock",
    "ExtractedPage",
    "ExternalExtractionError",
    "SourceSnapshot",
    "extract_page_blocks",
    "read_source_snapshot",
    "split_utf8_chunks",
]
