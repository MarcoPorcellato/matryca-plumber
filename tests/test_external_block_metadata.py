"""Each semantic fragment retains its original block identity and provenance."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from src.semantic.external import format_search_result, index_graph, search_graph
from src.semantic.external_config import ExternalSemanticSettings
from src.semantic.external_store import resolve_external_semantic_paths


class CountingEmbeddings:
    def count_tokens(self, text: str, *, add_special: bool = True) -> int:
        return len(text) + (2 if add_special else 0)

    def embed_text(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]


def test_long_block_fragments_preserve_properties_parent_and_exact_source_spans(
    tmp_path: Path,
) -> None:
    graph = tmp_path / "graph"
    (graph / "pages").mkdir(parents=True)
    parent_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    body = " ".join(
        f"Frase numero {number} con una decisione da ritrovare." for number in range(60)
    )
    raw = (
        f"- Progetto di migrazione.\n  id:: {parent_id}\n"
        f"  - {body}\n    id:: {child_id}\n    priority:: A\n"
    ).encode()
    page = graph / "pages" / "Progetto.md"
    page.write_bytes(raw)
    before = (page.read_bytes(), page.stat().st_mtime_ns)
    settings = ExternalSemanticSettings(
        enabled=True,
        cache_root=tmp_path / "cache",
        model="fixture",
        model_revision="fixture",
        dimensions=3,
    )
    client = CountingEmbeddings()

    result = index_graph(graph, settings, client)
    assert result["snapshot_complete"] is True
    found = search_graph(graph, "decisione", settings, client, limit=10)
    hits = found["hits"]
    assert isinstance(hits, list)
    hit = next(item for item in hits if item["persisted_uuid"] == child_id)
    assert hit["parent_citation_id"] == parent_id
    assert hit["ancestor_citation_ids"] == [parent_id]
    assert hit["block_properties"]["priority"] == "A"
    assert hit["block_content_hash"] == hashlib.sha256(body.encode()).hexdigest()
    assert hit["source_hash"] == hashlib.sha256(raw).hexdigest()
    assert hit["chunk_count"] > 1
    assert hit["chunk_token_count"] <= settings.max_input_tokens
    assert hit["content"] == body[hit["chunk_start_char"] : hit["chunk_end_char"]]
    formatted = format_search_result(found)
    assert "block chars" in formatted
    assert '"priority": "A"' in formatted

    paths = resolve_external_semantic_paths(graph, settings)
    with closing(
        sqlite3.connect(f"{paths.published_db.as_uri()}?mode=ro&immutable=1", uri=True)
    ) as db:
        metadata = db.execute(
            "SELECT properties_json, parent_citation_id FROM semantic_blocks "
            "WHERE block_content_hash = ?",
            (hit["block_content_hash"],),
        ).fetchall()
        assert len(metadata) == 1
        assert json.loads(metadata[0][0])["priority"] == "A"
        assert metadata[0][1] == parent_id
        chunks = db.execute(
            "SELECT content, chunk_start_char, chunk_end_char, token_count "
            "FROM semantic_vectors WHERE persisted_uuid = ? "
            "ORDER BY chunk_ordinal",
            (child_id,),
        ).fetchall()
        covered: set[int] = set()
        for text, start, end, tokens in chunks:
            assert text == body[start:end]
            assert tokens <= settings.max_input_tokens
            covered.update(range(start, end))
        assert covered == set(range(len(body)))
    assert (page.read_bytes(), page.stat().st_mtime_ns) == before


def test_explicit_rebuild_replaces_incompatible_work_schema_without_touching_sources(
    tmp_path: Path,
) -> None:
    graph = tmp_path / "graph"
    (graph / "pages").mkdir(parents=True)
    page = graph / "pages" / "Example.md"
    raw = b"- A complete source block.\n"
    page.write_bytes(raw)
    settings = ExternalSemanticSettings(
        enabled=True,
        cache_root=tmp_path / "cache",
        model="fixture",
        model_revision="fixture",
        dimensions=3,
    )
    client = CountingEmbeddings()
    assert index_graph(graph, settings, client)["snapshot_complete"] is True
    paths = resolve_external_semantic_paths(graph, settings)
    with closing(sqlite3.connect(paths.working_db)) as db:
        db.execute("DROP TABLE semantic_vectors")
        db.execute("DROP TABLE semantic_blocks")
        db.execute(
            "CREATE TABLE semantic_vectors (source_path TEXT, block_key TEXT, "
            "citation_id TEXT, persisted_uuid TEXT, block_ordinal INTEGER, "
            "chunk_ordinal INTEGER, source_hash TEXT, content TEXT, vector BLOB)"
        )
        db.execute(
            "UPDATE semantic_meta SET value = 'content-chunks-v1' WHERE key = 'pipeline_version'"
        )
        db.commit()
    rebuilt = index_graph(graph, settings, client)
    assert rebuilt["snapshot_complete"] is True
    assert page.read_bytes() == raw
