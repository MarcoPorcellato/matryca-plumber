"""Lightweight persistent JSON catalog for Matryca Plumber graph scalability."""

from __future__ import annotations

import contextlib
import json
import re
import shutil
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger

from ..utils.bounded_json import BoundedJsonError, read_bounded_json
from .alias_index import build_alias_index, iter_alias_source_paths, page_title_from_path
from .generated_hub_write import write_generated_hub_page
from .json_flock import cross_process_json_flock
from .markdown_blocks import atomic_write_bytes, occ_snapshot
from .markdown_io import MmapTextView, read_graph_page_text
from .path_sandbox import read_graph_file_text

CATALOG_FILENAME = "master_catalog.json"
CATALOG_VERSION = 1
LEGACY_SECONDS_MTIME_CUTOFF = 10_000_000_000
SEMANTIC_INDEX_HEADING = "### Matryca Semantic Index"
SEMANTIC_INDEX_HEADER = f"- {SEMANTIC_INDEX_HEADING}"
MASTER_INDEX_PAGE_TITLE = "Matryca Master Index"
MATRYCA_GENERATED_INDEX_TITLES = frozenset(
    {MASTER_INDEX_PAGE_TITLE, "Matryca Graph Insights"},
)

_SUMMARY_LINE = re.compile(r"^\s*-\s*summary::\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_TAGS_LINE = re.compile(r"^\s*-\s*suggested-tags::\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_TYPE_LINE = re.compile(r"^\s*type::\s*(\S+)\s*$", re.IGNORECASE | re.MULTILINE)
_MARPA_DOMAINS = frozenset({"mappa", "area", "risorsa", "progetto", "archivio"})

_lock = threading.Lock()
_loaded: dict[str, MasterCatalog] = {}
_catalog_mtime_ns: dict[str, int] = {}


class CatalogLoadError(OSError):
    """Raised when ``master_catalog.json`` cannot be read and no safe cache exists."""


def normalize_stored_mtime_ns(stored_mtime: int) -> int:
    """Return ``last_mtime`` as nanoseconds, accepting legacy second values."""
    if abs(stored_mtime) < LEGACY_SECONDS_MTIME_CUTOFF:
        return stored_mtime * 1_000_000_000
    return stored_mtime


def _stored_mtime_matches(stored_mtime: int, mtime_ns: int) -> bool:
    if abs(stored_mtime) < LEGACY_SECONDS_MTIME_CUTOFF:
        return int(mtime_ns // 1_000_000_000) == stored_mtime
    return int(mtime_ns) == stored_mtime


@dataclass(slots=True)
class CatalogEntry:
    """One page row in the master catalog."""

    summary: str = ""
    domain: str = ""
    tags: list[str] = field(default_factory=list)
    last_mtime: int = 0
    orphan: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "domain": self.domain,
            "tags": list(self.tags),
            "last_mtime": self.last_mtime,
            "orphan": self.orphan,
        }

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> CatalogEntry:
        raw_tags = payload.get("tags", [])
        tags = [str(t) for t in raw_tags] if isinstance(raw_tags, list) else []
        return cls(
            summary=str(payload.get("summary", "")),
            domain=str(payload.get("domain", "")),
            tags=tags,
            last_mtime=int(payload.get("last_mtime", 0)),
            orphan=bool(payload.get("orphan", False)),
        )


@dataclass
class MasterCatalog:
    """In-memory master catalog backed by ``.matryca_semantic_cache/master_catalog.json``."""

    graph_root: Path
    version: int = CATALOG_VERSION
    updated_at: str | None = None
    pages: dict[str, CatalogEntry] = field(default_factory=dict)
    alias_to_page: dict[str, str] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)
    persist_allowed: bool = True
    _pending_removals: set[str] = field(default_factory=set, repr=False, compare=False)

    @staticmethod
    def catalog_path(graph_root: Path) -> Path:
        return graph_root / ".matryca_semantic_cache" / CATALOG_FILENAME

    def to_json(self) -> dict[str, Any]:
        with self._lock:
            pages_payload = {title: entry.to_json() for title, entry in sorted(self.pages.items())}
        return {
            "version": self.version,
            "updated_at": self.updated_at,
            "pages": pages_payload,
        }

    @classmethod
    def from_json(cls, graph_root: Path, payload: dict[str, Any]) -> MasterCatalog:
        pages: dict[str, CatalogEntry] = {}
        raw_pages = payload.get("pages", {})
        if isinstance(raw_pages, dict):
            for title, rec in raw_pages.items():
                if isinstance(rec, dict):
                    pages[str(title)] = CatalogEntry.from_json(rec)
        return cls(
            graph_root=graph_root,
            version=int(payload.get("version", CATALOG_VERSION)),
            updated_at=payload.get("updated_at"),
            pages=pages,
        )

    def save(self, *, replace: bool = False) -> None:
        """Persist catalog atomically under the graph root.

        When ``replace`` is false (default), reload disk state under flock and merge
        pending page rows by ``last_mtime`` so concurrent writers do not clobber each
        other. When ``replace`` is true, write ``self.pages`` as the full catalog
        (used after ``prune_missing_pages``).
        """
        if not self.persist_allowed:
            logger.error(
                "Refusing to save master catalog for {}: load did not succeed "
                "(transient I/O or corruption).",
                self.graph_root,
            )
            return
        path = self.catalog_path(self.graph_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            pending = dict(self.pages)
            removals = set(self._pending_removals)
            version = self.version
        updated_at = datetime.now(tz=UTC).isoformat()
        with cross_process_json_flock(path):
            if replace:
                merged_pages = pending
            else:
                disk_pages = _load_catalog_pages_unlocked(path, self.graph_root)
                merged_pages = _merge_catalog_page_deltas(disk_pages, pending)
                for title in removals:
                    merged_pages.pop(title, None)
            payload = {
                "version": version,
                "updated_at": updated_at,
                "pages": {title: entry.to_json() for title, entry in sorted(merged_pages.items())},
            }
            data = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
            atomic_write_bytes(
                path,
                data.encode("utf-8"),
                graph_root=self.graph_root,
                validate_block_refs=False,
            )
        with self._lock:
            self.pages = merged_pages
            self.updated_at = updated_at
            self._pending_removals.clear()
        cache_key = str(self.graph_root.expanduser().resolve(strict=False))
        with _lock, contextlib.suppress(OSError):
            _catalog_mtime_ns[cache_key] = path.stat().st_mtime_ns

    def upsert(self, page_title: str, entry: CatalogEntry) -> None:
        with self._lock:
            self.pages[page_title] = entry

    def get(self, page_title: str) -> CatalogEntry | None:
        with self._lock:
            return self.pages.get(page_title)

    def get_case_insensitive(self, page_title: str) -> tuple[str, CatalogEntry] | None:
        """Return ``(canonical_title, entry)`` matching ``page_title`` without case sensitivity."""
        with self._lock:
            entry = self.pages.get(page_title)
            if entry is not None:
                return page_title, entry
            fold = page_title.casefold()
            for title, row in self.pages.items():
                if title.casefold() == fold:
                    return title, row
            return None

    def rebuild_alias_index(self) -> None:
        """Refresh the in-memory alias map from ``alias::`` frontmatter across the graph."""
        idx = build_alias_index(self.graph_root)
        with self._lock:
            self.alias_to_page = dict(idx.alias_to_page)

    def resolve_page_title(self, page_title: str) -> str | None:
        """Return canonical title when ``page_title`` matches a page or alias (case-insensitive)."""
        from .page_path import resolve_existing_page_title

        return resolve_existing_page_title(self.graph_root, page_title)

    def resolve_alias(self, alias: str) -> str | None:
        """Return canonical page title for a known alias, or ``None``."""
        from .alias_index import normalize_concept_key

        norm = normalize_concept_key(alias)
        if not norm:
            return None
        with self._lock:
            return self.alias_to_page.get(norm)

    def remove(self, page_title: str) -> None:
        with self._lock:
            self.pages.pop(page_title, None)
            self._pending_removals.add(page_title)

    def needs_refresh(self, page_title: str, mtime_ns: int) -> bool:
        """Return True when the on-disk page is newer than the catalog row."""
        with self._lock:
            entry = self.pages.get(page_title)
            if entry is None:
                return True
            return not _stored_mtime_matches(entry.last_mtime, int(mtime_ns))

    def prune_missing_pages(self) -> int:
        """Drop catalog rows and alias mappings for deleted markdown files."""
        live_titles = {
            page_title_from_path(self.graph_root, path)
            for path in iter_alias_source_paths(self.graph_root)
        }
        with self._lock:
            stale = [title for title in self.pages if title not in live_titles]
            for title in stale:
                del self.pages[title]
            alias_purged = 0
            orphan_keys = [
                key for key, title in self.alias_to_page.items() if title not in live_titles
            ]
            for key in orphan_keys:
                del self.alias_to_page[key]
                alias_purged += 1
            return len(stale) + alias_purged


def _catalog_backup_path(catalog_path: Path) -> Path:
    return catalog_path.with_suffix(catalog_path.suffix + ".bak")


def _load_catalog_pages_unlocked(path: Path, root: Path) -> dict[str, CatalogEntry]:
    """Read catalog page rows from disk without acquiring flock."""
    if not path.is_file():
        return {}
    try:
        payload = read_bounded_json(path)
    except BoundedJsonError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return dict(MasterCatalog.from_json(root, payload).pages)


def _merge_catalog_page_deltas(
    disk_pages: dict[str, CatalogEntry],
    pending: dict[str, CatalogEntry],
) -> dict[str, CatalogEntry]:
    """Merge pending rows into disk state without dropping unseen concurrent writers."""
    merged = dict(disk_pages)
    for title, entry in pending.items():
        existing = merged.get(title)
        entry_mtime_ns = normalize_stored_mtime_ns(entry.last_mtime)
        existing_mtime_ns = (
            normalize_stored_mtime_ns(existing.last_mtime) if existing is not None else None
        )
        if existing_mtime_ns is None or entry_mtime_ns >= existing_mtime_ns:
            merged[title] = entry
    return merged


def _quarantine_corrupt_catalog(catalog_path: Path) -> Path:
    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    dest = catalog_path.with_name(f"{catalog_path.name}.corrupt.{stamp}")
    shutil.move(str(catalog_path), str(dest))
    return dest


def _load_catalog_payload_from_disk(path: Path, root: Path) -> MasterCatalog:
    """Parse catalog JSON from disk; restore backup or quarantine on corruption."""
    try:
        with cross_process_json_flock(path):
            payload = read_bounded_json(path)
    except BoundedJsonError as exc:
        msg = str(exc)
        if msg.startswith("Cannot stat") or msg.startswith("Cannot read"):
            raise OSError(msg) from exc
        backup = _catalog_backup_path(path)
        if backup.is_file():
            try:
                with cross_process_json_flock(backup):
                    payload = read_bounded_json(backup)
                logger.warning(
                    "[METADATA CORRUPTION DETECTED] Restored master catalog from backup at {}",
                    backup,
                )
                if isinstance(payload, dict):
                    catalog = MasterCatalog.from_json(root, payload)
                    catalog.persist_allowed = True
                    return catalog
            except BoundedJsonError:
                pass
        try:
            with cross_process_json_flock(path):
                quarantined = _quarantine_corrupt_catalog(path)
            logger.warning(
                "[METADATA CORRUPTION DETECTED] Quarantined malformed catalog to {}",
                quarantined,
            )
        except OSError as move_exc:
            logger.warning(
                "[METADATA CORRUPTION DETECTED] Could not quarantine catalog: {}",
                move_exc,
            )
        catalog = MasterCatalog(graph_root=root, persist_allowed=False)
        return catalog
    if isinstance(payload, dict):
        return MasterCatalog.from_json(root, payload)
    logger.warning("[METADATA CORRUPTION DETECTED] Catalog root is not a JSON object.")
    return MasterCatalog(graph_root=root, persist_allowed=False)


def load_master_catalog(graph_root: Path, *, force_reload: bool = False) -> MasterCatalog:
    """Load catalog into RAM at startup (cached per graph root)."""
    root = graph_root.expanduser().resolve(strict=False)
    key = str(root)
    path = MasterCatalog.catalog_path(root)
    with _lock:
        if not force_reload and key in _loaded:
            cached = _loaded[key]
            if path.is_file():
                try:
                    disk_mtime_ns = path.stat().st_mtime_ns
                except OSError:
                    disk_mtime_ns = None
                else:
                    if _catalog_mtime_ns.get(key) != disk_mtime_ns:
                        force_reload = True
            if not force_reload:
                return cached

        if not path.is_file():
            catalog = MasterCatalog(graph_root=root)
        else:
            try:
                catalog = _load_catalog_payload_from_disk(path, root)
            except OSError as exc:
                if key in _loaded:
                    logger.warning(
                        "Transient catalog read failure for {} — using in-process cache: {}",
                        path,
                        exc,
                    )
                    return _loaded[key]
                msg = f"Could not read master catalog at {path}: {exc}"
                raise CatalogLoadError(msg) from exc
            else:
                if catalog.persist_allowed:
                    backup = _catalog_backup_path(path)
                    try:
                        with cross_process_json_flock(path):
                            shutil.copy2(path, backup)
                    except OSError as copy_exc:
                        logger.debug("Could not refresh catalog backup {}: {}", backup, copy_exc)
        catalog.rebuild_alias_index()
        _loaded[key] = catalog
        if path.is_file():
            try:
                _catalog_mtime_ns[key] = path.stat().st_mtime_ns
            except OSError:
                _catalog_mtime_ns.pop(key, None)
        return catalog


def clear_master_catalog_cache(graph_root: Path | None = None) -> None:
    """Drop in-process catalog cache (tests)."""
    with _lock:
        if graph_root is None:
            _loaded.clear()
            _catalog_mtime_ns.clear()
            return
        key = str(graph_root.expanduser().resolve(strict=False))
        _loaded.pop(key, None)
        _catalog_mtime_ns.pop(key, None)


def unload_master_catalog(graph_root: Path | str) -> bool:
    """Release in-memory catalog for one graph (Phase 1 teardown / RAM budget)."""
    key = str(Path(graph_root).expanduser().resolve(strict=False))
    with _lock:
        return _loaded.pop(key, None) is not None


def _normalize_domain(raw: str) -> str:
    value = raw.strip().lower()
    return value if value in _MARPA_DOMAINS else ""


def _parse_tags(raw: str) -> list[str]:
    tags: list[str] = []
    for chunk in re.split(r"\s+", raw.strip()):
        token = chunk.strip().lstrip("#")
        if token:
            tags.append(token.lower())
    return tags


def extract_catalog_fields_from_mmap(view: MmapTextView) -> CatalogEntry | None:
    """Fast regex read of semantic index metadata from a mmap view."""
    if view.search(SEMANTIC_INDEX_HEADING) is None:
        return None
    return extract_catalog_fields_from_content(view.decode_utf8())


def extract_catalog_fields_from_content(content: str) -> CatalogEntry | None:
    """Fast regex read of an existing ``### Matryca Semantic Index`` block."""
    if SEMANTIC_INDEX_HEADING not in content:
        return None

    summary_match = _SUMMARY_LINE.search(content)
    if summary_match is None:
        return None
    summary = summary_match.group(1).strip()
    if not summary:
        return None

    tags: list[str] = []
    tags_match = _TAGS_LINE.search(content)
    if tags_match:
        tags = _parse_tags(tags_match.group(1))

    domain = ""
    type_match = _TYPE_LINE.search(content)
    if type_match:
        domain = _normalize_domain(type_match.group(1))
    if not domain:
        for line in content.splitlines()[:20]:
            if line.strip().lower().startswith("- type::"):
                domain = _normalize_domain(line.split("::", 1)[1])
                break

    return CatalogEntry(summary=summary, domain=domain, tags=tags)


def entry_from_page_path(graph_root: Path, page_path: Path) -> CatalogEntry | None:
    """Build a catalog entry from on-disk semantic index metadata."""
    if not page_path.is_file():
        return None
    try:
        content = read_graph_page_text(page_path, graph_root, errors="replace")
        mtime_ns = page_path.stat().st_mtime_ns
    except OSError:
        return None

    extracted = extract_catalog_fields_from_content(content)
    if extracted is None:
        return None
    extracted.last_mtime = int(mtime_ns)
    return extracted


def list_stale_page_paths(graph_root: Path, catalog: MasterCatalog) -> list[Path]:
    """Return markdown paths whose mtime differs from the catalog row."""
    stale: list[Path] = []
    for path in iter_alias_source_paths(graph_root):
        title = page_title_from_path(graph_root, path)
        try:
            mtime_ns = path.stat().st_mtime_ns
        except OSError:
            continue
        if catalog.needs_refresh(title, mtime_ns):
            stale.append(path)
    return stale


def build_master_index_markdown(catalog: MasterCatalog) -> str:
    """Compile ``pages/Matryca Master Index.md`` grouped by MARPA domain."""
    domain_order = ["mappa", "area", "risorsa", "progetto", "archivio", ""]
    grouped: dict[str, list[tuple[str, CatalogEntry]]] = {d: [] for d in domain_order}
    for title, entry in catalog.pages.items():
        if title in MATRYCA_GENERATED_INDEX_TITLES:
            continue
        domain = entry.domain if entry.domain in _MARPA_DOMAINS else ""
        grouped[domain].append((title, entry))

    stamp = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "- type:: hub",
        f"- updated:: {stamp}",
        "- # Matryca Master Index",
        "",
        f"_Auto-generated catalog of {len(catalog.pages)} indexed page(s)._",
        "",
    ]

    labels = {
        "mappa": "Mappa — strategic vision",
        "area": "Area — ongoing operations",
        "risorsa": "Risorsa — timeless reference",
        "progetto": "Progetto — time-bounded initiatives",
        "archivio": "Archivio — closed or dormant",
        "": "Uncategorized",
    }

    for domain in domain_order:
        rows = sorted(grouped[domain], key=lambda item: item[0].lower())
        if not rows:
            continue
        lines.append(f"- ## {labels[domain]}")
        lines.append("  collapsed:: true")
        for title, entry in rows:
            summary = entry.summary.strip()
            if summary:
                lines.append(f"  - [[{title}]] — {summary}")
            else:
                lines.append(f"  - [[{title}]]")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def master_index_page_path(graph_root: Path) -> Path:
    """Return the on-disk path for the compiled master index page."""
    return graph_root / "pages" / f"{MASTER_INDEX_PAGE_TITLE}.md"


