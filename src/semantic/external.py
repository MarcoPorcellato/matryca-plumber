"""Strict-read-only semantic indexing and search over an external SQLite snapshot."""

from __future__ import annotations

import heapq
import json
import math
import sqlite3
import struct
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from ..graph.alias_index import iter_alias_source_paths
from ..graph.path_sandbox import resolved_graph_root
from .external_chunks import TokenCounter
from .external_config import ExternalSemanticSettings
from .external_extract import (
    MAX_SOURCE_PAGE_BYTES,
    ExternalExtractionError,
    ExtractedPage,
    SourceSnapshot,
    extract_page_blocks,
    read_source_snapshot,
)
from .external_store import (
    ExternalSemanticPaths,
    ExternalSemanticStoreError,
    exclusive_writer_lock,
    get_metadata,
    open_published_database,
    open_working_database,
    publish_snapshot,
    reset_working_database,
    resolve_external_semantic_paths,
    set_metadata,
    table_counts,
)

PIPELINE_VERSION = "block-sentences-v2"
_VECTOR_FORMAT = "<f"
_MAX_SEARCH_LIMIT = 100


class EmbeddingClient(TokenCounter, Protocol):
    """Narrow embedding boundary used by the external index."""

    def embed_text(self, text: str) -> list[float]: ...


