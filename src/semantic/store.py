"""Persistent dual-vector index per block UUID (JSON under semantic cache)."""

from __future__ import annotations

import json
import os
import threading
from collections import OrderedDict
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import ijson
from loguru import logger

from ..graph.json_flock import cross_process_json_flock, cross_process_json_read_flock
from ..graph.safety.write_policy import GraphReadOnlyError, guard_graph_mutation
from ..utils.bounded_json import BoundedJsonError, read_bounded_json

BLOCK_VECTORS_FILENAME = "block_vectors.json"
BLOCK_VECTORS_VERSION = 1

_lock = threading.Lock()
_loaded: OrderedDict[str, BlockVectorStore] = OrderedDict()
_disk_mtimes: dict[str, float] = {}


def _block_vector_store_max_graphs() -> int:
    raw = os.environ.get("MATRYCA_BLOCK_VECTOR_STORE_MAX_GRAPHS", "").strip()
    if not raw:
        return 4
    try:
        return max(1, min(32, int(raw)))
    except ValueError:
        return 4


def _evict_lru_block_stores() -> None:
    limit = _block_vector_store_max_graphs()
    while len(_loaded) > limit:
        _loaded.popitem(last=False)


def _graph_cache_key(graph_root: Path) -> str:
    return str(graph_root.expanduser().resolve(strict=False))


def _block_vectors_mtime(path: Path) -> float:
    if not path.is_file():
        return 0.0
    return path.stat().st_mtime


def _block_vector_store_mode() -> str:
    raw = os.environ.get("MATRYCA_BLOCK_VECTOR_STORE_MODE", "ondemand").strip().lower()
    return raw if raw in {"resident", "ondemand"} else "ondemand"


def _cache_block_vector_store(key: str, store: BlockVectorStore, *, disk_mtime: float) -> None:
    if _block_vector_store_mode() != "resident":
        return
    _loaded[key] = store
    _loaded.move_to_end(key)
    _evict_lru_block_stores()
    _disk_mtimes[key] = disk_mtime


def _semantic_search_max_candidates() -> int:
    raw = os.environ.get("MATRYCA_SEMANTIC_SEARCH_MAX_CANDIDATES", "").strip()
    if not raw:
        return 50_000
    try:
        return max(100, min(500_000, int(raw)))
    except ValueError:
        return 50_000


@dataclass(slots=True)
class BlockVectorRecord:
    """Dual embeddings for one Logseq block."""

    page_title: str
    block_text: str
    applicability_text: str
    vec_content: list[float]
    vec_applicability: list[float]
    updated_at: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "page_title": self.page_title,
            "block_text": self.block_text,
            "applicability_text": self.applicability_text,
            "vec_content": self.vec_content,
            "vec_applicability": self.vec_applicability,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> BlockVectorRecord:
        return cls(
            page_title=str(payload.get("page_title", "")),
            block_text=str(payload.get("block_text", "")),
            applicability_text=str(payload.get("applicability_text", "")),
            vec_content=[float(x) for x in payload.get("vec_content", [])],
            vec_applicability=[float(x) for x in payload.get("vec_applicability", [])],
            updated_at=str(payload.get("updated_at", "")),
        )