def is_bootstrap_catalog_complete(graph_root: Path) -> bool:
    """Return True when every scannable page has a catalog summary and the master index exists."""
    root = graph_root.expanduser().resolve(strict=False)
    if not master_index_page_path(root).is_file():
        return False

    catalog = load_master_catalog(root)
    if not catalog.pages:
        return False

    for path in iter_alias_source_paths(root):
        title = page_title_from_path(root, path)
        if title in MATRYCA_GENERATED_INDEX_TITLES:
            continue
        try:
            content = read_graph_file_text(path, root, errors="replace")
            mtime_ns = path.stat().st_mtime_ns
        except OSError:
            return False
        if not content.strip():
            continue
        entry = catalog.get(title)
        if entry is None or not entry.summary.strip():
            return False
        if catalog.needs_refresh(title, mtime_ns):
            return False
    return True


def write_master_index_page(graph_root: Path, catalog: MasterCatalog) -> Path:
    """Write the compiled master index page under ``pages/``."""
    from .path_sandbox import graph_safe_page_path

    path = graph_safe_page_path(graph_root, MASTER_INDEX_PAGE_TITLE)
    baseline_mtime = occ_snapshot(path) if path.is_file() else None
    md = build_master_index_markdown(catalog)
    result = write_generated_hub_page(
        graph_root,
        MASTER_INDEX_PAGE_TITLE,
        md,
        baseline_mtime=baseline_mtime,
        robot_commit_summary="recompiled Matryca Master Index hub page",
    )
    return result.path


__all__ = [
    "CATALOG_FILENAME",
    "CatalogLoadError",
    "CatalogEntry",
    "MASTER_INDEX_PAGE_TITLE",
    "MATRYCA_GENERATED_INDEX_TITLES",
    "MasterCatalog",
    "SEMANTIC_INDEX_HEADER",
    "SEMANTIC_INDEX_HEADING",
    "build_master_index_markdown",
    "clear_master_catalog_cache",
    "entry_from_page_path",
    "extract_catalog_fields_from_content",
    "is_bootstrap_catalog_complete",
    "list_stale_page_paths",
    "load_master_catalog",
    "unload_master_catalog",
    "master_index_page_path",
    "normalize_stored_mtime_ns",
    "write_master_index_page",
]