class ExternalSemanticError(ValueError):
    """Content-free semantic backend contract error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def index_graph(
    graph_root: str | Path,
    settings: ExternalSemanticSettings,
    embedding_client: EmbeddingClient,
    *,
    progress: Callable[[dict[str, object]], None] | None = None,
) -> dict[str, object]:
    """Build a complete, resumable semantic snapshot without writing to the graph."""
    if not settings.enabled:
        return _disabled_result()
    _validate_profile(settings)
    root = resolved_graph_root(graph_root)
    if not root.is_dir():
        return _failure_result("graph_root_missing", published=False)

    paths = resolve_external_semantic_paths(root, settings)
    existing_snapshot = paths.published_db.is_file()
    try:
        with exclusive_writer_lock(paths, timeout_seconds=settings.timeout_seconds):
            working = _open_resumable_working_db(paths, settings)
            try:
                _set_work_state(working, "building", 0, ())
                source_paths = iter_alias_source_paths(root)
                failed_codes: Counter[str] = Counter()
                for processed_count, source_path in enumerate(source_paths, start=1):
                    try:
                        source = read_source_snapshot(
                            source_path,
                            root,
                            max_bytes=MAX_SOURCE_PAGE_BYTES,
                        )
                        if _working_page_matches(working, source):
                            _refresh_working_mtime(working, source)
                            continue
                        extracted = extract_page_blocks(
                            source,
                            root,
                            settings=settings,
                            tokenizer=embedding_client,
                        )
                        _index_page_transaction(
                            working,
                            source_path,
                            extracted,
                            root,
                            embedding_client,
                            settings,
                        )
                    except ExternalExtractionError as exc:
                        failed_codes[exc.code] += 1
                    except ExternalSemanticStoreError:
                        raise
                    except ExternalSemanticError as exc:
                        failed_codes[exc.code] += 1
                    except sqlite3.Error as exc:
                        raise ExternalSemanticStoreError("working_database_error") from exc
                    except Exception as exc:  # noqa: BLE001 - emit only a content-free category
                        failed_codes[_safe_error_code(exc)] += 1
                    if progress is not None:
                        page_count, block_count, chunk_count = table_counts(working)
                        progress(
                            {
                                "phase": "indexing",
                                "processed_page_count": processed_count,
                                "source_page_count": len(source_paths),
                                "indexed_page_count": page_count,
                                "indexed_block_count": block_count,
                                "chunk_count": chunk_count,
                                "failed_page_count": sum(failed_codes.values()),
                            }
                        )

                current_paths = {path.relative_to(root).as_posix() for path in source_paths}
                if not failed_codes:
                    _remove_deleted_working_pages(working, current_paths)
                    final_hashes, final_failures = _current_source_hashes(root)
                    failed_codes.update(final_failures)
                    if not final_failures:
                        working_hashes = _working_page_hashes(working)
                        if set(final_hashes) != set(working_hashes):
                            failed_codes["source_set_changed"] += 1
                        elif any(final_hashes[key] != working_hashes[key] for key in final_hashes):
                            failed_codes["source_changed_during_build"] += 1

                if failed_codes:
                    _set_work_state(working, "incomplete", sum(failed_codes.values()), failed_codes)
                    return _build_result(
                        working,
                        snapshot_complete=False,
                        failed_page_count=sum(failed_codes.values()),
                        failure_codes=failed_codes,
                        published_snapshot_preserved=existing_snapshot,
                        resumable=True,
                        working_state="incomplete",
                    )

                if progress is not None:
                    progress(
                        {
                            "phase": "validating",
                            "processed_page_count": len(source_paths),
                            "source_page_count": len(source_paths),
                            "failed_page_count": 0,
                        }
                    )
                page_count, block_count, chunk_count = table_counts(working)
                profile = _profile_metadata(settings)
                _begin(working)
                set_metadata(
                    working,
                    {
                        **profile,
                        "snapshot_complete": "1",
                        "build_state": "complete",
                        "indexed_page_count": str(page_count),
                        "indexed_block_count": str(block_count),
                        "chunk_count": str(chunk_count),
                        "source_page_count": str(len(current_paths)),
                        "published_at": _utc_now_iso(),
                        "last_failure_count": "0",
                        "last_failure_codes": "",
                    },
                )
                working.commit()
                publish_snapshot(working, paths)
                result = {
                    "snapshot_complete": True,
                    "snapshot_state": "complete",
                    "published_snapshot_state": "published",
                    "published_snapshot_complete": True,
                    "working_state": "complete",
                    "indexed_page_count": page_count,
                    "indexed_block_count": block_count,
                    "chunk_count": chunk_count,
                    "failed_page_count": 0,
                    "failure_codes": [],
                    "published_snapshot_preserved": False,
                    "resumable": False,
                }
                if progress is not None:
                    progress(
                        {
                            "phase": "published",
                            "processed_page_count": page_count,
                            "source_page_count": len(current_paths),
                            "indexed_page_count": page_count,
                            "indexed_block_count": block_count,
                            "chunk_count": chunk_count,
                            "failed_page_count": 0,
                        }
                    )
                return result
            finally:
                working.close()
    except ExternalSemanticStoreError as exc:
        return _failure_result(exc.code, published=existing_snapshot)


def index_status(
    graph_root: str | Path,
    settings: ExternalSemanticSettings,
) -> dict[str, object]:
    """Report snapshot state and exact source-hash coverage without creating files."""
    if not settings.enabled:
        return _disabled_result()
    _validate_profile(settings)
    root = resolved_graph_root(graph_root)
    if not root.is_dir():
        return _status_without_snapshot("graph_root_missing")
    paths = resolve_external_semantic_paths(root, settings)
    if not paths.published_db.exists():
        source_hashes, failures = _current_source_hashes(root)
        return {
            **_status_without_snapshot(None),
            "current_source_page_count": len(source_hashes) + sum(failures.values()),
            "unindexed_source_page_count": len(source_hashes) + sum(failures.values()),
            "unavailable_source_page_count": sum(failures.values()),
        }

    try:
        with closing(open_published_database(paths)) as connection:
            metadata = get_metadata(connection)
            page_count, block_count, chunk_count = table_counts(connection)
            indexed = {
                str(source_path): str(source_hash)
                for source_path, source_hash in connection.execute(
                    "SELECT source_path, source_hash FROM indexed_pages"
                )
            }
        profile_matches = _profile_matches(metadata, settings)
        source_hashes, failures = _current_source_hashes(root)
        coverage = _coverage_counts(indexed, source_hashes)
        unavailable_count = sum(failures.values())
        is_current = (
            profile_matches
            and not unavailable_count
            and coverage["stale_page_count"] == 0
            and coverage["unindexed_source_page_count"] == 0
            and metadata.get("snapshot_complete") == "1"
        )
        freshness = (
            "model_mismatch"
            if not profile_matches
            else "current_at_check"
            if is_current
            else "unknown"
            if unavailable_count
            else "stale"
        )
        return {
            "enabled": True,
            "snapshot_state": (
                "complete" if metadata.get("snapshot_complete") == "1" else "incomplete"
            ),
            "snapshot_complete": metadata.get("snapshot_complete") == "1",
            "compatible": profile_matches,
            "freshness": freshness,
            "indexed_page_count": page_count,
            "indexed_block_count": block_count,
            "chunk_count": chunk_count,
            "current_source_page_count": len(source_hashes) + unavailable_count,
            "unavailable_source_page_count": unavailable_count,
            "model": settings.model,
            "model_revision": settings.model_revision,
            "dimensions": settings.dimensions,
            "last_build_state": metadata.get("build_state", "unknown"),
            **coverage,
        }
    except (ExternalSemanticStoreError, sqlite3.Error):
        return _status_without_snapshot("snapshot_invalid")


def search_graph(
    graph_root: str | Path,
    query: str,
    settings: ExternalSemanticSettings,
    embedding_client: EmbeddingClient,
    *,
    limit: int = 15,
) -> dict[str, object]:
    """Search only a compatible published snapshot; the read path never writes files."""
    if not settings.enabled:
        return {**_disabled_result(), "hits": []}
    _validate_profile(settings)
    cleaned_query = query.strip()
    if not cleaned_query:
        raise ExternalSemanticError("query_empty")
    try:
        query_byte_count = len(cleaned_query.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ExternalSemanticError("query_invalid_utf8") from exc
    if query_byte_count > settings.max_input_bytes:
        raise ExternalSemanticError("query_too_large")
    if not 1 <= limit <= _MAX_SEARCH_LIMIT:
        raise ExternalSemanticError("search_limit_out_of_range")

    root = resolved_graph_root(graph_root)
    if not root.is_dir():
        return {**_status_without_snapshot("graph_root_missing"), "hits": []}
    paths = resolve_external_semantic_paths(root, settings)
    if not paths.published_db.exists():
        status = index_status(root, settings)
        return {**status, "hits": []}

    try:
        with closing(open_published_database(paths)) as connection:
            metadata = get_metadata(connection)
            if metadata.get("snapshot_complete") != "1":
                return {
                    **_status_without_snapshot("snapshot_incomplete"),
                    "snapshot_state": "incomplete",
                    "hits": [],
                }
            if not _profile_matches(metadata, settings):
                return {
                    **_status_without_snapshot("model_profile_mismatch"),
                    "snapshot_state": "complete",
                    "snapshot_complete": True,
                    "compatible": False,
                    "freshness": "model_mismatch",
                    "hits": [],
                }
            source_hashes, failures = _current_source_hashes(root)
            indexed = {
                str(source_path): str(source_hash)
                for source_path, source_hash in connection.execute(
                    "SELECT source_path, source_hash FROM indexed_pages"
                )
            }
            coverage = _coverage_counts(indexed, source_hashes)
            initial_unavailable_count = sum(failures.values())
            query_tokens = embedding_client.count_tokens(cleaned_query, add_special=True)
            if type(query_tokens) is not int or query_tokens < 0:
                raise ExternalSemanticError("token_count_invalid")
            if query_tokens > settings.max_input_tokens:
                raise ExternalSemanticError("query_too_large")
            query_vector = _normalized_vector(
                embedding_client.embed_text(cleaned_query),
                dimensions=settings.dimensions,
            )
            hits = _top_scoring_blocks(
                connection,
                source_hashes,
                query_vector,
                settings.dimensions,
                limit=limit,
            )
        rechecked: dict[str, str | None] = {}
        current_hits: list[dict[str, object]] = []
        rechecked_stale_paths: set[str] = set()
        rechecked_unavailable_paths: set[str] = set()
        rechecked_deleted_paths: set[str] = set()
        for hit in hits:
            source_path = str(hit["source_path"])
            current_hash = rechecked.get(source_path)
            if source_path not in rechecked:
                try:
                    current_hash = read_source_snapshot(
                        root / source_path,
                        root,
                        max_bytes=MAX_SOURCE_PAGE_BYTES,
                    ).source_hash
                except ExternalExtractionError:
                    current_hash = None
                rechecked[source_path] = current_hash
            if current_hash != hit["source_hash"]:
                rechecked_stale_paths.add(source_path)
                if current_hash is None:
                    if (root / source_path).exists():
                        rechecked_unavailable_paths.add(source_path)
                    else:
                        rechecked_deleted_paths.add(source_path)
                continue
            current_hits.append(hit)

        coverage["stale_page_count"] += len(rechecked_stale_paths)
        coverage["stale_indexed_page_count"] += len(rechecked_stale_paths)
        unavailable_count = initial_unavailable_count + len(rechecked_unavailable_paths)
        current_source_page_count = (
            len(source_hashes) + initial_unavailable_count - len(rechecked_deleted_paths)
        )
        freshness = (
            "unknown"
            if unavailable_count
            else "stale"
            if rechecked_stale_paths
            or coverage["stale_page_count"] > 0
            or coverage["unindexed_source_page_count"] > 0
            else "current_at_check"
        )
        return {
            "enabled": True,
            "snapshot_state": "complete",
            "snapshot_complete": True,
            "compatible": True,
            "freshness": freshness,
            "indexed_page_count": len(indexed),
            "current_source_page_count": current_source_page_count,
            "unavailable_source_page_count": unavailable_count,
            **coverage,
            "hits": current_hits,
        }
    except (ExternalSemanticStoreError, sqlite3.Error) as exc:
        return {
            **_status_without_snapshot(
                exc.code if isinstance(exc, ExternalSemanticStoreError) else "snapshot_invalid"
            ),
            "hits": [],
        }


def format_search_result(result: dict[str, object]) -> str:
    """Format citations and excerpts from an explicit semantic search request."""
    snapshot_state = str(result.get("snapshot_state", "unknown"))
    freshness = str(result.get("freshness", "unknown"))
    if freshness == "current_at_check":
        freshness = "current at the hash check"
    indexed = _int_value(result.get("indexed_page_count"))
    current = _int_value(result.get("current_source_page_count"))
    stale = _int_value(result.get("stale_page_count"))
    unindexed = _int_value(result.get("unindexed_source_page_count"))
    lines = [
        "External semantic index: "
        f"snapshot {snapshot_state}; source freshness {freshness}; "
        f"indexed pages {indexed}; current source pages {current}; "
        f"stale indexed pages {stale}; unindexed source pages {unindexed}."
    ]
    hits_obj = result.get("hits")
    hits = hits_obj if isinstance(hits_obj, list) else []
    if not hits:
        reason = result.get("error_code")
        if reason:
            lines.append(f"No semantic results ({reason}).")
        else:
            lines.append("No current semantic matches.")
        return "\n".join(lines)
    for raw in hits:
        if not isinstance(raw, Mapping):
            continue
        source_path = str(raw.get("source_path", ""))
        title = str(raw.get("title", ""))
        citation_id = str(raw.get("citation_id", ""))
        chunk_ordinal = _int_value(raw.get("chunk_ordinal"))
        score = _float_value(raw.get("score"))
        source_hash = str(raw.get("source_hash", ""))
        content = str(raw.get("content", ""))
        span_start = _int_value(raw.get("chunk_start_char"))
        span_end = _int_value(raw.get("chunk_end_char"))
        token_count = _int_value(raw.get("chunk_token_count"))
        fragment_count = _int_value(raw.get("chunk_count"))
        parent = raw.get("parent_citation_id")
        lines.append(
            f"- {title} ({source_path}), citation {citation_id}, "
            f"chunk {chunk_ordinal + 1}/{fragment_count}, block chars {span_start}:{span_end}, "
            f"input tokens {token_count}, score {score:.3f}, source SHA-256 {source_hash}\n"
            f"  {content}"
        )
        properties = raw.get("block_properties")
        if isinstance(properties, dict) and properties:
            encoded = json.dumps(properties, ensure_ascii=False, sort_keys=True)
            if len(encoded) > 2048:
                encoded = encoded[:2048] + "… [metadata preview truncated; full values in index]"
            lines.append(f"  Source block properties: {encoded}")
        if parent is not None:
            lines.append(f"  Parent block reference: {parent}")
    return "\n".join(lines)


def _open_resumable_working_db(
    paths: ExternalSemanticPaths,
    settings: ExternalSemanticSettings,
) -> sqlite3.Connection:
    if not paths.working_db.exists():
        _seed_working_from_published(paths, settings)
    connection = open_working_database(paths)
    metadata = get_metadata(connection)
    profile = _profile_metadata(settings)
    if any(metadata.get(key) != value for key, value in profile.items()):
        reset_working_database(connection)
        _begin(connection)
        set_metadata(connection, profile)
        connection.commit()
    return connection


def _seed_working_from_published(
    paths: ExternalSemanticPaths,
    settings: ExternalSemanticSettings,
) -> None:
    if not paths.published_db.is_file():
        return
    try:
        source = open_published_database(paths)
    except ExternalSemanticStoreError:
        return
    try:
        metadata = get_metadata(source)
        if not _profile_matches(metadata, settings) or metadata.get("snapshot_complete") != "1":
            return
        destination = sqlite3.connect(str(paths.working_db), timeout=settings.timeout_seconds)
        try:
            source.backup(destination)
            destination.commit()
        finally:
            destination.close()
    except sqlite3.Error:
        return
    finally:
        source.close()


def _index_page_transaction(
    connection: sqlite3.Connection,
    source_path: Path,
    extracted: ExtractedPage,
    graph_root: Path,
    embedding_client: EmbeddingClient,
    settings: ExternalSemanticSettings,
) -> None:
    source = extracted.source
    relative_path = source.relative_path
    _begin(connection)
    try:
        connection.execute("DELETE FROM indexed_pages WHERE source_path = ?", (relative_path,))
        connection.execute(
            "INSERT INTO indexed_pages "
            "(source_path, title, source_hash, source_size, source_mtime_ns, "
            "block_count, chunk_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                relative_path,
                source.title,
                source.source_hash,
                source.byte_count,
                source.mtime_ns,
                extracted.block_count,
                sum(len(block.chunks) for block in extracted.blocks),
            ),
        )
        for block in extracted.blocks:
            connection.execute(
                "INSERT INTO semantic_blocks "
                "(source_path, block_key, block_content_hash, block_length_chars, "
                "parent_citation_id, ancestor_citation_ids_json, properties_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    relative_path,
                    block.block_key,
                    block.block_content_hash,
                    len(block.content),
                    block.parent_citation_id,
                    json.dumps(block.ancestor_citation_ids),
                    json.dumps(block.properties, ensure_ascii=False, sort_keys=True),
                ),
            )
            for chunk_ordinal, chunk in enumerate(block.chunks):
                if (
                    not 0 <= chunk.start_char < chunk.end_char <= len(block.content)
                    or block.content[chunk.start_char : chunk.end_char] != chunk.text
                    or not 0 < chunk.token_count <= settings.max_input_tokens
                ):
                    raise ExternalSemanticError("chunk_provenance_invalid")
                vector = _normalized_vector(
                    embedding_client.embed_text(chunk.embedding_text),
                    dimensions=settings.dimensions,
                )
                blob = struct.pack(f"<{settings.dimensions}f", *vector)
                connection.execute(
                    "INSERT INTO semantic_vectors "
                    "(source_path, block_key, citation_id, persisted_uuid, block_ordinal, "
                    "chunk_ordinal, source_hash, content, vector, chunk_start_char, "
                    "chunk_end_char, token_count, context_text, split_kind) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        relative_path,
                        block.block_key,
                        block.citation_id,
                        block.persisted_uuid,
                        block.block_ordinal,
                        chunk_ordinal,
                        source.source_hash,
                        chunk.text,
                        blob,
                        chunk.start_char,
                        chunk.end_char,
                        chunk.token_count,
                        chunk.context_text,
                        chunk.split_kind,
                    ),
                )
        current = read_source_snapshot(
            source_path,
            graph_root,
            max_bytes=MAX_SOURCE_PAGE_BYTES,
        )
        if current.source_hash != source.source_hash:
            raise ExternalExtractionError("source_changed_during_index")
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def _working_page_matches(connection: sqlite3.Connection, source: SourceSnapshot) -> bool:
    row = connection.execute(
        "SELECT source_hash, source_size FROM indexed_pages WHERE source_path = ?",
        (source.relative_path,),
    ).fetchone()
    return (
        row is not None and str(row[0]) == source.source_hash and int(row[1]) == source.byte_count
    )


def _refresh_working_mtime(connection: sqlite3.Connection, source: SourceSnapshot) -> None:
    row = connection.execute(
        "SELECT source_mtime_ns FROM indexed_pages WHERE source_path = ?",
        (source.relative_path,),
    ).fetchone()
    if row is None or int(row[0]) == source.mtime_ns:
        return
    _begin(connection)
    connection.execute(
        "UPDATE indexed_pages SET source_mtime_ns = ? WHERE source_path = ?",
        (source.mtime_ns, source.relative_path),
    )
    connection.commit()


def _remove_deleted_working_pages(connection: sqlite3.Connection, current_paths: set[str]) -> None:
    indexed_paths = {
        str(row[0]) for row in connection.execute("SELECT source_path FROM indexed_pages")
    }
    removed = indexed_paths - current_paths
    if not removed:
        return
    _begin(connection)
    connection.executemany(
        "DELETE FROM indexed_pages WHERE source_path = ?",
        tuple((path,) for path in sorted(removed)),
    )
    connection.commit()


def _set_work_state(
    connection: sqlite3.Connection,
    state: str,
    failed_count: int,
    failure_codes: Mapping[str, int] | Iterable[tuple[str, int]],
) -> None:
    codes = dict(failure_codes)
    _begin(connection)
    set_metadata(
        connection,
        {
            "build_state": state,
            "last_failure_count": str(failed_count),
            "last_failure_codes": ",".join(f"{key}:{codes[key]}" for key in sorted(codes)),
            **_profile_from_connection(connection),
        },
    )
    connection.commit()


def _profile_from_connection(connection: sqlite3.Connection) -> dict[str, str]:
    metadata = get_metadata(connection)
    return {
        key: metadata[key]
        for key in ("pipeline_version", "model", "model_revision", "dimensions", "chunk_bytes")
        if key in metadata
    }


def _working_page_hashes(connection: sqlite3.Connection) -> dict[str, str]:
    return {
        str(source_path): str(source_hash)
        for source_path, source_hash in connection.execute(
            "SELECT source_path, source_hash FROM indexed_pages"
        )
    }


def _current_source_hashes(root: Path) -> tuple[dict[str, str], Counter[str]]:
    hashes: dict[str, str] = {}
    failures: Counter[str] = Counter()
    for source_path in iter_alias_source_paths(root):
        try:
            source = read_source_snapshot(source_path, root, max_bytes=MAX_SOURCE_PAGE_BYTES)
            hashes[source.relative_path] = source.source_hash
        except ExternalExtractionError as exc:
            failures[exc.code] += 1
    return hashes, failures


def _coverage_counts(indexed: Mapping[str, str], current: Mapping[str, str]) -> dict[str, int]:
    indexed_paths = set(indexed)
    current_paths = set(current)
    stale = sum(
        1 for path in indexed_paths if path not in current or indexed[path] != current.get(path)
    )
    return {
        "stale_page_count": stale,
        "stale_indexed_page_count": stale,
        "unindexed_source_page_count": len(current_paths - indexed_paths),
    }


def _top_scoring_blocks(
    connection: sqlite3.Connection,
    source_hashes: Mapping[str, str],
    query_vector: tuple[float, ...],
    dimensions: int,
    *,
    limit: int,
) -> list[dict[str, object]]:
    heap: list[tuple[float, int, dict[str, object]]] = []
    current_key: tuple[str, str] | None = None
    current_best: tuple[float, int, dict[str, object]] | None = None
    block_order = 0
    rows = connection.execute(
        "SELECT v.source_path, p.title, v.block_key, v.citation_id, v.persisted_uuid, "
        "v.block_ordinal, v.chunk_ordinal, v.source_hash, v.content, v.vector, "
        "v.chunk_start_char, v.chunk_end_char, v.token_count, v.context_text, v.split_kind "
        "FROM semantic_vectors AS v JOIN indexed_pages AS p USING(source_path) "
        "ORDER BY v.source_path, v.block_key, v.chunk_ordinal"
    )
    for row in rows:
        (
            source_path_raw,
            title_raw,
            block_key_raw,
            citation_id_raw,
            persisted_uuid_raw,
            block_ordinal_raw,
            chunk_ordinal_raw,
            source_hash_raw,
            content_raw,
            vector_raw,
            start_raw,
            end_raw,
            token_count_raw,
            context_raw,
            split_kind_raw,
        ) = row
        source_path = str(source_path_raw)
        source_hash = str(source_hash_raw)
        block_key = str(block_key_raw)
        row_key = (source_path, block_key)
        if current_key is not None and row_key != current_key:
            _keep_top_candidate(heap, current_best, limit)
            block_order += 1
            current_best = None
        if row_key != current_key:
            current_key = row_key
        if source_hashes.get(source_path) != source_hash:
            continue
        blob = bytes(vector_raw)
        if len(blob) != dimensions * 4:
            raise ExternalSemanticStoreError("stored_vector_dimension_invalid")
        vector = struct.unpack(f"<{dimensions}f", blob)
        if any(not math.isfinite(value) for value in vector):
            raise ExternalSemanticStoreError("stored_vector_invalid")
        norm = math.sqrt(math.fsum(value * value for value in vector))
        if not math.isfinite(norm) or norm <= 0.0:
            raise ExternalSemanticStoreError("stored_vector_zero_norm")
        score = math.sumprod(query_vector, vector)
        score = max(-1.0, min(1.0, score / norm))
        hit: dict[str, object] = {
            "source_path": source_path,
            "title": str(title_raw),
            "citation_id": str(citation_id_raw),
            "persisted_uuid": None if persisted_uuid_raw is None else str(persisted_uuid_raw),
            "block_ordinal": int(block_ordinal_raw),
            "chunk_ordinal": int(chunk_ordinal_raw),
            "source_hash": source_hash,
            "content": str(content_raw),
            "chunk_start_char": int(start_raw),
            "chunk_end_char": int(end_raw),
            "chunk_token_count": int(token_count_raw),
            "context_text": str(context_raw),
            "split_kind": str(split_kind_raw),
            "score": score,
            "_block_key": block_key,
        }
        previous = current_best
        if previous is None or score > previous[0]:
            current_best = (score, block_order, hit)
    _keep_top_candidate(heap, current_best, limit)
    heap.sort(key=lambda item: (-item[0], -item[1]))
    hits = [hit for _score, _order, hit in heap]
    # Decode potentially large properties only for the bounded selected hits.
    for hit in hits:
        block_key = str(hit.pop("_block_key"))
        hit.update(_read_block_metadata(connection, str(hit["source_path"]), block_key))
    return hits


def _read_block_metadata(
    connection: sqlite3.Connection,
    source_path: str,
    block_key: str,
) -> dict[str, object]:
    row = connection.execute(
        "SELECT block_content_hash, block_length_chars, parent_citation_id, "
        "ancestor_citation_ids_json, properties_json FROM semantic_blocks "
        "WHERE source_path = ? AND block_key = ?",
        (source_path, block_key),
    ).fetchone()
    if row is None:
        raise ExternalSemanticStoreError("stored_block_metadata_missing")
    try:
        ancestors = json.loads(row[3])
        properties = json.loads(row[4])
    except (ValueError, TypeError) as exc:
        raise ExternalSemanticStoreError("stored_block_metadata_invalid") from exc
    if (
        not isinstance(ancestors, list)
        or any(not isinstance(item, str) for item in ancestors)
        or not isinstance(properties, dict)
    ):
        raise ExternalSemanticStoreError("stored_block_metadata_invalid")
    count_row = connection.execute(
        "SELECT COUNT(*) FROM semantic_vectors WHERE source_path = ? AND block_key = ?",
        (source_path, block_key),
    ).fetchone()
    return {
        "block_content_hash": str(row[0]),
        "block_length_chars": int(row[1]),
        "parent_citation_id": str(row[2]) if row[2] is not None else None,
        "ancestor_citation_ids": ancestors,
        "block_properties": properties,
        "chunk_count": int(count_row[0]) if count_row else 0,
    }


def _keep_top_candidate(
    heap: list[tuple[float, int, dict[str, object]]],
    candidate: tuple[float, int, dict[str, object]] | None,
    limit: int,
) -> None:
    if candidate is None:
        return
    score, order, hit = candidate
    ranked = (score, -order, hit)
    if len(heap) < limit:
        heapq.heappush(heap, ranked)
    elif ranked[:2] > heap[0][:2]:
        heapq.heapreplace(heap, ranked)


def _normalized_vector(vector: Iterable[float], *, dimensions: int) -> tuple[float, ...]:
    try:
        values = tuple(float(value) for value in vector)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ExternalSemanticError("embedding_vector_invalid") from exc
    if len(values) != dimensions:
        raise ExternalSemanticError("embedding_dimension_mismatch")
    if any(not math.isfinite(value) for value in values):
        raise ExternalSemanticError("embedding_vector_nonfinite")
    try:
        norm = math.sqrt(math.fsum(value * value for value in values))
    except (OverflowError, ValueError) as exc:
        raise ExternalSemanticError("embedding_vector_invalid") from exc
    if not math.isfinite(norm) or norm <= 0.0:
        raise ExternalSemanticError("embedding_vector_zero_norm")
    normalized = tuple(value / norm for value in values)
    if any(not math.isfinite(value) for value in normalized):
        raise ExternalSemanticError("embedding_vector_nonfinite")
    return normalized


def _profile_metadata(settings: ExternalSemanticSettings) -> dict[str, str]:
    return {
        "pipeline_version": PIPELINE_VERSION,
        "model": str(settings.model),
        "model_revision": str(settings.model_revision),
        "dimensions": str(settings.dimensions),
        "target_tokens": str(settings.target_tokens),
        "max_input_tokens": str(settings.max_input_tokens),
        "context_tokens": str(settings.context_tokens),
        "overlap_tokens": str(settings.overlap_tokens),
        "max_input_bytes": str(settings.max_input_bytes),
        "tokenizer_policy": "llama_tokenize_special_parse_true_v1",
        "pooling": "cls",
        "normalization": "l2",
    }


def _profile_matches(metadata: Mapping[str, str], settings: ExternalSemanticSettings) -> bool:
    expected = _profile_metadata(settings)
    return all(metadata.get(key) == value for key, value in expected.items())


def _validate_profile(settings: ExternalSemanticSettings) -> None:
    if settings.dimensions <= 0 or settings.max_input_tokens <= 0:
        raise ExternalSemanticError("settings_invalid")
    if not settings.model.strip() or not settings.model_revision.strip():
        raise ExternalSemanticError("model_profile_unconfigured")


def _begin(connection: sqlite3.Connection) -> None:
    connection.execute("BEGIN IMMEDIATE")


def _build_result(
    connection: sqlite3.Connection,
    *,
    snapshot_complete: bool,
    failed_page_count: int,
    failure_codes: Mapping[str, int],
    published_snapshot_preserved: bool,
    resumable: bool,
    working_state: str,
) -> dict[str, object]:
    page_count, block_count, chunk_count = table_counts(connection)
    return {
        "snapshot_complete": snapshot_complete,
        "snapshot_state": "complete" if snapshot_complete else "incomplete",
        "published_snapshot_state": "preserved" if published_snapshot_preserved else "missing",
        "working_state": working_state,
        "indexed_page_count": page_count,
        "indexed_block_count": block_count,
        "chunk_count": chunk_count,
        "failed_page_count": failed_page_count,
        "failure_codes": [f"{code}:{failure_codes[code]}" for code in sorted(failure_codes)],
        "published_snapshot_preserved": published_snapshot_preserved,
        "resumable": resumable,
    }


def _failure_result(code: str, *, published: bool) -> dict[str, object]:
    return {
        "snapshot_complete": False,
        "snapshot_state": "incomplete",
        "published_snapshot_state": "preserved" if published else "missing",
        "working_state": "unavailable",
        "indexed_page_count": 0,
        "indexed_block_count": 0,
        "chunk_count": 0,
        "failed_page_count": 0,
        "failure_codes": [code],
        "published_snapshot_preserved": published,
        "resumable": True,
    }


def _status_without_snapshot(code: str | None) -> dict[str, object]:
    result: dict[str, object] = {
        "enabled": True,
        "snapshot_state": "missing" if code is None else "unavailable",
        "snapshot_complete": False,
        "compatible": False,
        "freshness": "unknown",
        "indexed_page_count": 0,
        "indexed_block_count": 0,
        "chunk_count": 0,
        "current_source_page_count": 0,
        "stale_page_count": 0,
        "stale_indexed_page_count": 0,
        "unindexed_source_page_count": 0,
        "unavailable_source_page_count": 0,
    }
    if code:
        result["error_code"] = code
    return result


def _disabled_result() -> dict[str, object]:
    return {
        "enabled": False,
        "snapshot_state": "disabled",
        "snapshot_complete": False,
        "compatible": False,
        "freshness": "unknown",
        "indexed_page_count": 0,
        "indexed_block_count": 0,
        "chunk_count": 0,
        "current_source_page_count": 0,
        "stale_page_count": 0,
        "stale_indexed_page_count": 0,
        "unindexed_source_page_count": 0,
        "unavailable_source_page_count": 0,
    }


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _int_value(value: object) -> int:
    if type(value) is int:
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def _float_value(value: object) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        parsed = float(value)
    elif isinstance(value, str):
        try:
            parsed = float(value)
        except ValueError:
            return 0.0
    else:
        return 0.0
    return parsed if math.isfinite(parsed) else 0.0


def _safe_error_code(exc: Exception) -> str:
    candidate = getattr(exc, "code", None)
    if (
        isinstance(candidate, str)
        and candidate
        and all(
            character.isascii() and (character.isalnum() or character in "_-")
            for character in candidate
        )
    ):
        return candidate[:80]
    return "page_processing_error"


__all__ = [
    "EmbeddingClient",
    "ExternalSemanticError",
    "format_search_result",
    "index_graph",
    "index_status",
    "search_graph",
]