@dataclass
class BlockVectorStore:
    """In-memory block vector catalog backed by ``.matryca_semantic_cache/block_vectors.json``."""

    graph_root: Path
    version: int = BLOCK_VECTORS_VERSION
    updated_at: str | None = None
    embedding_dim: int | None = None
    blocks: dict[str, BlockVectorRecord] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    @staticmethod
    def store_path(graph_root: Path) -> Path:
        return graph_root / ".matryca_semantic_cache" / BLOCK_VECTORS_FILENAME

    def to_json(self) -> dict[str, Any]:
        with self._lock:
            payload = {str(uuid): rec.to_json() for uuid, rec in sorted(self.blocks.items())}
        return {
            "version": self.version,
            "updated_at": self.updated_at,
            "embedding_dim": self.embedding_dim,
            "blocks": payload,
        }

    @classmethod
    def from_json(cls, graph_root: Path, payload: dict[str, Any]) -> BlockVectorStore:
        blocks: dict[str, BlockVectorRecord] = {}
        raw = payload.get("blocks", {})
        if isinstance(raw, dict):
            for block_uuid, rec in raw.items():
                if isinstance(rec, dict):
                    blocks[str(block_uuid)] = BlockVectorRecord.from_json(rec)
        dim_raw = payload.get("embedding_dim")
        embedding_dim = int(dim_raw) if isinstance(dim_raw, int) else None
        if embedding_dim is None and blocks:
            first = next(iter(blocks.values()))
            if first.vec_content:
                embedding_dim = len(first.vec_content)
        return cls(
            graph_root=graph_root,
            version=int(payload.get("version", BLOCK_VECTORS_VERSION)),
            updated_at=payload.get("updated_at"),
            embedding_dim=embedding_dim,
            blocks=blocks,
        )

    def _validate_vector(self, vector: list[float], *, block_uuid: str) -> bool:
        if not vector:
            logger.warning("Empty embedding vector for block {}", block_uuid)
            return False
        dim = len(vector)
        with self._lock:
            expected = self.embedding_dim
            if expected is None:
                self.embedding_dim = dim
                return True
            if dim != expected:
                logger.warning(
                    "Embedding dim mismatch for {}: got {} expected {} "
                    "(reindex after MATRYCA_EMBEDDING_MODEL change)",
                    block_uuid,
                    dim,
                    expected,
                )
                return False
        return True

    def upsert(self, block_uuid: str, record: BlockVectorRecord) -> bool:
        if not self._validate_vector(record.vec_content, block_uuid=block_uuid):
            return False
        if not self._validate_vector(record.vec_applicability, block_uuid=block_uuid):
            return False
        with self._lock:
            self.blocks[block_uuid] = record
        return True

    def remove_blocks_for_page_except(
        self,
        page_title: str,
        keep_uuids: set[str],
    ) -> int:
        removed = 0
        with self._lock:
            stale = [
                uid
                for uid, rec in self.blocks.items()
                if rec.page_title == page_title and uid not in keep_uuids
            ]
            for uid in stale:
                del self.blocks[uid]
                removed += 1
        return removed

    def iter_records(self) -> list[tuple[str, BlockVectorRecord]]:
        with self._lock:
            return list(self.blocks.items())

    def save(self) -> None:
        path = self.store_path(self.graph_root)
        try:
            guard_graph_mutation(self.graph_root, path, operation="save_block_vector_store")
        except GraphReadOnlyError:
            logger.debug("Skipping graph-local block vector save under read-only policy")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with cross_process_json_flock(path), self._lock:
            self.updated_at = datetime.now(tz=UTC).isoformat()
            payload = {
                "version": self.version,
                "updated_at": self.updated_at,
                "embedding_dim": self.embedding_dim,
                "blocks": {
                    str(block_uuid): record.to_json()
                    for block_uuid, record in sorted(self.blocks.items())
                },
            }
            data = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(data, encoding="utf-8")
            tmp.replace(path)
        key = _graph_cache_key(self.graph_root)
        with _lock:
            _disk_mtimes[key] = _block_vectors_mtime(path)
            _cache_block_vector_store(key, self, disk_mtime=_disk_mtimes[key])


def _read_block_vectors_header(path: Path) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "version": BLOCK_VECTORS_VERSION,
        "updated_at": None,
        "embedding_dim": None,
    }
    if not path.is_file():
        return meta
    try:
        with path.open("rb") as handle:
            for prefix, event, value in ijson.parse(handle):
                if prefix == "version" and event in {"number", "string"}:
                    meta["version"] = int(value)
                elif prefix == "updated_at" and event == "string":
                    meta["updated_at"] = value
                elif prefix == "embedding_dim" and event == "number":
                    meta["embedding_dim"] = int(value)
                elif prefix == "blocks" or prefix.startswith("blocks."):
                    break
    except (OSError, ValueError, TypeError) as exc:
        logger.warning("Failed to read block_vectors.json header: {}", exc)
    return meta


def _coerce_embedding_dim(raw: Any) -> int | None:
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw)
    return None


