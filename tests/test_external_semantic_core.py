from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import pytest
import src.semantic.external as external_module
from src.semantic.external import (
    format_search_result,
    index_graph,
    index_status,
    search_graph,
)
from src.semantic.external_cli import main as external_cli_main
from src.semantic.external_config import ExternalSemanticSettings
from src.semantic.external_extract import (
    ExternalExtractionError,
    SourceSnapshot,
    extract_page_blocks,
    read_source_snapshot,
    split_utf8_chunks,
)
from src.semantic.external_store import (
    ExternalSemanticPaths,
    ExternalSemanticStoreError,
    exclusive_writer_lock,
    open_published_database,
    resolve_external_semantic_paths,
)

SqliteParameters = Sequence[object] | Mapping[str, object]


class FakeEmbeddings:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail_on: str | None = None
        self.on_embed: Callable[[str], None] | None = None

    def count_tokens(self, text: str, *, add_special: bool = True) -> int:
        return len(text) + (2 if add_special else 0)

    def embed_text(self, text: str) -> list[float]:
        self.calls.append(text)
        if self.on_embed is not None:
            self.on_embed(text)
        if self.fail_on is not None and self.fail_on in text:
            raise RuntimeError("synthetic_embedding_failure")
        lowered = text.casefold()
        if "alpha" in lowered or "needle" in lowered:
            return [1.0, 0.0, 0.0]
        if "beta" in lowered:
            return [0.0, 1.0, 0.0]
        return [0.5, 0.5, 0.0]


def _settings(cache_root: Path) -> ExternalSemanticSettings:
    return ExternalSemanticSettings(
        enabled=True,
        cache_root=cache_root,
        model="fixture-bge",
        model_revision="sha256:fixture",
        dimensions=3,
        base_url="http://127.0.0.1:8081/v1",
        unix_socket=None,
        timeout_seconds=1.0,
    )


def _hits(result: dict[str, object]) -> list[dict[str, object]]:
    raw_hits = result.get("hits")
    assert isinstance(raw_hits, list)
    hits: list[dict[str, object]] = []
    for raw_hit in raw_hits:
        assert isinstance(raw_hit, dict)
        assert all(isinstance(key, str) for key in raw_hit)
        hits.append({key: value for key, value in raw_hit.items() if isinstance(key, str)})
    return hits


def _string_list(result: dict[str, object], key: str) -> list[str]:
    raw_values = result.get(key)
    assert isinstance(raw_values, list)
    values: list[str] = []
    for value in raw_values:
        assert isinstance(value, str)
        values.append(value)
    return values


def _write_graph(graph: Path) -> None:
    (graph / "pages").mkdir(parents=True)
    (graph / "journals").mkdir()
    (graph / "pages" / "Alpha.md").write_bytes(
        b"- alpha needle in a page\n"
        b"  id:: 11111111-1111-4111-8111-111111111111\n"
        b"  - child alpha detail\n"
    )
    (graph / "journals" / "2026_10_26.md").write_bytes(b"- beta journal note\n")


def _graph_snapshot(graph: Path) -> dict[str, tuple[bytes, int]]:
    return {
        path.relative_to(graph).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in sorted(graph.rglob("*"))
        if path.is_file()
    }


def test_build_indexes_pages_and_journals_without_mutating_graph(tmp_path: Path) -> None:
    graph = tmp_path / "graph"
    _write_graph(graph)
    before = _graph_snapshot(graph)
    embeddings = FakeEmbeddings()
    settings = _settings(tmp_path / "cache")

    built = index_graph(graph, settings, embeddings)

    assert built["snapshot_complete"] is True
    assert built["indexed_page_count"] == 2
    assert built["indexed_block_count"] == 3
    assert built["chunk_count"] == 3
    assert built["failed_page_count"] == 0
    assert _graph_snapshot(graph) == before
    assert all("alpha needle" not in str(value) for value in built.values())

    status = index_status(graph, settings)
    assert status["snapshot_complete"] is True
    assert status["indexed_page_count"] == 2
    assert status["unindexed_source_page_count"] == 0
    assert status["stale_page_count"] == 0

    found = search_graph(graph, "alpha needle", settings, embeddings, limit=5)
    hits = _hits(found)
    assert hits
    top = hits[0]
    assert top["source_path"] == "pages/Alpha.md"
    assert top["persisted_uuid"] == "11111111-1111-4111-8111-111111111111"
    assert top["chunk_ordinal"] == 0
    source_hash = top.get("source_hash")
    assert isinstance(source_hash, str)
    assert len(source_hash) == 64
    assert top["score"] == pytest.approx(1.0)
    assert "alpha needle" in format_search_result(found)
    assert _graph_snapshot(graph) == before


