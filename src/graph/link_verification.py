"""Zero-LLM link rot and missing-asset hygiene (GitHub #15).

Extracts URLs and local asset paths during page scans, verifies them asynchronously,
and flags blocks with ``dead-link::`` / ``missing-asset::`` after repeated failures.
Registry sidecar: ``.matryca_link_registry.json`` at the graph root (ephemeral queue only).
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import urlparse

import httpx
from loguru import logger

from ..utils.bounded_json import BoundedJsonError, read_bounded_json
from .global_fence_scanner import compute_page_protected_line_indices
from .json_flock import cross_process_json_flock
from .markdown_blocks import (
    atomic_write_bytes,
    atomic_write_bytes_if_unchanged,
    block_property_insert_index,
    bullet_indent_unit,
    file_mtime_drifted,
    locate_block_by_uuid,
    occ_snapshot,
    occ_verify_before_write,
    strip_lines_for_match,
)
from .mldoc_properties import parse_logseq_property_line
from .page_write_lock import page_rmw_lock
from .path_sandbox import (
    PathTraversalSecurityError,
    is_resolved_path_within_graph,
    read_graph_file_text,
    resolve_graph_relative_key,
)

LINK_REGISTRY_FILENAME = ".matryca_link_registry.json"
REGISTRY_VERSION = 1

_URL_RE = re.compile(r"https?://[^\s\)\]>\"']+", re.IGNORECASE)
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
_ASSET_INLINE_RE = re.compile(r"(?:^|[\s(])(assets/[^\s\)\]>\"']+)", re.IGNORECASE)
_BULLET_RE = re.compile(r"^(\s*)[-*+]\s+(.*)$")
_ID_LINE_RE = re.compile(r"^\s*id::\s+([0-9a-f-]{36})\s*$", re.IGNORECASE)
_DEAD_LINK_PROP = re.compile(r"^\s*dead-link::", re.IGNORECASE)
_MISSING_ASSET_PROP = re.compile(r"^\s*missing-asset::", re.IGNORECASE)
_HEAD_INCONCLUSIVE = frozenset({401, 403, 405, 501})
_HEAD_TRY_GET_STATUSES = _HEAD_INCONCLUSIVE | {404}
_MAX_VERIFY_ERRORS = 50
_GET_BODY_READ_CAP_BYTES = 65_536

LinkKind = Literal["url", "asset"]


def link_registry_path(graph_root: Path) -> Path:
    return graph_root.expanduser().resolve() / LINK_REGISTRY_FILENAME


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def link_verify_enabled() -> bool:
    return _env_bool("MATRYCA_LINK_VERIFY_ENABLED", True)


def link_verify_strikes_threshold() -> int:
    raw = os.environ.get("MATRYCA_LINK_VERIFY_STRIKES", "2").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 2


def link_verify_batch_size() -> int:
    raw = os.environ.get("MATRYCA_LINK_VERIFY_BATCH", "25").strip()
    try:
        return max(1, min(200, int(raw)))
    except ValueError:
        return 25


def link_verify_timeout_seconds() -> float:
    raw = os.environ.get("MATRYCA_LINK_VERIFY_TIMEOUT", "8").strip()
    try:
        return max(1.0, min(60.0, float(raw)))
    except ValueError:
        return 8.0


@dataclass
class LinkRegistryEntry:
    kind: LinkKind
    target: str
    page_relpath: str
    block_uuid: str
    strikes: int = 0
    last_status: int | None = None
    last_checked_at: str | None = None
    flagged: bool = False

    def registry_key(self) -> str:
        return f"{self.page_relpath}|{self.block_uuid}|{self.kind}|{self.target}"

    def to_json(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "target": self.target,
            "page_relpath": self.page_relpath,
            "block_uuid": self.block_uuid,
            "strikes": self.strikes,
            "last_status": self.last_status,
            "last_checked_at": self.last_checked_at,
            "flagged": self.flagged,
        }

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> LinkRegistryEntry:
        return cls(
            kind=cast(LinkKind, payload.get("kind", "url")),
            target=str(payload.get("target", "")),
            page_relpath=str(payload.get("page_relpath", "")),
            block_uuid=str(payload.get("block_uuid", "")),
            strikes=int(payload.get("strikes", 0)),
            last_status=payload.get("last_status"),
            last_checked_at=payload.get("last_checked_at"),
            flagged=bool(payload.get("flagged", False)),
        )


@dataclass
class LinkVerificationCycleResult:
    checked: int = 0
    dead_urls: int = 0  # newly failing URL checks (excludes already-flagged rows)
    missing_assets: int = 0  # newly failing asset checks (excludes already-flagged rows)
    flagged_blocks: int = 0
    flagged_url_blocks: int = 0
    flagged_asset_blocks: int = 0
    errors: list[str] = field(default_factory=list)


def _load_registry_unlocked(path: Path) -> dict[str, LinkRegistryEntry]:
    if not path.is_file():
        return {}
    try:
        payload = read_bounded_json(path)
    except (BoundedJsonError, OSError) as exc:
        logger.warning("Link registry unreadable: {}", exc)
        return {}
    entries_raw = payload.get("entries", {})
    if not isinstance(entries_raw, dict):
        return {}
    out: dict[str, LinkRegistryEntry] = {}
    for key, item in entries_raw.items():
        if not isinstance(item, dict):
            continue
        entry = LinkRegistryEntry.from_json(item)
        if _safe_page_path(path.parent, entry.page_relpath) is None:
            logger.warning(
                "Link registry entry dropped (invalid page_relpath): {}",
                entry.page_relpath,
            )
            continue
        out[str(key)] = entry
    return out


def _save_registry_unlocked(path: Path, entries: dict[str, LinkRegistryEntry]) -> None:
    payload = {
        "version": REGISTRY_VERSION,
        "updated_at": datetime.now(tz=UTC).isoformat(),
        "entries": {key: entry.to_json() for key, entry in entries.items()},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    atomic_write_bytes(path, data, graph_root=path.parent)


def load_link_registry(graph_root: Path) -> dict[str, LinkRegistryEntry]:
    path = link_registry_path(graph_root)
    with cross_process_json_flock(path):
        return _load_registry_unlocked(path)


def save_link_registry(graph_root: Path, entries: dict[str, LinkRegistryEntry]) -> None:
    path = link_registry_path(graph_root)
    with cross_process_json_flock(path):
        _save_registry_unlocked(path, entries)


def _persist_checked_registry_updates(
    graph_root: Path,
    updates: dict[str, LinkRegistryEntry],
    checked_keys: set[str],
) -> None:
    """Merge verification results into the on-disk registry without clobbering concurrent merges."""
    if not checked_keys:
        return
    path = link_registry_path(graph_root)
    with cross_process_json_flock(path):
        fresh = _load_registry_unlocked(path)
        for key in checked_keys:
            if key in updates:
                fresh[key] = updates[key]
        _save_registry_unlocked(path, fresh)


_INVALID_ASSET = ".matryca_invalid_asset"


def _safe_page_path(graph_root: Path, page_relpath: str) -> Path | None:
    """Resolve a registry page key under the graph root, or None when invalid."""
    if not page_relpath.strip():
        return None
    try:
        return resolve_graph_relative_key(graph_root, page_relpath)
    except PathTraversalSecurityError:
        return None


def _resolve_asset_path(graph_root: Path, page_path: Path, asset_ref: str) -> Path:
    ref = asset_ref.strip()
    if ref.startswith("/"):
        return graph_root / _INVALID_ASSET
    if ref.startswith("assets/"):
        candidate = (graph_root / ref).resolve()
    else:
        candidate = (page_path.parent / ref).resolve()
    if not is_resolved_path_within_graph(candidate, graph_root):
        return graph_root / _INVALID_ASSET
    return candidate


def _block_has_property(
    stripped: list[str],
    bullet_idx: int,
    block_end: int,
    pattern: re.Pattern[str],
) -> bool:
    for i in range(bullet_idx + 1, min(block_end, len(stripped))):
        if pattern.match(stripped[i]):
            return True
    return False


def _page_relpath(graph_root: Path, page_path: Path) -> str | None:
    try:
        return page_path.relative_to(graph_root).as_posix()
    except ValueError:
        return None


def extract_links_from_page(
    graph_root: Path,
    page_path: Path,
    content: str,
) -> list[LinkRegistryEntry]:
    """Passive extract: URLs and asset paths anchored to block UUIDs."""
    if not content.strip():
        return []
    page_relpath = _page_relpath(graph_root, page_path)
    if page_relpath is None:
        return []

    protected = compute_page_protected_line_indices(content)
    lines = content.splitlines(keepends=True)
    if not lines:
        lines = [""]
    stripped = strip_lines_for_match(lines)

    entries: list[LinkRegistryEntry] = []
    seen: set[str] = set()

    for idx, line in enumerate(stripped):
        if idx in protected:
            continue
        id_match = _ID_LINE_RE.match(line.rstrip("\n"))
        if not id_match:
            continue
        block_uuid = id_match.group(1).strip()
        located = locate_block_by_uuid(stripped, block_uuid)
        if located is None:
            continue
        bullet_idx, _id_idx, block_end = located
        if bullet_idx in protected:
            continue

        bullet_match = _BULLET_RE.match(stripped[bullet_idx].rstrip("\n"))
        if not bullet_match:
            continue
        block_text_parts: list[str] = [bullet_match.group(2)]
        for i in range(bullet_idx + 1, min(block_end, len(stripped))):
            if _BULLET_RE.match(stripped[i].rstrip("\n")):
                break
            prop = parse_logseq_property_line(stripped[i].rstrip("\n"))
            if prop is not None:
                continue
            if _ID_LINE_RE.match(stripped[i].rstrip("\n")):
                continue
            block_text_parts.append(stripped[i].rstrip("\n"))
        block_blob = "\n".join(block_text_parts)

        for url_match in _URL_RE.finditer(block_blob):
            url = url_match.group(0).rstrip(".,;)")
            if not urlparse(url).scheme:
                continue
            entry = LinkRegistryEntry(
                kind="url",
                target=url,
                page_relpath=page_relpath,
                block_uuid=block_uuid,
            )
            key = entry.registry_key()
            if key not in seen:
                seen.add(key)
                entries.append(entry)

        asset_candidates: list[str] = []
        for img_match in _IMAGE_RE.finditer(block_blob):
            asset_candidates.append(img_match.group(1).strip())
        for asset_match in _ASSET_INLINE_RE.finditer(block_blob):
            asset_candidates.append(asset_match.group(1).strip())

        for asset_ref in asset_candidates:
            if asset_ref.startswith("http://") or asset_ref.startswith("https://"):
                continue
            entry = LinkRegistryEntry(
                kind="asset",
                target=asset_ref,
                page_relpath=page_relpath,
                block_uuid=block_uuid,
            )
            key = entry.registry_key()
            if key not in seen:
                seen.add(key)
                entries.append(entry)

    return entries


def merge_page_links_into_registry(
    graph_root: Path,
    page_path: Path,
    content: str,
) -> int:
    """Upsert extracted links for one page; drop registry rows removed from the page."""
    new_entries = extract_links_from_page(graph_root, page_path, content)
    page_relpath = _page_relpath(graph_root, page_path)
    if page_relpath is None:
        return 0

    path = link_registry_path(graph_root)
    new_keys = {entry.registry_key() for entry in new_entries}
    with cross_process_json_flock(path):
        registry = _load_registry_unlocked(path)
        stale = [
            key
            for key, entry in registry.items()
            if entry.page_relpath == page_relpath and key not in new_keys
        ]
        for key in stale:
            del registry[key]
        if not new_entries:
            _save_registry_unlocked(path, registry)
            return 0
        for entry in new_entries:
            key = entry.registry_key()
            prior = registry.get(key)
            if prior is not None:
                entry.strikes = prior.strikes
                entry.flagged = prior.flagged
                entry.last_status = prior.last_status
                entry.last_checked_at = prior.last_checked_at
            registry[key] = entry
        _save_registry_unlocked(path, registry)
    return len(new_entries)


async def _head_url(client: httpx.AsyncClient, url: str) -> int | None:
    try:
        response = await client.head(url, follow_redirects=True)
        return response.status_code
    except httpx.HTTPError:
        return None


async def _get_url(client: httpx.AsyncClient, url: str) -> int | None:
    """Bounded GET (range/limit) for HEAD fallbacks without downloading large bodies."""
    headers = {"Range": f"bytes=0-{_GET_BODY_READ_CAP_BYTES - 1}"}
    try:
        response = await client.get(url, follow_redirects=True, headers=headers)
        try:
            await response.aread()
        finally:
            await response.aclose()
        return response.status_code
    except httpx.HTTPError:
        return None


async def _verify_url_status(client: httpx.AsyncClient, url: str) -> int | None:
    """HEAD first; fall back to GET when HEAD is inconclusive or fails."""
    status = await _head_url(client, url)
    if status is not None and status < 400:
        return status
    if status is None or status in _HEAD_TRY_GET_STATUSES:
        get_status = await _get_url(client, url)
        if get_status is not None:
            return get_status
    return status


def _append_verify_error(result: LinkVerificationCycleResult, message: str) -> None:
    if len(result.errors) < _MAX_VERIFY_ERRORS:
        result.errors.append(message)


def _asset_missing(graph_root: Path, page_relpath: str, asset_ref: str) -> bool:
    page_path = _safe_page_path(graph_root, page_relpath)
    if page_path is None or not page_path.is_file():
        return True
    resolved = _resolve_asset_path(graph_root, page_path, asset_ref)
    return not resolved.is_file()


def _url_check_failed(status: int | None) -> bool:
    return status is None or status >= 400


def _recover_flagged_entry(
    graph_root: Path,
    entry: LinkRegistryEntry,
    *,
    property_name: str,
) -> None:
    """Clear on-graph hygiene only when OCC write succeeds; then unflag registry."""
    if not entry.flagged:
        entry.strikes = 0
        return
    if clear_block_hygiene_property(
        graph_root,
        entry.page_relpath,
        entry.block_uuid,
        property_name,
    ):
        entry.strikes = 0
        entry.flagged = False
    # If clear fails, keep flagged + strikes so registry matches on-graph properties.


async def verify_registry_batch(
    graph_root: Path,
    entries: dict[str, LinkRegistryEntry],
    *,
    batch_size: int | None = None,
) -> LinkVerificationCycleResult:
    """Verify up to ``batch_size`` entries (unflagged first, then flagged for recovery)."""
    result = LinkVerificationCycleResult()
    if not entries:
        return result

    batch_n = batch_size if batch_size is not None else link_verify_batch_size()
    threshold = link_verify_strikes_threshold()
    timeout = link_verify_timeout_seconds()
    unflagged = [e for e in entries.values() if not e.flagged]
    flagged = [e for e in entries.values() if e.flagged]
    pending = (unflagged + flagged)[:batch_n]
    if not pending:
        return result

    checked_keys: set[str] = set()
    timeout_cfg = httpx.Timeout(timeout, connect=timeout)
    async with httpx.AsyncClient(timeout=timeout_cfg) as client:
        for entry in pending:
            result.checked += 1
            checked_keys.add(entry.registry_key())
            entry.last_checked_at = datetime.now(tz=UTC).isoformat()
            was_flagged = entry.flagged
            if entry.kind == "url":
                status = await _verify_url_status(client, entry.target)
                entry.last_status = status
                if status is None:
                    _append_verify_error(result, f"url_unreachable:{entry.target}")
                if _url_check_failed(status):
                    if not was_flagged:
                        entry.strikes += 1
                        result.dead_urls += 1
                else:
                    _recover_flagged_entry(
                        graph_root,
                        entry,
                        property_name="dead-link",
                    )
            else:
                missing = _asset_missing(graph_root, entry.page_relpath, entry.target)
                entry.last_status = 404 if missing else 200
                if missing:
                    if not was_flagged:
                        entry.strikes += 1
                        result.missing_assets += 1
                else:
                    _recover_flagged_entry(
                        graph_root,
                        entry,
                        property_name="missing-asset",
                    )

            if (
                entry.strikes >= threshold
                and not entry.flagged
                and flag_block_hygiene_property(
                    graph_root,
                    entry.page_relpath,
                    entry.block_uuid,
                    "dead-link" if entry.kind == "url" else "missing-asset",
                )
            ):
                entry.flagged = True
                result.flagged_blocks += 1
                if entry.kind == "url":
                    result.flagged_url_blocks += 1
                else:
                    result.flagged_asset_blocks += 1

    _persist_checked_registry_updates(graph_root, entries, checked_keys)
    return result


def _mutate_block_hygiene_property(
    graph_root: Path,
    page_relpath: str,
    block_uuid: str,
    property_name: str,
    *,
    remove: bool,
) -> bool:
    """Add or remove ``dead-link::`` / ``missing-asset::`` under the block (OCC-safe)."""
    page_path = _safe_page_path(graph_root, page_relpath)
    if page_path is None or not page_path.is_file():
        return False

    prop_key = property_name if property_name.endswith("::") else f"{property_name}::"
    prop_pattern = _DEAD_LINK_PROP if property_name.startswith("dead-link") else _MISSING_ASSET_PROP

    baseline_mtime = occ_snapshot(page_path)
    if baseline_mtime is None or not occ_verify_before_write(page_path, baseline_mtime):
        return False

    with page_rmw_lock(page_path):
        if file_mtime_drifted(page_path, baseline_mtime):
            return False
        raw = read_graph_file_text(page_path, graph_root, errors="replace")
        lines = raw.splitlines(keepends=True)
        if not lines:
            lines = [""]
        stripped = strip_lines_for_match(lines)
        located = locate_block_by_uuid(stripped, block_uuid)
        if located is None:
            return False
        bullet_idx, _id_idx, block_end = located

        if remove:
            changed = False
            remove_at: list[int] = []
            for i in range(bullet_idx + 1, min(block_end, len(stripped))):
                if prop_pattern.match(stripped[i]):
                    remove_at.append(i)
            for i in reversed(remove_at):
                del lines[i]
                changed = True
            if not changed:
                return False
            updated = "".join(
                ln if ln.endswith("\n") else ln + "\n" for ln in [ln.rstrip("\n") for ln in lines]
            )
            return bool(
                atomic_write_bytes_if_unchanged(
                    page_path,
                    updated.encode("utf-8"),
                    graph_root=graph_root,
                    baseline_mtime=baseline_mtime,
                    robot_commit_summary=f"cleared {property_name} on block",
                ),
            )

        if _block_has_property(stripped, bullet_idx, block_end, prop_pattern):
            return True

        insert_at = block_property_insert_index(stripped, bullet_idx, block_end)
        bullet_match = _BULLET_RE.match(stripped[bullet_idx].rstrip("\n"))
        base_ws = bullet_match.group(1) if bullet_match else ""
        indent = base_ws + bullet_indent_unit(stripped, bullet_idx)
        lines.insert(insert_at, f"{indent}{prop_key} true\n")

        updated = "".join(
            ln if ln.endswith("\n") else ln + "\n" for ln in [ln.rstrip("\n") for ln in lines]
        )
        return bool(
            atomic_write_bytes_if_unchanged(
                page_path,
                updated.encode("utf-8"),
                graph_root=graph_root,
                baseline_mtime=baseline_mtime,
                robot_commit_summary=f"flagged {property_name} on block",
            ),
        )


def flag_block_hygiene_property(
    graph_root: Path,
    page_relpath: str,
    block_uuid: str,
    property_name: str,
) -> bool:
    """Append ``dead-link:: true`` or ``missing-asset:: true`` under the block (OCC-safe)."""
    return _mutate_block_hygiene_property(
        graph_root,
        page_relpath,
        block_uuid,
        property_name,
        remove=False,
    )


def clear_block_hygiene_property(
    graph_root: Path,
    page_relpath: str,
    block_uuid: str,
    property_name: str,
) -> bool:
    """Remove hygiene property lines under the block when a link recovers."""
    return _mutate_block_hygiene_property(
        graph_root,
        page_relpath,
        block_uuid,
        property_name,
        remove=True,
    )


def _run_async_verify_batch(
    graph_root: Path,
    registry: dict[str, LinkRegistryEntry],
) -> LinkVerificationCycleResult:
    """Run async verify from sync code (daemon thread or nested event-loop safe)."""
    coro = verify_registry_batch(graph_root, registry)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result()


def run_link_verification_cycle(graph_root: Path) -> LinkVerificationCycleResult:
    """Sync entry: load registry, verify a batch, return metrics."""
    if not link_verify_enabled():
        return LinkVerificationCycleResult()
    path = link_registry_path(graph_root)
    with cross_process_json_flock(path):
        registry = _load_registry_unlocked(path)
    if not registry:
        return LinkVerificationCycleResult()
    return _run_async_verify_batch(graph_root, registry)


def _purge_registry_entries_for_page(graph_root: Path, page_relpath: str) -> int:
    """Drop registry rows for a page file that no longer exists."""
    path = link_registry_path(graph_root)
    with cross_process_json_flock(path):
        registry = _load_registry_unlocked(path)
        stale = [key for key, entry in registry.items() if entry.page_relpath == page_relpath]
        if not stale:
            return 0
        for key in stale:
            del registry[key]
        _save_registry_unlocked(path, registry)
    return len(stale)


def register_page_links_from_path(graph_root: Path, page_path: Path) -> int:
    """Read page from disk and merge link entries into the registry."""
    if not link_verify_enabled():
        return 0
    page_relpath = _page_relpath(graph_root, page_path)
    if not page_path.is_file():
        if page_relpath:
            return _purge_registry_entries_for_page(graph_root, page_relpath)
        return 0
    try:
        content = read_graph_file_text(page_path, graph_root, errors="replace")
    except (OSError, PathTraversalSecurityError):
        return 0
    return merge_page_links_into_registry(graph_root, page_path, content)


__all__ = [
    "LINK_REGISTRY_FILENAME",
    "LinkRegistryEntry",
    "LinkVerificationCycleResult",
    "clear_block_hygiene_property",
    "extract_links_from_page",
    "flag_block_hygiene_property",
    "link_verify_enabled",
    "load_link_registry",
    "merge_page_links_into_registry",
    "register_page_links_from_path",
    "run_link_verification_cycle",
    "save_link_registry",
    "verify_registry_batch",
]
