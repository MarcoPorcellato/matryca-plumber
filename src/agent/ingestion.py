"""Atomic document ingestion into Logseq pages with LOG and GLOSSARY ledgers."""

from __future__ import annotations

import os
import re
import tempfile
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from logseq_matryca_parser import LogosParser
from logseq_matryca_parser.logos_core import LogseqNode, LogseqPage
from logseq_matryca_parser.logseq_markdown import serialize_logseq_page
from loguru import logger

from ..graph.graph_path_validate import validate_logseq_graph_path
from ..graph.link_tag_hop import _extract_inline_tags
from ..graph.markdown_blocks import (
    OCCConflictError,
    OCCSnapshot,
    atomic_write_bytes,
    atomic_write_bytes_if_unchanged,
    graph_safe_page_path,
    read_file_mtime_ns,
)
from ..graph.page_properties import stamp_plumber_authored_page
from ..graph.page_write_lock import page_rmw_lock
from ..graph.path_sandbox import read_graph_file_text
from ..utils.secret_redaction import secret_violations_in_text
from .graph_tool_helpers import graph_missing_text, graph_path_from_env
from .routing_hint import routing_hint_for_write_outline

INGEST_ENV_KEY = "MATRYCA_INGEST_PAGE"
LOG_PAGE_TITLE = "LOG"
GLOSSARY_PAGE_TITLE = "GLOSSARY"

_CAP_TERM = re.compile(r"\b[A-Z][A-Za-z0-9]+(?:[-/][A-Z][A-Za-z0-9]+)+\b")
_MAX_LOG_UUIDS_SHOWN = 12
_MAX_GLOSSARY_TERMS = 48


@dataclass(frozen=True, slots=True)
class IngestionResult:
    """Outcome of ``process_ingestion``."""

    ok: bool
    source_name: str
    destination_page: str
    destination_path: str
    block_uuids: list[str]
    log_path: str | None
    glossary_path: str | None
    files_touched: list[str]
    error: str | None = None


def resolve_ingest_destination_page_title(*, as_of: date | None = None) -> str:
    """Resolve ingest page title from ``MATRYCA_INGEST_PAGE`` or daily ``Ingest/YYYY-MM-DD``."""
    override = os.environ.get("MATRYCA_INGEST_PAGE", "").strip()
    if override:
        return override
    day = as_of or date.today()
    return f"Ingest/{day.isoformat()}"


def _parse_markdown_to_page(raw_markdown: str) -> LogseqPage:
    """Parse markdown via OS temp file (never under graph ``pages/`` — avoids watchdog churn)."""
    scratch: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".md",
            delete=False,
            encoding="utf-8",
        ) as handle:
            handle.write(raw_markdown)
            handle.flush()
            scratch = Path(handle.name)
        return LogosParser().parse_page_file(scratch)
    finally:
        if scratch is not None:
            os.unlink(scratch)


def _assign_fresh_block_ids(node: LogseqNode) -> tuple[LogseqNode, list[str]]:
    """Return a copy of ``node`` with fresh ``id::`` UUIDs on every bullet."""
    block_id = str(uuid.uuid4())
    props = dict(node.properties)
    props["id"] = block_id
    child_nodes: list[LogseqNode] = []
    all_ids = [block_id]
    for child in node.children:
        stamped_child, child_ids = _assign_fresh_block_ids(child)
        child_nodes.append(stamped_child)
        all_ids.extend(child_ids)
    data = node.model_dump()
    data["uuid"] = block_id
    data["source_uuid"] = block_id
    data["synthetic_id"] = False
    data["properties"] = props
    data["children"] = child_nodes
    return LogseqNode.model_validate(data), all_ids


def _stamp_page_roots(page: LogseqPage) -> tuple[LogseqPage, list[str]]:
    stamped_roots: list[LogseqNode] = []
    all_uuids: list[str] = []
    for root in page.root_nodes:
        stamped, ids = _assign_fresh_block_ids(root)
        stamped_roots.append(stamped)
        all_uuids.extend(ids)
    return page.model_copy(update={"root_nodes": stamped_roots}), all_uuids


def _indent_as_children(markdown_body: str, *, extra: str = "  ") -> str:
    lines: list[str] = []
    for line in markdown_body.splitlines():
        if line.strip():
            lines.append(f"{extra}{line}")
        elif lines:
            lines.append("")
    return "\n".join(lines)