def test_build_progress_is_content_free_and_emitted_per_source_page(tmp_path: Path) -> None:
    graph = tmp_path / "graph"
    _write_graph(graph)
    events: list[dict[str, object]] = []

    result = index_graph(
        graph,
        _settings(tmp_path / "cache"),
        FakeEmbeddings(),
        progress=events.append,
    )

    assert result["snapshot_complete"] is True
    page_events = [event for event in events if event["phase"] == "indexing"]
    assert len(page_events) == 2
    assert page_events[-1]["processed_page_count"] == 2
    assert all(
        not {"source_path", "title", "content", "text"}.intersection(event) for event in events
    )


def test_synthetic_citation_ids_are_distinct_and_chunking_keeps_utf8_bytes() -> None:
    chunks = split_utf8_chunks("A😀BéC", max_bytes=5)
    assert chunks == ["A😀", "BéC"]
    assert all(len(chunk.encode("utf-8")) <= 5 for chunk in chunks)
    with pytest.raises(ValueError, match="chunk_limit_too_small"):
        split_utf8_chunks("😀", max_bytes=3)


def test_uuidless_blocks_use_external_citation_ids(tmp_path: Path) -> None:
    graph = tmp_path / "graph"
    (graph / "pages").mkdir(parents=True)
    page = graph / "pages" / "No ID.md"
    page.write_bytes(b"- a child-only fact\n")
    settings = _settings(tmp_path / "cache")
    embeddings = FakeEmbeddings()
    index_graph(graph, settings, embeddings)

    found = search_graph(graph, "child", settings, embeddings)
    hits = _hits(found)
    assert hits
    hit = hits[0]
    assert hit["persisted_uuid"] is None
    assert str(hit["citation_id"]).startswith("synthetic:")
    assert hit["chunk_ordinal"] == 0


def test_exact_source_hash_preserves_crlf_and_empty_pages_are_coverage(tmp_path: Path) -> None:
    graph = tmp_path / "graph"
    pages = graph / "pages"
    pages.mkdir(parents=True)
    crlf = pages / "CRLF.md"
    crlf_bytes = b"- alpha note\r\n  id:: 22222222-2222-4222-8222-222222222222\r\n"
    crlf.write_bytes(crlf_bytes)
    empty = pages / "Empty.md"
    empty.write_bytes(b"")
    whitespace = pages / "Whitespace.md"
    whitespace.write_bytes(b"  \r\n\t\r\n")

    snapshot = read_source_snapshot(crlf, graph)
    assert snapshot.source_hash == hashlib.sha256(crlf_bytes).hexdigest()
    assert "\r\n" in snapshot.text
    parsed_empty = extract_page_blocks(
        read_source_snapshot(empty, graph),
        graph,
        settings=_settings(tmp_path / "cache"),
        tokenizer=FakeEmbeddings(),
    )
    parsed_whitespace = extract_page_blocks(
        read_source_snapshot(whitespace, graph),
        graph,
        settings=_settings(tmp_path / "cache"),
        tokenizer=FakeEmbeddings(),
    )
    assert parsed_empty.block_count == 0
    assert parsed_whitespace.block_count == 0

    embeddings = FakeEmbeddings()
    built = index_graph(graph, _settings(tmp_path / "cache"), embeddings)
    assert built["snapshot_complete"] is True
    assert built["indexed_page_count"] == 3
    assert built["indexed_block_count"] == 1
    assert built["chunk_count"] == 1


def test_in_graph_file_aliases_keep_their_graph_relative_citation_path(tmp_path: Path) -> None:
    graph = tmp_path / "graph"
    pages = graph / "pages"
    pages.mkdir(parents=True)
    (pages / "Source.md").write_bytes(b"- alpha source content\n")
    (pages / "Alias.md").symlink_to(pages / "Source.md")

    result = index_graph(graph, _settings(tmp_path / "cache"), FakeEmbeddings())
    status = index_status(graph, _settings(tmp_path / "cache"))

    assert result["snapshot_complete"] is True
    assert result["indexed_page_count"] == 2
    assert status["freshness"] == "current_at_check"


