"""v2.0-alpha hardening — Axis 4: FTS5 (audit probes).

Read-only on ``src/`` — temporary vault fixtures exercise FTS5 query syntax,
indexed content contracts, BM25 ordering, sync/index parity, and failure
injection. Findings feed tracking issue #261.

Workflow: minimal reproducer → ``xfail(strict=True)`` only after confirmation
→ child issue → surgical fix PR → remove xfail.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from src.agent.dispatch_search_handlers import handle_search_bm25
from src.shadow.bootstrap import rebuild_shadow_from_graph
from src.shadow.connection import open_shadow_db, shadow_db_path
from src.shadow.fts_format import (
    MAX_FTS_MATCH_QUERY_CHARS,
    FtsQueryValidationError,
    format_shadow_fts_markdown,
    resolve_bm25_search_markdown,
    validate_fts_match_query,
)
from src.shadow.health import ShadowHealthState, resolve_shadow_health
from src.shadow.query import search_blocks_fts
from src.shadow.runtime_state import reset_shadow_runtime_state_for_tests
from src.shadow.sync import sync_page_to_shadow


@pytest.fixture(autouse=True)
def _shadow_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")
    monkeypatch.setenv("MATRYCA_SHADOW_DB_BUSY_TIMEOUT_MS", "200")
    reset_shadow_runtime_state_for_tests()


def _minimal_graph(tmp_path: Path) -> Path:
    graph = tmp_path / "vault"
    (graph / "pages").mkdir(parents=True)
    return graph


def _write_page(graph: Path, rel: str, body: str) -> Path:
    target = graph / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target


def _seed_fts_graph(graph: Path, *, keyword: str = "needle") -> str:
    block_uuid = "11111111-1111-4111-8111-111111111111"
    _write_page(
        graph,
        "pages/FtsProbe.md",
        f"- {keyword} shadow token here\n  id:: {block_uuid}\n",
    )
    rebuild_shadow_from_graph(graph)
    return block_uuid


def _fts_row_count(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM blocks_fts").fetchone()[0])


def _block_row_count(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM blocks").fetchone()[0])


# --- A4-QUERY ---


def test_a4_query_01_simple_token(tmp_path: Path) -> None:
    """A4-QUERY-01: single token returns the matching block."""
    graph = _minimal_graph(tmp_path)
    block_uuid = _seed_fts_graph(graph)
    conn = open_shadow_db(graph)
    try:
        hits = search_blocks_fts(conn, "needle")
        assert len(hits) == 1
        assert hits[0].block_uuid == block_uuid
    finally:
        conn.close()


def test_a4_query_02_multiple_tokens(tmp_path: Path) -> None:
    """A4-QUERY-02: implicit AND across multiple tokens."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/Multi.md",
        "- alpha beta gamma token\n  id:: 22222222-2222-4222-8222-222222222222\n",
    )
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        hits = search_blocks_fts(conn, "alpha gamma")
        assert len(hits) == 1
    finally:
        conn.close()


def test_a4_query_03_quoted_phrase(tmp_path: Path) -> None:
    """A4-QUERY-03: quoted phrase matches hyphenated block content."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/Phrase.md",
        "- state-of-the-art needle\n  id:: 33333333-3333-4333-8333-333333333333\n",
    )
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        hits = search_blocks_fts(conn, '"state-of-the-art"')
        assert len(hits) == 1
    finally:
        conn.close()


def test_a4_query_04_operators_and_parentheses(tmp_path: Path) -> None:
    """A4-QUERY-04: boolean OR with parentheses is supported when valid."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/Ops.md",
        "- alpha operator token\n  id:: 44444444-4444-4444-8444-444444444444\n"
        "- beta operator token\n  id:: 55555555-5555-4555-8555-555555555555\n",
    )
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        hits = search_blocks_fts(conn, "alpha OR beta")
        assert len(hits) == 2
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_a4_query_05_hyphenated_phrase_no_generational_fallback(
    tmp_path: Path,
) -> None:
    """A4-QUERY-05: hyphenated user input → shadow hit or validation error, never fallback."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/Hyphen.md",
        "- state-of-the-art needle\n  id:: 66666666-6666-4666-8666-666666666666\n",
    )
    rebuild_shadow_from_graph(graph)
    assert resolve_shadow_health(graph) == ShadowHealthState.READY

    out = await handle_search_bm25(str(graph), "state-of-the-art")
    assert "block `" in out
    assert "Hyphen.md" in out
    assert "Invalid FTS query" not in out


def test_a4_query_05b_hyphenated_ascii_token_hits(tmp_path: Path) -> None:
    """A4-QUERY-05b (#277): bare ASCII hyphenated token matches indexed block content."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/HyphenAscii.md",
        "- state-of-the-art token\n  id:: 67676767-6767-4676-8676-676767676767\n",
    )
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        hits = search_blocks_fts(conn, "state-of-the-art")
        assert len(hits) == 1
        assert "state-of-the-art" in hits[0].content
    finally:
        conn.close()