def _validate_block_vectors(
    record: BlockVectorRecord,
    *,
    block_uuid: str,
    embedding_dim: int | None,
) -> tuple[bool, int | None]:
    new_dim = embedding_dim
    for vector in (record.vec_content, record.vec_applicability):
        if not vector:
            logger.warning("Empty embedding vector for block {}", block_uuid)
            return False, embedding_dim
        dim = len(vector)
        if new_dim is None:
            new_dim = dim
        elif dim != new_dim:
            logger.warning(
                "Embedding dim mismatch for {}: got {} expected {} "
                "(reindex after MATRYCA_EMBEDDING_MODEL change)",
                block_uuid,
                dim,
                new_dim,
            )
            return False, embedding_dim
    return True, new_dim


def _invalidate_block_vector_cache(graph_root: Path) -> None:
    key = _graph_cache_key(graph_root)
    with _lock:
        _loaded.pop(key, None)
        path = BlockVectorStore.store_path(graph_root)
        if path.is_file():
            _disk_mtimes[key] = _block_vectors_mtime(path)
        else:
            _disk_mtimes.pop(key, None)


def apply_page_block_vector_updates(
    graph_root: Path,
    page_title: str,
    *,
    upserts: dict[str, BlockVectorRecord],
    keep_uuids: set[str],
) -> tuple[int, int]:
    """Apply page-scoped upserts/prunes via streaming merge (avoids full-vault RAM load)."""
    root = graph_root.expanduser().resolve(strict=False)
    path = BlockVectorStore.store_path(root)
    try:
        guard_graph_mutation(root, path, operation="apply_page_block_vector_updates")
    except GraphReadOnlyError:
        logger.debug("Skipping graph-local block vector update under read-only policy")
        return 0, 0

    embedding_dim = (
        _coerce_embedding_dim(_read_block_vectors_header(path).get("embedding_dim"))
        if path.is_file()
        else None
    )
    validated: dict[str, BlockVectorRecord] = {}
    for block_uuid, record in upserts.items():
        ok, embedding_dim = _validate_block_vectors(
            record,
            block_uuid=block_uuid,
            embedding_dim=embedding_dim,
        )
        if ok:
            validated[block_uuid] = record
    indexed = len(validated)

    if not path.is_file():
        if not validated:
            return 0, 0
        store = BlockVectorStore(graph_root=root)
        for block_uuid, record in validated.items():
            store.upsert(block_uuid, record)
        store.save()
        return indexed, 0

    pending = dict(validated)
    pruned = 0
    changed = bool(pending)
    tmp = path.with_suffix(".json.tmp")

    with cross_process_json_flock(path):
        meta = _read_block_vectors_header(path)
        version = int(meta.get("version", BLOCK_VECTORS_VERSION))
        if embedding_dim is None:
            embedding_dim = _coerce_embedding_dim(meta.get("embedding_dim"))

        with path.open("rb") as src, tmp.open("w", encoding="utf-8") as dst:
            now = datetime.now(tz=UTC).isoformat()
            dst.write("{\n")
            dst.write(f'  "version": {version},\n')
            dst.write(f'  "updated_at": {json.dumps(now)},\n')
            if embedding_dim is not None:
                dst.write(f'  "embedding_dim": {embedding_dim},\n')
            dst.write('  "blocks": {\n')

            first = True
            try:
                for block_uuid, raw in ijson.kvitems(src, "blocks"):
                    block_uuid = str(block_uuid)
                    if not isinstance(raw, dict):
                        continue
                    try:
                        rec = BlockVectorRecord.from_json(raw)
                    except (ValueError, TypeError) as exc:
                        logger.warning(
                            "Skipping corrupt block {} during merge: {}",
                            block_uuid,
                            exc,
                        )
                        changed = True
                        continue

                    if rec.page_title == page_title:
                        if block_uuid not in keep_uuids:
                            pruned += 1
                            changed = True
                            continue
                        if block_uuid in pending:
                            rec = pending.pop(block_uuid)
                            changed = True
                    elif block_uuid in pending:
                        rec = pending.pop(block_uuid)
                        changed = True

                    if not first:
                        dst.write(",\n")
                    first = False
                    entry = json.dumps(rec.to_json(), ensure_ascii=False)
                    dst.write(f"    {json.dumps(block_uuid)}: {entry}")
            except (BoundedJsonError, OSError, ValueError, TypeError) as exc:
                logger.warning("Failed to stream block_vectors.json during merge: {}", exc)
                tmp.unlink(missing_ok=True)
                return indexed, pruned

            for block_uuid, rec in pending.items():
                changed = True
                if not first:
                    dst.write(",\n")
                first = False
                entry = json.dumps(rec.to_json(), ensure_ascii=False)
                dst.write(f"    {json.dumps(block_uuid)}: {entry}")

            dst.write("\n  }\n}\n")

        if not changed:
            tmp.unlink(missing_ok=True)
            return indexed, pruned

        tmp.replace(path)
        _invalidate_block_vector_cache(root)

    return indexed, pruned