def _build_ingest_section(source_name: str, stamped_page: LogseqPage) -> tuple[str, str]:
    """Wrap serialized blocks under a dated ingest container bullet."""
    body = serialize_logseq_page(stamped_page).strip()
    section_uuid = str(uuid.uuid4())
    indented = _indent_as_children(body)
    section = f"- Ingested: **{source_name}**\n  id:: {section_uuid}\n"
    if indented:
        section += f"{indented}\n"
    return section, section_uuid


def _format_log_uuid_clause(block_uuids: list[str]) -> str:
    if len(block_uuids) <= _MAX_LOG_UUIDS_SHOWN:
        return ", ".join(block_uuids)
    head = ", ".join(block_uuids[:_MAX_LOG_UUIDS_SHOWN])
    return f"{head}, … +{len(block_uuids) - _MAX_LOG_UUIDS_SHOWN} more"


def _walk_glossary_node(node: LogseqNode, register: Callable[[str, str], None]) -> None:
    """Recursively register glossary term candidates found under one block."""
    block_uuid = str(node.properties.get("id") or node.uuid or "")
    text = f"{node.content} {node.clean_text}"
    for tag in _extract_inline_tags(text):
        register(tag, block_uuid)
    for match in _CAP_TERM.finditer(text):
        register(match.group(0), block_uuid)
    for child in node.children:
        _walk_glossary_node(child, register)


def _extract_glossary_candidates(
    raw_markdown: str,
    stamped_page: LogseqPage,
) -> list[tuple[str, str]]:
    """Map glossary terms to the first block UUID whose text contains the term."""
    term_to_uuid: dict[str, str] = {}

    def first_root_uuid() -> str:
        if not stamped_page.root_nodes:
            return ""
        root = stamped_page.root_nodes[0]
        return str(root.properties.get("id") or root.uuid or "")

    def register(term: str, block_uuid: str) -> None:
        key = term.strip()
        if not key or key in term_to_uuid or not block_uuid:
            return
        term_to_uuid[key] = block_uuid

    for root in stamped_page.root_nodes:
        _walk_glossary_node(root, register)

    fallback = first_root_uuid()
    for tag in _extract_inline_tags(raw_markdown):
        register(tag, fallback)
    for match in _CAP_TERM.finditer(raw_markdown):
        register(match.group(0), fallback)

    return list(term_to_uuid.items())[:_MAX_GLOSSARY_TERMS]


def _glossary_display_title(term: str) -> str:
    if "/" in term or term.islower():
        return term
    return term.replace("-", "/").title()


def _append_markdown_page(
    graph_root: Path,
    page_title: str,
    section: str,
    *,
    robot_commit_summary: str,
) -> Path:
    """Append a markdown section to ``pages/<title>.md`` with OCC when the file exists."""
    path = graph_safe_page_path(graph_root, page_title)
    path.parent.mkdir(parents=True, exist_ok=True)
    section_text = section.rstrip() + "\n"

    with page_rmw_lock(path):
        prev = read_graph_file_text(path, graph_root, encoding="utf-8") if path.is_file() else ""
        if not prev.strip():
            prev = stamp_plumber_authored_page("")
        new_text = prev.rstrip("\n") + ("\n\n" if prev.strip() else "") + section_text

        if path.is_file():
            occ = OCCSnapshot.capture(path)
            if occ is None:
                msg = f"Could not capture OCC snapshot for {path}"
                raise RuntimeError(msg)
            if occ.drifted():
                raise OCCConflictError(
                    path,
                    baseline_mtime=occ.baseline_mtime,
                    current_mtime=read_file_mtime_ns(path),
                )
            if not atomic_write_bytes_if_unchanged(
                path,
                new_text.encode("utf-8"),
                graph_root=graph_root,
                baseline_mtime=occ.baseline_mtime,
                validate_block_refs=False,
                robot_commit_summary=robot_commit_summary,
            ):
                raise OCCConflictError(
                    path,
                    baseline_mtime=occ.baseline_mtime,
                    current_mtime=read_file_mtime_ns(path),
                )
            occ.refresh_after_own_write()
        else:
            atomic_write_bytes(
                path,
                new_text.encode("utf-8"),
                graph_root=graph_root,
                validate_block_refs=False,
                robot_commit_summary=robot_commit_summary,
            )
    return path


