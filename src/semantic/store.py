"""Persistent dual-vector index per block UUID (JSON under semantic cache)."""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger

from ..graph.json_flock import cross_process_json_flock
from ..utils.bounded_json import BoundedJsonError, read_bounded_json

BLOCK_VECTORS_FILENAME = "block_vectors.json"
BLOCK_VECTORS_VERSION = 1

_lock = threading.Lock()
_loaded: dict[str, BlockVectorStore] = {}
_disk_mtimes: dict[str, int] = {}


def _graph_cache_key(graph_root: Path) -> str:
    return str(graph_root.expanduser().resolve(strict=False))


def _block_vectors_mtime(path: Path) -> int:
    if not path.is_file():
        return 0
    return path.stat().st_mtime_ns


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
            _loaded[key] = self


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
            try:
                with cross_process_json_flock(path):
                    payload = read_bounded_json(path)
                if isinstance(payload, dict):
                    store = BlockVectorStore.from_json(Path(key), payload)
            except (BoundedJsonError, OSError, ValueError, TypeError) as exc:
                logger.warning("Failed to load block_vectors.json: {}", exc)
        _loaded[key] = store
        _disk_mtimes[key] = disk_mtime
        return store


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
    "_semantic_search_max_candidates",
    "clear_block_vector_store_cache",
    "load_block_vector_store",
]