def iter_block_records_from_disk(graph_root: Path) -> Iterator[tuple[str, BlockVectorRecord]]:
    """Stream block records from disk without retaining the global resident cache."""
    root = graph_root.expanduser().resolve(strict=False)
    path = BlockVectorStore.store_path(root)
    if not path.is_file():
        return
    try:
        with cross_process_json_read_flock(path, graph_root=root), path.open("rb") as handle:
            for block_uuid, raw in ijson.kvitems(handle, "blocks"):
                if isinstance(raw, dict):
                    yield str(block_uuid), BlockVectorRecord.from_json(raw)
    except (BoundedJsonError, OSError, ValueError, TypeError) as exc:
        logger.warning("Failed to stream block_vectors.json: {}", exc)


def release_block_vector_store(graph_root: Path) -> None:
    """Drop the in-memory store for one graph (Phase teardown / RAM budget)."""
    key = _graph_cache_key(graph_root)
    with _lock:
        _loaded.pop(key, None)
        _disk_mtimes.pop(key, None)


def load_block_vector_store(
    graph_root: Path,
    *,
    force_reload: bool = False,
) -> BlockVectorStore:
    """Load or create the block vector store for ``graph_root``."""
    key = _graph_cache_key(graph_root)
    path = BlockVectorStore.store_path(Path(key))
    disk_mtime = _block_vectors_mtime(path)
    with _lock:
        if not force_reload and key in _loaded and _disk_mtimes.get(key) == disk_mtime:
            return _loaded[key]

        store = BlockVectorStore(graph_root=Path(key))
        if path.is_file():
            if _block_vector_store_mode() == "ondemand":
                meta = _read_block_vectors_header(path)
                store.version = int(meta.get("version", BLOCK_VECTORS_VERSION))
                updated_at = meta.get("updated_at")
                store.updated_at = updated_at if isinstance(updated_at, str) else None
                store.embedding_dim = _coerce_embedding_dim(meta.get("embedding_dim"))
            else:
                try:
                    with cross_process_json_read_flock(path, graph_root=Path(key)):
                        payload = read_bounded_json(path)
                    if isinstance(payload, dict):
                        store = BlockVectorStore.from_json(Path(key), payload)
                except (BoundedJsonError, OSError, ValueError, TypeError) as exc:
                    logger.warning("Failed to load block_vectors.json: {}", exc)
        _cache_block_vector_store(key, store, disk_mtime=disk_mtime)
        return store


def block_vector_store_ondemand() -> bool:
    return _block_vector_store_mode() == "ondemand"


def clear_block_vector_store_cache() -> None:
    """Drop in-memory stores (tests)."""
    with _lock:
        _loaded.clear()
        _disk_mtimes.clear()


__all__ = [
    "BLOCK_VECTORS_FILENAME",
    "BLOCK_VECTORS_VERSION",
    "BlockVectorRecord",
    "BlockVectorStore",
    "apply_page_block_vector_updates",
    "block_vector_store_ondemand",
    "_semantic_search_max_candidates",
    "clear_block_vector_store_cache",
    "iter_block_records_from_disk",
    "load_block_vector_store",
    "release_block_vector_store",
]