def _build_glossary_section(
    graph_root: Path,
    pairs: list[tuple[str, str]],
) -> str:
    if not pairs:
        return ""
    glossary_path = graph_safe_page_path(graph_root, GLOSSARY_PAGE_TITLE)
    existing = (
        read_graph_file_text(glossary_path, graph_root, encoding="utf-8")
        if glossary_path.is_file()
        else ""
    )
    existing_fold = existing.casefold()
    lines: list[str] = []
    for term, block_uuid in pairs:
        title = _glossary_display_title(term)
        needle = f"[[{title}]]".casefold()
        if needle in existing_fold:
            continue
        lines.append(f"- [[{title}]] -> {{{{embed (({block_uuid}))}}}}")
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def process_ingestion(
    graph_root: Path,
    source_name: str,
    raw_markdown: str,
    *,
    as_of: date | None = None,
) -> IngestionResult:
    """Ingest external markdown into the graph with LOG/GLOSSARY ledger updates."""
    cleaned_name = source_name.strip()
    cleaned_md = raw_markdown.strip()
    if not cleaned_name:
        msg = "source_name must be a non-empty string"
        raise ValueError(msg)
    if not cleaned_md:
        msg = "raw_markdown must be a non-empty string"
        raise ValueError(msg)

    violations = secret_violations_in_text(cleaned_md)
    if violations:
        msg = f"raw_markdown contains forbidden secret patterns: {', '.join(violations)}"
        raise ValueError(msg)

    root = graph_root.expanduser().resolve(strict=False)
    destination_title = resolve_ingest_destination_page_title(as_of=as_of)

    page = _parse_markdown_to_page(cleaned_md)
    if not page.root_nodes:
        msg = "raw_markdown produced no outliner bullets to ingest"
        raise ValueError(msg)

    stamped_page, block_uuids = _stamp_page_roots(page)
    ingest_section, _section_uuid = _build_ingest_section(cleaned_name, stamped_page)

    files_touched: list[str] = []
    dest_path = _append_markdown_page(
        root,
        destination_title,
        ingest_section,
        robot_commit_summary=f"ingest {cleaned_name} -> {destination_title}",
    )
    files_touched.append(str(dest_path.relative_to(root)))

    day_label = (as_of or date.today()).isoformat()
    log_line = (
        f"- [[{day_label}]] - Ingested: **{cleaned_name}** - "
        f"Generated {len(block_uuids)} blocks. "
        f"(UUIDs: {_format_log_uuid_clause(block_uuids)})"
    )
    log_path = _append_markdown_page(
        root,
        LOG_PAGE_TITLE,
        log_line + "\n",
        robot_commit_summary=f"ingest log {cleaned_name}",
    )
    files_touched.append(str(log_path.relative_to(root)))

    glossary_path: str | None = None
    glossary_section = _build_glossary_section(
        root,
        _extract_glossary_candidates(cleaned_md, stamped_page),
    )
    if glossary_section:
        g_path = _append_markdown_page(
            root,
            GLOSSARY_PAGE_TITLE,
            glossary_section,
            robot_commit_summary=f"ingest glossary {cleaned_name}",
        )
        glossary_path = str(g_path.relative_to(root))
        files_touched.append(glossary_path)

    logger.bind(
        source=cleaned_name,
        page=destination_title,
        blocks=len(block_uuids),
    ).info("Atomic ingestion completed")

    return IngestionResult(
        ok=True,
        source_name=cleaned_name,
        destination_page=destination_title,
        destination_path=str(dest_path.relative_to(root)),
        block_uuids=block_uuids,
        log_path=str(log_path.relative_to(root)),
        glossary_path=glossary_path,
        files_touched=files_touched,
    )


async def dispatch_ingest_document(source_name: str, raw_text: str) -> dict[str, Any]:
    """MCP entry: ingest ``raw_text`` from external source ``source_name``."""
    raw = graph_path_from_env()
    if not raw:
        msg = graph_missing_text()
        raise ValueError(msg)
    graph_root = validate_logseq_graph_path(raw)
    result = process_ingestion(graph_root, source_name, raw_text)
    return {
        "ok": result.ok,
        "source_name": result.source_name,
        "destination_page": result.destination_page,
        "destination_path": result.destination_path,
        "block_uuids": result.block_uuids,
        "block_count": len(result.block_uuids),
        "log_path": result.log_path,
        "glossary_path": result.glossary_path,
        "files_touched": result.files_touched,
        "routing_hint": routing_hint_for_write_outline(),
    }


__all__ = [
    "INGEST_ENV_KEY",
    "GLOSSARY_PAGE_TITLE",
    "IngestionResult",
    "LOG_PAGE_TITLE",
    "dispatch_ingest_document",
    "process_ingestion",
    "resolve_ingest_destination_page_title",
]