def test_a4_query_05c_unicode_dash_hyphenated_token(tmp_path: Path) -> None:
    """A4-QUERY-05c (#277): Unicode dash compounds are quoted like ASCII hyphens."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/HyphenUnicode.md",
        "- state–of–the–art token\n  id:: 68686868-6868-4686-8686-686868686868\n",
    )
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        hits = search_blocks_fts(conn, "state–of–the–art")
        assert len(hits) == 1
    finally:
        conn.close()


def test_a4_query_05d_leading_hyphen_is_not_compound_quoting(tmp_path: Path) -> None:
    """A4-QUERY-05d (#277): leading ``-`` remains FTS negation, not phrase quoting."""
    from src.shadow.query import prepare_fts_user_query

    assert prepare_fts_user_query("-needle") == "-needle"


def test_a4_query_05e_trailing_hyphen_not_auto_quoted(tmp_path: Path) -> None:
    """A4-QUERY-05e (#277): trailing hyphen tokens are not rewritten as compounds."""
    from src.shadow.query import prepare_fts_user_query

    assert prepare_fts_user_query("token-") == "token-"


def test_a4_query_05f_multi_term_with_one_hyphenated(tmp_path: Path) -> None:
    """A4-QUERY-05f (#277): mixed query quotes only the hyphenated bare token."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/MixHyphen.md",
        "- needle state-of-the-art token\n  id:: 69696969-6969-4696-8696-696969696969\n",
    )
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        hits = search_blocks_fts(conn, "needle state-of-the-art")
        assert len(hits) == 1
    finally:
        conn.close()


def test_a4_query_05g_quoted_hyphenated_phrase_unchanged(tmp_path: Path) -> None:
    """A4-QUERY-05g (#277): user-supplied quoted spans are not re-quoted."""
    from src.shadow.query import prepare_fts_user_query

    assert prepare_fts_user_query('"state-of-the-art"') == '"state-of-the-art"'


@pytest.mark.asyncio
async def test_a4_query_05h_hyphenated_with_supported_or_operator(tmp_path: Path) -> None:
    """A4-QUERY-05h (#277): hyphenated token coexists with explicit OR syntax."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/OrHyphen.md",
        "- alpha state-of-the-art token\n  id:: 70707070-7070-4707-8707-707070707070\n"
        "- beta plain token\n  id:: 71717171-7171-4717-8717-717171717171\n",
    )
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        hits = search_blocks_fts(conn, "state-of-the-art OR beta")
        assert len(hits) == 2
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_a4_query_05i_invalid_syntax_still_validation_error(tmp_path: Path) -> None:
    """A4-QUERY-05i (#277): truly invalid FTS input still raises validation error."""
    graph = _minimal_graph(tmp_path)
    _seed_fts_graph(graph)
    out = await handle_search_bm25(str(graph), '"unclosed')
    assert "Invalid FTS query" in out
    assert "## Ranked pages (BM25)" not in out


@pytest.mark.asyncio
async def test_a4_query_05j_backend_failure_still_generational_fallback(
    tmp_path: Path,
) -> None:
    """A4-QUERY-05j (#277): real SQLite backend failures still fall back once."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/FallbackHyphen.md",
        "- state-of-the-art fallback marker\n",
    )
    _seed_fts_graph(graph)
    with patch(
        "src.shadow.fts_format.search_blocks_fts",
        side_effect=sqlite3.OperationalError("database disk image is malformed"),
    ):
        out = await handle_search_bm25(str(graph), "state-of-the-art")
    assert "FallbackHyphen.md" in out
    assert "malformed" not in out


def test_a4_query_06_apostrophe_raises_validation_not_sqlite(tmp_path: Path) -> None:
    """A4-QUERY-06: apostrophe in query → public validation error (no raw SQLite leak)."""
    graph = _minimal_graph(tmp_path)
    _seed_fts_graph(graph)
    with pytest.raises(FtsQueryValidationError):
        format_shadow_fts_markdown(graph, "don't")


@pytest.mark.parametrize(
    ("body", "query", "expected_hits"),
    [
        pytest.param(
            "- café beverage\n  id:: 77777777-7777-4777-8777-777777777777\n",
            "cafe",
            1,
            id="cafe-acute",
        ),
        pytest.param(
            "- caffè beverage\n  id:: 88888888-8888-4888-8888-888888888888\n",
            "caffe",
            1,
            id="caffe-grave",
        ),
        pytest.param(
            "- caffè beverage\n  id:: 99999999-9999-4999-8999-999999999999\n",
            "cafe",
            0,
            id="cafe-misses-double-f",
        ),
        pytest.param(
            "- résumé text\n  id:: aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa\n", "resume", 1, id="resume"
        ),
        pytest.param(
            "- naïve idea\n  id:: bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb\n", "naive", 1, id="naive"
        ),
    ],
)
def test_a4_query_07_unicode_diacritic_fold(
    tmp_path: Path,
    body: str,
    query: str,
    expected_hits: int,
) -> None:
    """A4-QUERY-07: ``unicode61 remove_diacritics 2`` fold contract (#278).

    Diacritic folding is active (``résumé``→``resume``, ``naïve``→``naive``).
    ``caffè``→``caffe`` is not the same token as ``cafe`` (consonant-count gap);
    matching that pair would require fuzzy orthography, not accent removal alone.
    """
    graph = _minimal_graph(tmp_path)
    _write_page(graph, "pages/Accent.md", body)
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        assert len(search_blocks_fts(conn, query)) == expected_hits
    finally:
        conn.close()


def test_a4_query_08_whitespace_only_returns_empty(tmp_path: Path) -> None:
    """A4-QUERY-08: whitespace-only query returns no hits at FTS layer."""
    graph = _minimal_graph(tmp_path)
    _seed_fts_graph(graph)
    conn = open_shadow_db(graph)
    try:
        assert search_blocks_fts(conn, "   \t\n") == []
    finally:
        conn.close()


def test_a4_query_09_invalid_syntax_validation_error(tmp_path: Path) -> None:
    """A4-QUERY-09: unbalanced quotes rejected before SQLite."""
    with pytest.raises(FtsQueryValidationError):
        validate_fts_match_query('"unclosed')


def test_a4_query_10_very_long_query_bounded(tmp_path: Path) -> None:
    """A4-QUERY-10 (#279): overlong query rejected with validation error (bounded input)."""
    long_query = "needle " + ("x" * 5000)
    with pytest.raises(FtsQueryValidationError, match="exceeds max length"):
        validate_fts_match_query(long_query)


def test_a4_query_10b_length_at_limit_minus_one_accepted(tmp_path: Path) -> None:
    """A4-QUERY-10b (#279): query at limit-1 passes validation."""
    query = "n" * (MAX_FTS_MATCH_QUERY_CHARS - 1)
    validate_fts_match_query(query)


def test_a4_query_10c_length_at_limit_accepted(tmp_path: Path) -> None:
    """A4-QUERY-10c (#279): query at exact limit passes validation."""
    query = "n" * MAX_FTS_MATCH_QUERY_CHARS
    validate_fts_match_query(query)


def test_a4_query_10d_length_over_limit_rejected(tmp_path: Path) -> None:
    """A4-QUERY-10d (#279): query at limit+1 is rejected."""
    query = "n" * (MAX_FTS_MATCH_QUERY_CHARS + 1)
    with pytest.raises(FtsQueryValidationError, match="exceeds max length"):
        validate_fts_match_query(query)


def test_a4_query_10e_unicode_multibyte_counts_characters_not_bytes(tmp_path: Path) -> None:
    """A4-QUERY-10e (#279): limit uses Unicode code points, not UTF-8 byte length."""
    query = "café" + ("é" * (MAX_FTS_MATCH_QUERY_CHARS - 4))
    validate_fts_match_query(query)
    over = "café" + ("é" * (MAX_FTS_MATCH_QUERY_CHARS - 3))
    with pytest.raises(FtsQueryValidationError, match="exceeds max length"):
        validate_fts_match_query(over)


def test_a4_query_10f_whitespace_only_still_empty_at_fts_layer(tmp_path: Path) -> None:
    """A4-QUERY-10f (#279): whitespace-only input unchanged at FTS search layer."""
    graph = _minimal_graph(tmp_path)
    _seed_fts_graph(graph)
    conn = open_shadow_db(graph)
    try:
        assert search_blocks_fts(conn, "   \t\n") == []
    finally:
        conn.close()


def test_a4_query_10g_operator_prefix_hyphen_within_limit(tmp_path: Path) -> None:
    """A4-QUERY-10g (#279): operators, prefix, and hyphenated tokens within limit."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/BoundOps.md",
        "- alpha state-of-the-art prefixneedle token\n"
        "  id:: 19191919-1919-4191-8191-919191919191\n",
    )
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        query = 'alpha OR "state-of-the-art" prefix*'
        validate_fts_match_query(query)
        assert len(search_blocks_fts(conn, query)) == 1
    finally:
        conn.close()


def test_a4_query_10h_overlong_skips_sqlite_match() -> None:
    """A4-QUERY-10h (#279): overlong query never reaches SQLite ``MATCH``."""
    conn = MagicMock(spec=sqlite3.Connection)
    overlong = "n" * (MAX_FTS_MATCH_QUERY_CHARS + 1)
    with pytest.raises(FtsQueryValidationError):
        search_blocks_fts(conn, overlong)
    conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_a4_query_10i_overlong_public_bm25_validation_error(tmp_path: Path) -> None:
    """A4-QUERY-10i (#279): MCP/CLI BM25 envelope returns validation error, no fallback."""
    graph = _minimal_graph(tmp_path)
    _seed_fts_graph(graph)
    overlong = "needle " + ("x" * 5000)
    out = await handle_search_bm25(str(graph), overlong)
    assert "Invalid FTS query" in out
    assert "exceeds max length" in out
    assert "block `" not in out
    assert "xxxx" not in out


def test_a4_query_10j_overlong_error_message_bounded(tmp_path: Path) -> None:
    """A4-QUERY-10j (#279): validation error omits full query and vault paths."""
    graph = _minimal_graph(tmp_path)
    secret = "supersecretvaulttoken"
    _write_page(
        graph,
        f"pages/{secret}.md",
        "- body\n  id:: 20202020-2020-4202-8202-020202020202\n",
    )
    rebuild_shadow_from_graph(graph)
    overlong = secret + ("z" * 5000)
    with pytest.raises(FtsQueryValidationError) as exc:
        format_shadow_fts_markdown(graph, overlong)
    msg = str(exc.value)
    assert secret not in msg
    assert str(graph) not in msg
    assert len(msg) < 500


# --- A4-CONTENT ---


def test_a4_content_01_block_body_indexed_not_page_title(tmp_path: Path) -> None:
    """A4-CONTENT-01: only block ``content`` is indexed — page title alone is not."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/UniqueTitleOnlyXYZ.md",
        "- unrelated body words\n  id:: 88888888-8888-4888-8888-888888888888\n",
    )
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        assert search_blocks_fts(conn, "UniqueTitleOnlyXYZ") == []
        assert len(search_blocks_fts(conn, "unrelated")) == 1
    finally:
        conn.close()


def test_a4_content_02_properties_not_indexed(tmp_path: Path) -> None:
    """A4-CONTENT-02: block properties are not FTS-indexed (content column only)."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/Props.md",
        "- visible body\n"
        "  id:: 99999999-9999-4999-8999-999999999999\n"
        "  secret-prop:: needleonlyinproperty\n",
    )
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        assert search_blocks_fts(conn, "needleonlyinproperty") == []
        assert len(search_blocks_fts(conn, "visible")) == 1
    finally:
        conn.close()


def test_a4_content_03_unicode_in_body(tmp_path: Path) -> None:
    """A4-CONTENT-03: Unicode body text is searchable with accent preserved."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/Unicode.md",
        "- naïve résumé token\n  id:: aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa\n",
    )
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        assert len(search_blocks_fts(conn, "résumé")) == 1
        assert len(search_blocks_fts(conn, "resume")) == 1
    finally:
        conn.close()


def test_a4_content_04_markdown_punctuation_in_body(tmp_path: Path) -> None:
    """A4-CONTENT-04: markdown punctuation in body does not break indexing."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/Punct.md",
        "- **bold** _italic_ `code` token\n  id:: bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb\n",
    )
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        assert len(search_blocks_fts(conn, "token")) == 1
    finally:
        conn.close()


def test_a4_content_05_multiline_block_content(tmp_path: Path) -> None:
    """A4-CONTENT-05: multiline block content is indexed as a single FTS row."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/MultiLine.md",
        "- line one\n  line two continued\n  id:: cccccccc-cccc-4ccc-8ccc-cccccccccccc\n",
    )
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        assert len(search_blocks_fts(conn, "continued")) == 1
    finally:
        conn.close()


def test_a4_content_06_public_envelope_omits_raw_db_paths(tmp_path: Path) -> None:
    """A4-CONTENT-06: public BM25 envelope exposes rel path + block uuid, not SQLite internals."""
    graph = _minimal_graph(tmp_path)
    block_uuid = _seed_fts_graph(graph)
    md = format_shadow_fts_markdown(graph, "needle")
    assert f"block `{block_uuid}`" in md
    assert "pages/FtsProbe.md" in md
    assert "blocks_fts" not in md
    assert "rowid" not in md


# --- A4-RANK ---


def test_a4_rank_01_bm25_ordering_higher_relevance_first(tmp_path: Path) -> None:
    """A4-RANK-01: BM25 ranks exact token repetition above weak overlap."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/Rank.md",
        "- needle needle needle strong\n  id:: dddddddd-dddd-4ddd-8ddd-dddddddddddd\n"
        "- needle weak\n  id:: eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee\n",
    )
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        hits = search_blocks_fts(conn, "needle", limit=10)
        assert len(hits) == 2
        assert hits[0].block_uuid == "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
        assert hits[0].rank <= hits[1].rank
    finally:
        conn.close()


def test_a4_rank_02_tie_break_stable_across_connections(tmp_path: Path) -> None:
    """A4-RANK-02: identical BM25 scores return ascending UUIDs across connections."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/Tie.md",
        "- shared token\n  id:: ffffffff-ffff-4fff-8fff-ffffffffffff\n"
        "- shared token\n  id:: 10101010-1010-4101-8101-010101010101\n",
    )
    rebuild_shadow_from_graph(graph)

    def _uuids() -> list[str]:
        conn = open_shadow_db(graph)
        try:
            return [h.block_uuid for h in search_blocks_fts(conn, "shared", limit=10)]
        finally:
            conn.close()

    expected = [
        "10101010-1010-4101-8101-010101010101",
        "ffffffff-ffff-4fff-8fff-ffffffffffff",
    ]
    assert _uuids() == expected
    assert _uuids() == expected


def test_a4_rank_03_limit_boundaries(tmp_path: Path) -> None:
    """A4-RANK-03: limit is clamped to [1, 500]."""
    graph = _minimal_graph(tmp_path)
    lines = [f"- shared word {i}\n  id:: {i:08x}-1111-4111-8111-111111111111\n" for i in range(6)]
    _write_page(graph, "pages/Limits.md", "".join(lines))
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        assert len(search_blocks_fts(conn, "shared", limit=0)) == 1
        assert len(search_blocks_fts(conn, "shared", limit=2)) == 2
        assert len(search_blocks_fts(conn, "shared", limit=999)) == 6
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_a4_rank_04_zero_hits_no_generational_fallback(tmp_path: Path) -> None:
    """A4-RANK-04: zero FTS hits stay on shadow envelope (no generational fallback)."""
    graph = _minimal_graph(tmp_path)
    _seed_fts_graph(graph)
    out = await handle_search_bm25(str(graph), "zzznomatchzz")
    assert "- **Matches:** 0" in out
    assert "_No lexical overlap" in out
    assert "block `" not in out


# --- A4-SYNC ---


def test_a4_sync_01_full_rebuild_matches_incremental_create(tmp_path: Path) -> None:
    """A4-SYNC-01: full rebuild FTS rows match incremental sync for same Markdown."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/Sync.md",
        "- sync needle token\n  id:: 12121212-1212-4121-8121-212121212121\n",
    )
    rebuild_shadow_from_graph(graph)
    full_conn = open_shadow_db(graph)
    try:
        full_hits = search_blocks_fts(full_conn, "sync")
        full_fts_count = _fts_row_count(full_conn)
    finally:
        full_conn.close()

    graph2 = _minimal_graph(tmp_path.parent / "incr")
    page2 = _write_page(
        graph2,
        "pages/Sync.md",
        "- sync needle token\n  id:: 12121212-1212-4121-8121-212121212121\n",
    )
    sync_page_to_shadow(graph2, page2)
    incr_conn = open_shadow_db(graph2)
    try:
        incr_hits = search_blocks_fts(incr_conn, "sync")
        assert [h.block_uuid for h in incr_hits] == [h.block_uuid for h in full_hits]
        assert _fts_row_count(incr_conn) == full_fts_count
    finally:
        incr_conn.close()


def test_a4_sync_02_update_removes_stale_tokens(tmp_path: Path) -> None:
    """A4-SYNC-02: content update removes prior FTS tokens."""
    graph = _minimal_graph(tmp_path)
    page = _write_page(
        graph,
        "pages/Update.md",
        "- oldtoken value\n  id:: 13131313-1313-4131-8131-313131313131\n",
    )
    sync_page_to_shadow(graph, page)
    page.write_text(
        "- newtoken value\n  id:: 13131313-1313-4131-8131-313131313131\n",
        encoding="utf-8",
    )
    sync_page_to_shadow(graph, page)
    conn = open_shadow_db(graph)
    try:
        assert search_blocks_fts(conn, "oldtoken") == []
        assert len(search_blocks_fts(conn, "newtoken")) == 1
    finally:
        conn.close()


def test_a4_sync_03_delete_removes_hits(tmp_path: Path) -> None:
    """A4-SYNC-03: page delete removes FTS hits."""
    graph = _minimal_graph(tmp_path)
    page = _write_page(
        graph,
        "pages/Delete.md",
        "- deleteme token\n  id:: 14141414-1414-4141-8141-414141414141\n",
    )
    sync_page_to_shadow(graph, page)
    page.unlink()
    sync_page_to_shadow(graph, page)
    conn = open_shadow_db(graph)
    try:
        assert search_blocks_fts(conn, "deleteme") == []
        assert _block_row_count(conn) == 0
        assert _fts_row_count(conn) == 0
    finally:
        conn.close()


def test_a4_sync_04_rename_no_duplicate_hits(tmp_path: Path) -> None:
    """A4-SYNC-04: rename keeps a single FTS row per block uuid."""
    graph = _minimal_graph(tmp_path)
    old = _write_page(
        graph,
        "pages/RenameOld.md",
        "- rename token\n  id:: 15151515-1515-4151-8151-515151515151\n",
    )
    sync_page_to_shadow(graph, old)
    new = graph / "pages" / "RenameNew.md"
    old.rename(new)
    sync_page_to_shadow(graph, new)
    conn = open_shadow_db(graph)
    try:
        hits = search_blocks_fts(conn, "rename")
        assert len(hits) == 1
        assert hits[0].block_uuid == "15151515-1515-4151-8151-515151515151"
        assert _fts_row_count(conn) == _block_row_count(conn)
    finally:
        conn.close()


def test_a4_sync_05_repeated_rebuild_no_duplicate_fts_rows(tmp_path: Path) -> None:
    """A4-SYNC-05: consecutive full rebuilds keep FTS row count aligned with blocks."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/Rebuild.md",
        "- rebuild token\n  id:: 16161616-1616-4161-8161-616161616161\n",
    )
    rebuild_shadow_from_graph(graph)
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        assert _fts_row_count(conn) == _block_row_count(conn)
        assert len(search_blocks_fts(conn, "rebuild")) == 1
    finally:
        conn.close()


# --- A4-FAIL ---


def test_a4_fail_01_missing_fts_table_falls_back_once(tmp_path: Path) -> None:
    """A4-FAIL-01: missing ``blocks_fts`` → single generational BM25 fallback."""
    graph = _minimal_graph(tmp_path)
    _write_page(graph, "pages/Fallback.md", "fallback needle token\n")
    _seed_fts_graph(graph)
    conn = open_shadow_db(graph)
    try:
        conn.execute("DROP TABLE blocks_fts")
        conn.commit()
    finally:
        conn.close()

    with patch("src.shadow.fts_format.format_shadow_fts_markdown") as mocked:
        mocked.side_effect = sqlite3.OperationalError("no such table: blocks_fts")
        out = resolve_bm25_search_markdown(graph, "needle")
    assert "Fallback.md" in out
    assert mocked.call_count == 1


@pytest.mark.asyncio
async def test_a4_fail_02_sqlite_locked_falls_back_to_generational(
    tmp_path: Path,
) -> None:
    """A4-FAIL-02: SQLite busy/locked during FTS → generational fallback."""
    graph = _minimal_graph(tmp_path)
    _write_page(graph, "pages/Locked.md", "locked needle token\n")
    _seed_fts_graph(graph)

    with patch(
        "src.shadow.fts_format.search_blocks_fts",
        side_effect=sqlite3.OperationalError("database is locked"),
    ):
        out = await handle_search_bm25(str(graph), "needle")
    assert "Locked.md" in out
    assert "database is locked" not in out


@pytest.mark.asyncio
async def test_a4_fail_03_health_not_ready_skips_shadow_fts(tmp_path: Path) -> None:
    """A4-FAIL-03: health flip to ``error`` routes to generational BM25."""
    graph = _minimal_graph(tmp_path)
    _write_page(graph, "pages/Health.md", "health needle token\n")
    _seed_fts_graph(graph)
    conn = open_shadow_db(graph)
    try:
        conn.execute(
            "UPDATE shadow_meta SET value = ? WHERE key = ?",
            ("injected", "last_sync_error"),
        )
        conn.commit()
    finally:
        conn.close()
    assert resolve_shadow_health(graph) == ShadowHealthState.ERROR

    out = await handle_search_bm25(str(graph), "needle")
    assert "Health.md" in out
    assert "block `" not in out


def test_a4_fail_04_backend_exception_bounded_public_error(tmp_path: Path) -> None:
    """A4-FAIL-04: validation errors are bounded and omit vault secrets."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/Secret.md",
        "- supersecretvaulttoken\n  id:: 17171717-1717-4171-8171-717171717171\n",
    )
    _seed_fts_graph(graph)
    with pytest.raises(FtsQueryValidationError) as exc:
        format_shadow_fts_markdown(graph, '"bad')
    msg = str(exc.value)
    assert "supersecretvaulttoken" not in msg
    assert len(msg) < 500


def test_a4_fail_05_writer_lock_does_not_corrupt_fts_meta(tmp_path: Path) -> None:
    """A4-FAIL-05: SQLite writer lock surfaces as error without tearing FTS meta."""
    graph = _minimal_graph(tmp_path)
    page = _write_page(
        graph,
        "pages/Lock.md",
        "- lock token\n  id:: 18181818-1818-4181-8181-818181818181\n",
    )
    rebuild_shadow_from_graph(graph)
    holder = open_shadow_db(graph)
    holder.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(sqlite3.OperationalError):
            sync_page_to_shadow(graph, page)
    finally:
        holder.rollback()
        holder.close()
    assert resolve_shadow_health(graph) == ShadowHealthState.READY
    assert shadow_db_path(graph).is_file()
