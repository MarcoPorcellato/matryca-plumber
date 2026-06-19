"""In-graph Telos & AI Constraints identity layer (read, inject, refresh)."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from logseq_matryca_parser.logos_core import LogseqNode, LogseqPage
from loguru import logger

from ..graph.page_path import page_title_to_filename, resolve_existing_page_title
from .ast_cache import get_graph_ast_cache

_IDENTITY_SECTION_MAX_BYTES = 8 * 1024
_IDENTITY_TOTAL_MAX_BYTES = 16 * 1024

_READ_PAGE_CANDIDATES = ("matryca/config", "matryca-config")
WRITE_PAGE_TITLE = "matryca-config"
CONSTRAINTS_HEADING = "AI Constraints"
TELOS_HEADING = "Telos"

_store_lock = threading.Lock()
_stores: dict[str, IdentityConfigStore] = {}


@dataclass(frozen=True, slots=True)
class IdentityConfig:
    """Parsed Telos and AI Constraints from the identity config page."""

    telos: str
    constraints: str
    source_page: str | None


def _env_identity_page_override() -> str | None:
    raw = os.environ.get("MATRYCA_IDENTITY_CONFIG_PAGE", "").strip()
    return raw or None


def _cap_section(text: str, max_bytes: int) -> str:
    encoded = text.encode()
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", errors="ignore").rstrip()


def _normalize_heading_label(node: LogseqNode) -> str:
    label = (node.clean_text or "").strip()
    if label:
        return label
    content = (node.content or "").strip()
    if content.startswith("#"):
        return content.lstrip("#").strip()
    return content


def _heading_matches(node: LogseqNode, expected: str) -> bool:
    return _normalize_heading_label(node).casefold() == expected.casefold()


def _collect_subtree_text(node: LogseqNode) -> str:
    parts: list[str] = []
    for child in node.children:
        body = (child.clean_text or child.content or "").strip()
        if body and not body.lower().startswith("id::"):
            parts.append(body)
        nested = _collect_subtree_text(child)
        if nested:
            parts.append(nested)
    return "\n".join(parts).strip()


def _extract_section(page: LogseqPage, heading: str) -> str:
    for root in page.root_nodes:
        if _heading_matches(root, heading):
            return _cap_section(_collect_subtree_text(root), _IDENTITY_SECTION_MAX_BYTES)
    return ""


def _parse_identity_from_page(page: LogseqPage, *, page_title: str) -> IdentityConfig:
    telos = _extract_section(page, TELOS_HEADING)
    constraints = _extract_section(page, CONSTRAINTS_HEADING)
    combined = f"{telos}\n{constraints}".encode()
    if len(combined) > _IDENTITY_TOTAL_MAX_BYTES:
        constraints = _cap_section(
            constraints,
            max(0, _IDENTITY_TOTAL_MAX_BYTES - len(telos.encode()) - 1),
        )
    return IdentityConfig(telos=telos, constraints=constraints, source_page=page_title)


def resolve_identity_read_page_title(graph_root: Path) -> str | None:
    """Return the canonical page title used for reading Telos/Constraints."""
    override = _env_identity_page_override()
    if override:
        resolved = resolve_existing_page_title(graph_root, override)
        return resolved or override
    for candidate in _READ_PAGE_CANDIDATES:
        resolved = resolve_existing_page_title(graph_root, candidate)
        if resolved:
            return resolved
    return None


def resolve_identity_config_path(graph_root: Path, *, for_write: bool = False) -> Path:
    """Resolve on-disk path for the identity config page."""
    root = graph_root.expanduser().resolve(strict=False)
    if for_write:
        title = WRITE_PAGE_TITLE
    else:
        title = resolve_identity_read_page_title(root) or WRITE_PAGE_TITLE
    return root / "pages" / page_title_to_filename(title)


def identity_config_page_paths(graph_root: Path) -> frozenset[Path]:
    """All markdown paths that may hold identity config (for watcher/hooks)."""
    root = graph_root.expanduser().resolve(strict=False)
    paths = {root / "pages" / page_title_to_filename(title) for title in _READ_PAGE_CANDIDATES}
    override = _env_identity_page_override()
    if override:
        paths.add(root / "pages" / page_title_to_filename(override))
    return frozenset(p.resolve(strict=False) for p in paths)


def is_identity_config_path(graph_root: Path, path: Path) -> bool:
    """Return whether ``path`` is a known identity config markdown file."""
    try:
        resolved = path.expanduser().resolve(strict=False)
    except OSError:
        return False
    return resolved in identity_config_page_paths(graph_root)


class IdentityConfigStore:
    """Thread-safe in-memory Telos/Constraints for a graph root."""

    def __init__(self, graph_root: Path) -> None:
        self.graph_root = graph_root.expanduser().resolve(strict=False)
        self._lock = threading.RLock()
        self._config = IdentityConfig(telos="", constraints="", source_page=None)
        self._source_mtime: int | None = None

    def _config_file_mtime(self) -> int | None:
        path = resolve_identity_config_path(self.graph_root, for_write=False)
        if not path.is_file():
            return None
        try:
            return path.stat().st_mtime_ns
        except OSError:
            return None

    def reload_if_stale(self, *, force: bool = False) -> None:
        """Reload identity from disk when the config page mtime changes."""
        mtime = self._config_file_mtime()
        with self._lock:
            if not force and mtime is not None and mtime == self._source_mtime:
                return
            if mtime is None:
                self._config = IdentityConfig(telos="", constraints="", source_page=None)
                self._source_mtime = None
                return
            self._config = self._load_from_graph()
            self._source_mtime = mtime

    def _load_from_graph(self) -> IdentityConfig:
        page_title = resolve_identity_read_page_title(self.graph_root)
        if page_title is None:
            return IdentityConfig(telos="", constraints="", source_page=None)
        cache = get_graph_ast_cache(self.graph_root)
        graph = cache.get_graph()
        page = graph.pages.get(page_title)
        if page is None:
            logger.bind(page=page_title).debug("Identity config page missing from graph index")
            return IdentityConfig(telos="", constraints="", source_page=page_title)
        return _parse_identity_from_page(page, page_title=page_title)

    def get(self) -> IdentityConfig:
        """Return cached identity, reloading when the config file changed."""
        self.reload_if_stale()
        with self._lock:
            return self._config

    def format_system_section(self) -> str:
        """Markdown block appended to LLM system prompts and MCP tool output."""
        cfg = self.get()
        if not cfg.telos.strip() and not cfg.constraints.strip():
            return ""
        parts: list[str] = []
        if cfg.telos.strip():
            parts.append(f"[MATRYCA IDENTITY — Telos]\n{cfg.telos.strip()}")
        if cfg.constraints.strip():
            parts.append(f"[MATRYCA IDENTITY — AI Constraints]\n{cfg.constraints.strip()}")
        return "\n\n".join(parts)


def get_identity_store(graph_root: str | Path) -> IdentityConfigStore:
    """Process singleton keyed by resolved graph root."""
    key = str(Path(graph_root).expanduser().resolve(strict=False))
    with _store_lock:
        store = _stores.get(key)
        if store is None:
            store = IdentityConfigStore(Path(key))
            _stores[key] = store
        return store


def clear_identity_config_stores() -> None:
    """Drop all identity stores (tests)."""
    with _store_lock:
        _stores.clear()
    _resolved_graph_root_from_env.cache_clear()


def clear_identity_env_cache() -> None:
    """Clear cached ``LOGSEQ_GRAPH_PATH`` resolution (tests)."""
    _resolved_graph_root_from_env.cache_clear()


def refresh_identity_config(graph_root: Path, path: Path) -> None:
    """Force identity reload when an identity config page was written."""
    if is_identity_config_path(graph_root, path):
        get_identity_store(graph_root).reload_if_stale(force=True)


@lru_cache(maxsize=1)
def _resolved_graph_root_from_env() -> Path | None:
    raw = os.environ.get("LOGSEQ_GRAPH_PATH", "").strip()
    if not raw:
        return None
    try:
        from ..graph.graph_path_validate import validate_logseq_graph_path

        return validate_logseq_graph_path(raw)
    except ValueError:
        return None


def inject_identity_into_system_prompt(
    system_prompt: str,
    *,
    graph_root: Path | None = None,
) -> str:
    """Append in-graph Telos/Constraints when configured (idempotent marker check)."""
    if "[MATRYCA IDENTITY —" in system_prompt:
        return system_prompt
    root = graph_root or _resolved_graph_root_from_env()
    if root is None:
        return system_prompt
    section = get_identity_store(root).format_system_section()
    if not section:
        return system_prompt
    return f"{system_prompt.rstrip()}\n\n{section}"


def append_identity_to_mcp_payload(result: str | dict[str, object]) -> str | dict[str, object]:
    """Append identity context to MCP tool responses for host agents."""
    root = _resolved_graph_root_from_env()
    if root is None:
        return result
    section = get_identity_store(root).format_system_section()
    if not section:
        return result
    marker = "<!-- matryca_identity:"
    if isinstance(result, str):
        if marker in result:
            return result
        return f"{result.rstrip()}\n\n{section}\n\n{marker} present -->\n"
    payload = dict(result)
    if marker in str(payload.get("identity_context", "")):
        return payload
    existing = str(payload.get("identity_context", "")).strip()
    payload["identity_context"] = f"{existing}\n\n{section}".strip() if existing else section
    hint = payload.get("routing_hint")
    if isinstance(hint, str) and marker not in hint:
        payload["routing_hint"] = f"{hint}\n{marker} present -->"
    return payload


def find_constraints_heading_node(graph_root: Path) -> tuple[LogseqPage, LogseqNode] | None:
    """Locate the AI Constraints heading on the write-target config page."""
    cache = get_graph_ast_cache(graph_root)
    graph = cache.get_graph()
    page = graph.pages.get(WRITE_PAGE_TITLE)
    if page is None:
        return None
    for root in page.root_nodes:
        if _heading_matches(root, CONSTRAINTS_HEADING):
            return page, root
    return None


__all__ = [
    "CONSTRAINTS_HEADING",
    "IdentityConfig",
    "IdentityConfigStore",
    "TELOS_HEADING",
    "WRITE_PAGE_TITLE",
    "append_identity_to_mcp_payload",
    "clear_identity_config_stores",
    "clear_identity_env_cache",
    "find_constraints_heading_node",
    "get_identity_store",
    "identity_config_page_paths",
    "inject_identity_into_system_prompt",
    "is_identity_config_path",
    "refresh_identity_config",
    "resolve_identity_config_path",
    "resolve_identity_read_page_title",
]