def test_same_size_preserved_mtime_source_edit_is_stale_and_not_returned(
    tmp_path: Path,
) -> None:
    graph = tmp_path / "graph"
    _write_graph(graph)
    settings = _settings(tmp_path / "cache")
    embeddings = FakeEmbeddings()
    index_graph(graph, settings, embeddings)

    path = graph / "pages" / "Alpha.md"
    original_stat = path.stat()
    old_bytes = path.read_bytes()
    replacement = old_bytes.replace(b"alpha needle", b"gamma needle")
    assert len(replacement) == len(old_bytes)
    path.write_bytes(replacement)
    os.utime(path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))

    status = index_status(graph, settings)
    assert status["snapshot_complete"] is True
    assert status["stale_page_count"] == 1
    assert status["unindexed_source_page_count"] == 0

    found = search_graph(graph, "alpha needle", settings, embeddings, limit=10)
    assert all(hit["source_path"] != "pages/Alpha.md" for hit in _hits(found))
    assert found["freshness"] == "stale"


def test_search_recheck_marks_a_source_changed_after_initial_hash_scan_as_stale(
    tmp_path: Path,
) -> None:
    graph = tmp_path / "graph"
    (graph / "pages").mkdir(parents=True)
    page = graph / "pages" / "Changing.md"
    page.write_bytes(b"- alpha needle remains in indexed snapshot\n")
    settings = _settings(tmp_path / "cache")
    embeddings = FakeEmbeddings()
    index_graph(graph, settings, embeddings)

    changed = False

    def edit_source_after_hash_scan(_text: str) -> None:
        nonlocal changed
        if not changed:
            changed = True
            page.write_bytes(b"- gamma needle replaced source\n")

    embeddings.on_embed = edit_source_after_hash_scan
    result = search_graph(graph, "alpha needle", settings, embeddings)

    assert _hits(result) == []
    assert result["freshness"] == "stale"
    assert result["stale_page_count"] == 1
    assert result["stale_indexed_page_count"] == 1


