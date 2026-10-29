"""Private external SQLite storage for the strict-read-only semantic index."""

from __future__ import annotations

import contextlib
import os
import sqlite3
import stat
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from ..shadow.cache_location import (
    ShadowCacheLocationError,
    resolve_shadow_cache_location,
)
from .external_config import ExternalSemanticSettings

_GRAPH_DIR = "graphs"
_SEMANTIC_DIR = "semantic"
_WORKING_DB = "working.sqlite"
_PUBLISHED_DB = "semantic.sqlite"
_LOCK_DB = "writer-lock.sqlite"

_SCHEMA: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS semantic_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS indexed_pages (
        source_path TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        source_hash TEXT NOT NULL,
        source_size INTEGER NOT NULL,
        source_mtime_ns INTEGER NOT NULL,
        block_count INTEGER NOT NULL,
        chunk_count INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS semantic_blocks (
        source_path TEXT NOT NULL REFERENCES indexed_pages(source_path) ON DELETE CASCADE,
        block_key TEXT NOT NULL,
        block_content_hash TEXT NOT NULL,
        block_length_chars INTEGER NOT NULL,
        parent_citation_id TEXT,
        ancestor_citation_ids_json TEXT NOT NULL,
        properties_json TEXT NOT NULL,
        PRIMARY KEY (source_path, block_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS semantic_vectors (
        source_path TEXT NOT NULL
            REFERENCES indexed_pages(source_path) ON DELETE CASCADE,
        block_key TEXT NOT NULL,
        citation_id TEXT NOT NULL,
        persisted_uuid TEXT,
        block_ordinal INTEGER NOT NULL,
        chunk_ordinal INTEGER NOT NULL,
        source_hash TEXT NOT NULL,
        content TEXT NOT NULL,
        vector BLOB NOT NULL,
        chunk_start_char INTEGER NOT NULL,
        chunk_end_char INTEGER NOT NULL,
        token_count INTEGER NOT NULL,
        context_text TEXT NOT NULL,
        split_kind TEXT NOT NULL,
        FOREIGN KEY (source_path, block_key)
            REFERENCES semantic_blocks(source_path, block_key) ON DELETE CASCADE,
        PRIMARY KEY (source_path, block_key, chunk_ordinal)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_semantic_vectors_source_hash "
    "ON semantic_vectors(source_path, source_hash)",
)


class ExternalSemanticStoreError(ValueError):
    """Content-free failure to resolve or use external semantic storage."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ExternalSemanticPaths:
    """Resolved external paths; resolving them never creates a file or directory."""

    graph_root: Path
    cache_root: Path
    graph_id: str
    semantic_dir: Path
    working_db: Path
    published_db: Path
    writer_lock_db: Path


def resolve_external_semantic_paths(
    graph_root: str | Path,
    settings: ExternalSemanticSettings,
) -> ExternalSemanticPaths:
    """Resolve the same canonical graph identity as Shadow, without initializing it."""
    from ..graph.path_sandbox import resolved_graph_root

    root = resolved_graph_root(graph_root)
    cache_candidate = settings.cache_root.expanduser()
    if not cache_candidate.is_absolute():
        raise ExternalSemanticStoreError("cache_path_not_absolute")
    _reject_symlink_components(cache_candidate)
    try:
        location = resolve_shadow_cache_location(
            root,
            env={"MATRYCA_CACHE_PATH": str(cache_candidate)},
        )
    except ShadowCacheLocationError as exc:
        raise ExternalSemanticStoreError(exc.reason) from exc

    cache_root = location.cache_root
    semantic_dir = cache_root / _GRAPH_DIR / location.graph_id / _SEMANTIC_DIR
    try:
        resolved_dir = semantic_dir.resolve(strict=False)
        if not resolved_dir.is_relative_to(cache_root):
            raise ExternalSemanticStoreError("semantic_directory_escape")
    except OSError as exc:
        raise ExternalSemanticStoreError("semantic_directory_unresolvable") from exc
    _reject_symlink_components(semantic_dir)
    paths = ExternalSemanticPaths(
        graph_root=root,
        cache_root=cache_root,
        graph_id=location.graph_id,
        semantic_dir=semantic_dir,
        working_db=semantic_dir / _WORKING_DB,
        published_db=semantic_dir / _PUBLISHED_DB,
        writer_lock_db=semantic_dir / _LOCK_DB,
    )
    for file_path in (paths.working_db, paths.published_db, paths.writer_lock_db):
        _reject_existing_symlink(file_path)
        _require_regular_or_missing(file_path)
    return paths


def ensure_semantic_directory(paths: ExternalSemanticPaths) -> None:
    """Create only the external semantic-cache directories with private modes."""
    directories = (
        paths.cache_root,
        paths.cache_root / _GRAPH_DIR,
        paths.cache_root / _GRAPH_DIR / paths.graph_id,
        paths.semantic_dir,
    )
    for directory in directories:
        _reject_symlink_components(directory)
        try:
            resolved = directory.resolve(strict=False)
            if directory != paths.cache_root and not resolved.is_relative_to(paths.cache_root):
                raise ExternalSemanticStoreError("semantic_directory_escape")
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            if not directory.is_dir():
                raise ExternalSemanticStoreError("semantic_directory_invalid")
            if directory != paths.cache_root and os.name == "posix":
                directory.chmod(0o700)
        except ExternalSemanticStoreError:
            raise
        except OSError as exc:
            raise ExternalSemanticStoreError("semantic_directory_unavailable") from exc


@contextmanager
def exclusive_writer_lock(
    paths: ExternalSemanticPaths,
    *,
    timeout_seconds: float,
) -> Iterator[None]:
    """Serialize indexers with a transaction held on an external SQLite lock file."""
    ensure_semantic_directory(paths)
    _reject_existing_symlink(paths.writer_lock_db)
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(str(paths.writer_lock_db), timeout=timeout_seconds)
        if os.name == "posix":
            os.chmod(paths.writer_lock_db, 0o600)
        connection.execute("BEGIN EXCLUSIVE")
        yield
    except sqlite3.Error as exc:
        raise ExternalSemanticStoreError("writer_lock_unavailable") from exc
    finally:
        if connection is not None:
            with contextlib.suppress(sqlite3.Error):
                connection.rollback()
            connection.close()


def open_working_database(paths: ExternalSemanticPaths) -> sqlite3.Connection:
    """Open/create the resumable writer database; callers own transactions."""
    ensure_semantic_directory(paths)
    _reject_existing_symlink(paths.working_db)
    try:
        connection = sqlite3.connect(str(paths.working_db), timeout=60.0)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute("PRAGMA synchronous = FULL")
        for statement in _SCHEMA:
            connection.execute(statement)
        connection.commit()
        if os.name == "posix":
            os.chmod(paths.working_db, 0o600)
        return connection
    except sqlite3.Error as exc:
        raise ExternalSemanticStoreError("working_database_unavailable") from exc


def reset_working_database(connection: sqlite3.Connection) -> None:
    """Recreate only derived work tables during an explicit incompatible rebuild."""
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DROP TABLE IF EXISTS semantic_vectors")
        connection.execute("DROP TABLE IF EXISTS semantic_blocks")
        connection.execute("DELETE FROM indexed_pages")
        connection.execute("DELETE FROM semantic_meta")
        for statement in _SCHEMA:
            connection.execute(statement)
        connection.commit()
    except sqlite3.Error as exc:
        connection.rollback()
        raise ExternalSemanticStoreError("working_schema_reset_failed") from exc


def open_published_database(paths: ExternalSemanticPaths) -> sqlite3.Connection:
    """Open the immutable published snapshot without creating files or sidecars."""
    _require_regular_file(paths.published_db)
    uri = f"{paths.published_db.as_uri()}?mode=ro&immutable=1"
    try:
        connection = sqlite3.connect(uri, uri=True)
        connection.execute("PRAGMA query_only = ON")
        return connection
    except sqlite3.Error as exc:
        raise ExternalSemanticStoreError("published_database_unreadable") from exc


def publish_snapshot(
    working: sqlite3.Connection,
    paths: ExternalSemanticPaths,
) -> None:
    """Atomically replace the published read-only snapshot from a complete database."""
    ensure_semantic_directory(paths)
    _reject_existing_symlink(paths.published_db)
    temporary = paths.semantic_dir / f".semantic-{uuid.uuid4().hex}.tmp"
    _require_regular_or_missing(temporary)
    destination: sqlite3.Connection | None = None
    try:
        destination = sqlite3.connect(str(temporary), timeout=60.0)
        destination.execute("PRAGMA journal_mode = DELETE")
        working.backup(destination)
        destination.commit()
        destination.close()
        destination = None
        if os.name == "posix":
            os.chmod(temporary, 0o600)
        _fsync_file(temporary)
        os.replace(temporary, paths.published_db)
        if os.name == "posix":
            os.chmod(paths.published_db, 0o600)
        _fsync_directory(paths.semantic_dir)
    except (OSError, sqlite3.Error) as exc:
        raise ExternalSemanticStoreError("snapshot_publish_failed") from exc
    finally:
        if destination is not None:
            destination.close()
        with contextlib.suppress(OSError):
            temporary.unlink()


def get_metadata(connection: sqlite3.Connection) -> dict[str, str]:
    """Read content-free metadata from a semantic database."""
    try:
        return {
            str(key): str(value)
            for key, value in connection.execute("SELECT key, value FROM semantic_meta")
        }
    except sqlite3.Error as exc:
        raise ExternalSemanticStoreError("semantic_metadata_unreadable") from exc


def set_metadata(connection: sqlite3.Connection, values: Mapping[str, str]) -> None:
    """Replace selected metadata values in the current writer transaction."""
    connection.executemany(
        "INSERT INTO semantic_meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        tuple((str(key), str(value)) for key, value in values.items()),
    )


def table_counts(connection: sqlite3.Connection) -> tuple[int, int, int]:
    """Return indexed page, distinct block, and chunk counts."""
    try:
        page_count = int(connection.execute("SELECT count(*) FROM indexed_pages").fetchone()[0])
        block_count = int(
            connection.execute(
                "SELECT COALESCE(sum(block_count), 0) FROM indexed_pages"
            ).fetchone()[0]
        )
        chunk_count = int(connection.execute("SELECT count(*) FROM semantic_vectors").fetchone()[0])
    except sqlite3.Error as exc:
        raise ExternalSemanticStoreError("semantic_database_invalid") from exc
    return page_count, block_count, chunk_count


def _reject_symlink_components(path: Path) -> None:
    for component in _path_components(path):
        if component.is_symlink():
            raise ExternalSemanticStoreError("cache_path_symlink")


def _reject_existing_symlink(path: Path) -> None:
    if path.is_symlink():
        raise ExternalSemanticStoreError("semantic_path_symlink")


def _require_regular_file(path: Path) -> None:
    _reject_existing_symlink(path)
    try:
        file_stat = path.lstat()
    except OSError as exc:
        raise ExternalSemanticStoreError("published_snapshot_missing") from exc
    if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_nlink > 1:
        raise ExternalSemanticStoreError("semantic_file_invalid")


def _require_regular_or_missing(path: Path) -> None:
    _reject_existing_symlink(path)
    if not path.exists():
        return
    try:
        file_stat = path.lstat()
    except OSError as exc:
        raise ExternalSemanticStoreError("semantic_file_invalid") from exc
    if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_nlink > 1:
        raise ExternalSemanticStoreError("semantic_file_invalid")


def _path_components(path: Path) -> tuple[Path, ...]:
    absolute = path.absolute()
    parts = absolute.parts
    if not parts:
        return ()
    current = Path(parts[0])
    items = [current]
    for part in parts[1:]:
        current = current / part
        items.append(current)
    return tuple(items)


def _fsync_file(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_directory(path: Path) -> None:
    if os.name != "posix":
        return
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


__all__ = [
    "ExternalSemanticPaths",
    "ExternalSemanticStoreError",
    "ensure_semantic_directory",
    "exclusive_writer_lock",
    "get_metadata",
    "open_published_database",
    "open_working_database",
    "publish_snapshot",
    "resolve_external_semantic_paths",
    "set_metadata",
    "table_counts",
]