def test_late_unavailable_source_is_not_double_counted_as_current_page(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = tmp_path / "graph"
    (graph / "pages").mkdir(parents=True)
    page = graph / "pages" / "Changing.md"
    page.write_bytes(b"- alpha needle source\n")
    settings = _settings(tmp_path / "cache")
    embeddings = FakeEmbeddings()
    index_graph(graph, settings, embeddings)

    original_read = read_source_snapshot
    reads = 0

    def fail_on_final_recheck(
        source_path: Path,
        graph_root: str | Path,
        **kwargs: int,
    ) -> SourceSnapshot:
        nonlocal reads
        if source_path == page:
            reads += 1
            if reads == 2:
                raise ExternalExtractionError("source_read_error")
        return original_read(source_path, graph_root, **kwargs)

    monkeypatch.setattr(external_module, "read_source_snapshot", fail_on_final_recheck)
    result = search_graph(graph, "alpha needle", settings, embeddings)

    assert _hits(result) == []
    assert result["freshness"] == "unknown"
    assert result["current_source_page_count"] == 1
    assert result["unavailable_source_page_count"] == 1
    assert result["stale_page_count"] == 1


@pytest.mark.parametrize("operation", ["status", "search"])
def test_read_paths_close_published_database_connections(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    graph = tmp_path / "graph"
    _write_graph(graph)
    settings = _settings(tmp_path / "cache")
    embeddings = FakeEmbeddings()
    index_graph(graph, settings, embeddings)
    opened: list[sqlite3.Connection] = []
    original_open = open_published_database

    def track_open(paths: ExternalSemanticPaths) -> sqlite3.Connection:
        connection = original_open(paths)
        opened.append(connection)
        return connection

    monkeypatch.setattr(external_module, "open_published_database", track_open)
    if operation == "status":
        index_status(graph, settings)
    else:
        search_graph(graph, "alpha", settings, embeddings)

    assert len(opened) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        opened[0].execute("SELECT 1")


def test_semantic_scan_query_avoids_temporary_btree_sort(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = tmp_path / "graph"
    _write_graph(graph)
    settings = _settings(tmp_path / "cache")
    embeddings = FakeEmbeddings()
    index_graph(graph, settings, embeddings)
    paths = resolve_external_semantic_paths(graph, settings)
    db_uri = f"file:{paths.published_db}?mode=ro&immutable=1"
    connection = sqlite3.connect(db_uri, uri=True)
    details: list[str] = []

    class ExplainConnection:
        def __enter__(self) -> ExplainConnection:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def close(self) -> None:
            connection.close()

        def execute(self, sql: str, parameters: SqliteParameters = ()) -> sqlite3.Cursor:
            if sql.lstrip().startswith("SELECT v.source_path"):
                details.extend(
                    str(row[3])
                    for row in connection.execute(
                        "EXPLAIN QUERY PLAN " + sql,
                        parameters,
                    )
                )
            return connection.execute(sql, parameters)

    monkeypatch.setattr(
        external_module,
        "open_published_database",
        lambda _paths: ExplainConnection(),
    )
    search_graph(graph, "alpha", settings, embeddings)

    assert details
    assert not any("TEMP B-TREE" in detail.upper() for detail in details)


def test_new_source_pages_remain_unindexed_and_invisible_until_next_build(
    tmp_path: Path,
) -> None:
    graph = tmp_path / "graph"
    (graph / "pages").mkdir(parents=True)
    (graph / "pages" / "Alpha.md").write_bytes(b"- alpha existing note\n")
    settings = _settings(tmp_path / "cache")
    embeddings = FakeEmbeddings()
    index_graph(graph, settings, embeddings)
    (graph / "pages" / "New.md").write_bytes(b"- beta new concept\n")

    status = index_status(graph, settings)
    result = search_graph(graph, "beta", settings, embeddings)

    assert status["unindexed_source_page_count"] == 1
    assert status["freshness"] == "stale"
    assert all(hit["source_path"] != "pages/New.md" for hit in _hits(result))


def test_incomplete_build_remains_resumable_and_does_not_publish_partial_snapshot(
    tmp_path: Path,
) -> None:
    graph = tmp_path / "graph"
    _write_graph(graph)
    settings = _settings(tmp_path / "cache")
    embeddings = FakeEmbeddings()
    embeddings.fail_on = "beta"

    failed = index_graph(graph, settings, embeddings)

    assert failed["snapshot_complete"] is False
    assert failed["resumable"] is True
    assert failed["failed_page_count"] == 1
    assert failed["published_snapshot_preserved"] is False
    assert index_status(graph, settings)["snapshot_state"] == "missing"

    embeddings.fail_on = None
    resumed = index_graph(graph, settings, embeddings)
    assert resumed["snapshot_complete"] is True
    assert resumed["failed_page_count"] == 0
    assert index_status(graph, settings)["snapshot_state"] == "complete"


def test_failed_rebuild_preserves_last_complete_published_snapshot(tmp_path: Path) -> None:
    graph = tmp_path / "graph"
    _write_graph(graph)
    settings = _settings(tmp_path / "cache")
    embeddings = FakeEmbeddings()
    first = index_graph(graph, settings, embeddings)
    assert first["snapshot_complete"] is True
    published = next((tmp_path / "cache").rglob("semantic.sqlite"))
    previous_snapshot = published.read_bytes()

    alpha = graph / "pages" / "Alpha.md"
    alpha.write_bytes(alpha.read_bytes().replace(b"alpha", b"gamma"))
    embeddings.fail_on = "gamma"
    failed = index_graph(graph, settings, embeddings)

    assert failed["snapshot_complete"] is False
    assert failed["published_snapshot_preserved"] is True
    assert published.read_bytes() == previous_snapshot
    assert index_status(graph, settings)["freshness"] == "stale"


def test_deleted_pages_are_removed_before_complete_snapshot_publication(tmp_path: Path) -> None:
    graph = tmp_path / "graph"
    _write_graph(graph)
    settings = _settings(tmp_path / "cache")
    embeddings = FakeEmbeddings()
    assert index_graph(graph, settings, embeddings)["snapshot_complete"] is True
    (graph / "journals" / "2026_10_26.md").unlink()

    rebuilt = index_graph(graph, settings, embeddings)
    status = index_status(graph, settings)

    assert rebuilt["snapshot_complete"] is True
    assert rebuilt["indexed_page_count"] == 1
    assert status["indexed_page_count"] == 1
    assert status["stale_page_count"] == 0
    assert status["unindexed_source_page_count"] == 0
    assert status["freshness"] == "current_at_check"


def test_open_published_reader_keeps_old_snapshot_across_atomic_replacement(
    tmp_path: Path,
) -> None:
    graph = tmp_path / "graph"
    _write_graph(graph)
    settings = _settings(tmp_path / "cache")
    embeddings = FakeEmbeddings()
    index_graph(graph, settings, embeddings)
    published = next((tmp_path / "cache").rglob("semantic.sqlite"))
    old_reader = sqlite3.connect(f"file:{published}?mode=ro&immutable=1", uri=True)
    try:
        old_hash = old_reader.execute(
            "SELECT source_hash FROM indexed_pages WHERE source_path = 'pages/Alpha.md'"
        ).fetchone()[0]
        page = graph / "pages" / "Alpha.md"
        page.write_bytes(page.read_bytes().replace(b"alpha", b"gamma"))
        rebuilt = index_graph(graph, settings, embeddings)
        assert rebuilt["snapshot_complete"] is True
        assert (
            old_reader.execute(
                "SELECT source_hash FROM indexed_pages WHERE source_path = 'pages/Alpha.md'"
            ).fetchone()[0]
            == old_hash
        )
        with sqlite3.connect(f"file:{published}?mode=ro&immutable=1", uri=True) as new_reader:
            new_hash = new_reader.execute(
                "SELECT source_hash FROM indexed_pages WHERE source_path = 'pages/Alpha.md'"
            ).fetchone()[0]
        assert new_hash != old_hash
    finally:
        old_reader.close()


def test_source_change_during_embedding_does_not_commit_or_publish_page(tmp_path: Path) -> None:
    graph = tmp_path / "graph"
    (graph / "pages").mkdir(parents=True)
    page = graph / "pages" / "Changing.md"
    page.write_bytes(b"- alpha source\n")
    settings = _settings(tmp_path / "cache")
    embeddings = FakeEmbeddings()
    changed = False

    def edit_source(_text: str) -> None:
        nonlocal changed
        if not changed:
            changed = True
            page.write_bytes(b"- beta source\n")

    embeddings.on_embed = edit_source
    failed = index_graph(graph, settings, embeddings)

    assert failed["snapshot_complete"] is False
    assert "source_changed_during_index:1" in _string_list(failed, "failure_codes")
    assert failed["indexed_page_count"] == 0
    assert index_status(graph, settings)["snapshot_state"] == "missing"


def test_invalid_embedding_vector_is_explicit_and_does_not_publish(tmp_path: Path) -> None:
    graph = tmp_path / "graph"
    (graph / "pages").mkdir(parents=True)
    (graph / "pages" / "Alpha.md").write_bytes(b"- alpha fact\n")
    settings = _settings(tmp_path / "cache")

    class InvalidEmbeddings(FakeEmbeddings):
        def embed_text(self, text: str) -> list[float]:
            del text
            return [float("nan"), 0.0, 0.0]

    failed = index_graph(graph, settings, InvalidEmbeddings())

    assert failed["snapshot_complete"] is False
    assert "embedding_vector_nonfinite:1" in _string_list(failed, "failure_codes")
    assert index_status(graph, settings)["snapshot_state"] == "missing"


def test_oversized_source_is_reported_and_never_published(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = tmp_path / "graph"
    (graph / "pages").mkdir(parents=True)
    page = graph / "pages" / "Too large.md"
    page.write_bytes(b"- this is longer than the test cap\n")
    monkeypatch.setattr("src.semantic.external.MAX_SOURCE_PAGE_BYTES", 12)

    result = index_graph(graph, _settings(tmp_path / "cache"), FakeEmbeddings())

    assert result["snapshot_complete"] is False
    assert "source_page_too_large:1" in _string_list(result, "failure_codes")
    assert index_status(graph, _settings(tmp_path / "cache"))["snapshot_state"] == "missing"


def test_model_revision_mismatch_is_reported_and_search_skips_embedding(tmp_path: Path) -> None:
    graph = tmp_path / "graph"
    (graph / "pages").mkdir(parents=True)
    (graph / "pages" / "Alpha.md").write_bytes(b"- alpha fact\n")
    original_settings = _settings(tmp_path / "cache")
    index_graph(graph, original_settings, FakeEmbeddings())
    changed_settings = _settings(tmp_path / "cache").model_copy(
        update={"model_revision": "sha256:changed"}
    )
    embeddings = FakeEmbeddings()

    status = index_status(graph, changed_settings)
    result = search_graph(graph, "alpha", changed_settings, embeddings)

    assert status["snapshot_state"] == "complete"
    assert status["compatible"] is False
    assert status["freshness"] == "model_mismatch"
    assert _hits(result) == []
    assert embeddings.calls == []


def test_query_rejects_oversized_utf8_input_and_does_not_create_sidecars(
    tmp_path: Path,
) -> None:
    graph = tmp_path / "graph"
    _write_graph(graph)
    settings = _settings(tmp_path / "cache")
    embeddings = FakeEmbeddings()
    index_graph(graph, settings, embeddings)
    db_path = next((tmp_path / "cache").rglob("semantic.sqlite"))
    before = {
        path.name: (path.stat().st_size, path.stat().st_mtime_ns)
        for path in db_path.parent.iterdir()
        if path.is_file()
    }

    with pytest.raises(ValueError, match="query_too_large"):
        search_graph(graph, "😀" * (settings.max_input_bytes // 4 + 1), settings, embeddings)

    search_graph(graph, "alpha", settings, embeddings)
    after = {
        path.name: (path.stat().st_size, path.stat().st_mtime_ns)
        for path in db_path.parent.iterdir()
        if path.is_file()
    }
    assert after == before
    assert not any(name.endswith(("-wal", "-shm")) for name in after)


def test_cache_inside_graph_is_rejected_before_writes(tmp_path: Path) -> None:
    graph = tmp_path / "graph"
    _write_graph(graph)
    settings = _settings(graph / ".cache")

    with pytest.raises(ValueError, match="cache_path_inside_graph"):
        index_graph(graph, settings, FakeEmbeddings())

    assert _graph_snapshot(graph).keys() == {
        "pages/Alpha.md",
        "journals/2026_10_26.md",
    }


def test_writer_lock_serializes_index_builders(tmp_path: Path) -> None:
    graph = tmp_path / "graph"
    _write_graph(graph)
    settings = _settings(tmp_path / "cache")
    paths = resolve_external_semantic_paths(graph, settings)

    with (
        exclusive_writer_lock(paths, timeout_seconds=1.0),
        pytest.raises(ExternalSemanticStoreError, match="writer_lock_unavailable"),
        exclusive_writer_lock(paths, timeout_seconds=0.02),
    ):
        raise AssertionError("second writer unexpectedly acquired the lock")


def test_status_cli_is_read_only_and_does_not_initialize_embedding_transport(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    graph = tmp_path / "graph"
    _write_graph(graph)
    cache = tmp_path / "cache"
    monkeypatch.setenv("MATRYCA_EXTERNAL_SEMANTIC_ENABLED", "true")
    monkeypatch.setenv("MATRYCA_EXTERNAL_SEMANTIC_CACHE_PATH", str(cache))
    monkeypatch.setenv("MATRYCA_EXTERNAL_SEMANTIC_MODEL", "fixture-bge")
    monkeypatch.setenv("MATRYCA_EXTERNAL_SEMANTIC_MODEL_REVISION", "sha256:fixture")
    monkeypatch.setenv("MATRYCA_EXTERNAL_SEMANTIC_DIMENSIONS", "3")

    import src.semantic.external_embedding as external_embedding

    def fail_if_constructed(_settings: object) -> object:
        raise AssertionError("status must not construct embedding transport")

    monkeypatch.setattr(external_embedding, "ExternalEmbeddingClient", fail_if_constructed)
    before = _graph_snapshot(graph)
    code = external_cli_main(["status", "--graph-root", str(graph)])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["event"] == "status"
    assert payload["snapshot_state"] == "missing"
    assert payload["unindexed_source_page_count"] == 2
    assert not cache.exists()
    assert _graph_snapshot(graph) == before
