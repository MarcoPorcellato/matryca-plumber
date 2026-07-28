#!/usr/bin/env python3
"""Post-publish smoke for PyPI ``matryca-plumber==2.0.0a5`` (temp or real vault copy).

Uses only the published wheel (no local checkout / no PYTHONPATH).

    uv run python scripts/smoke_postpublish_alpha5_pypi.py            # temp vault
    uv run python scripts/smoke_postpublish_alpha5_pypi.py /path/vault # existing vault
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PYPI_SPEC = "matryca-plumber==2.0.0a5"
EXPECTED = "2.0.0a5"
BLOCK_UUID = "11111111-1111-4111-8111-111111111111"
CHILD_UUID = "22222222-2222-4222-8222-222222222222"
REDACTED = "Shadow sync error (path details redacted)"


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def _ok(label: str) -> None:
    print(f"OK  {label}")


def _clean_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    return env


def _env(graph: Path, *, shadow: bool) -> dict[str, str]:
    env = _clean_env()
    env["LOGSEQ_GRAPH_PATH"] = str(graph)
    env["MATRYCA_MCP_ENABLED"] = "false"
    if shadow:
        env["MATRYCA_SHADOW_DB_ENABLED"] = "true"
    else:
        env.pop("MATRYCA_SHADOW_DB_ENABLED", None)
    return env


def _shadow_db(graph: Path) -> Path:
    return graph / ".matryca_semantic_cache" / "shadow.sqlite"


def _markdown_fingerprint(graph: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(graph.rglob("*.md")):
        if ".matryca_semantic_cache" in path.parts or ".git" in path.parts:
            continue
        rel = path.relative_to(graph).as_posix()
        h.update(rel.encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def _write_temp_vault(graph: Path) -> None:
    (graph / "pages").mkdir(parents=True)
    (graph / "journals").mkdir(parents=True)
    (graph / "pages" / "Alpha.md").write_text(
        f"- alpha shadow term\n  id:: {BLOCK_UUID}\n  - child block\n    id:: {CHILD_UUID}\n",
        encoding="utf-8",
    )


def _install(venv_dir: Path) -> Path:
    if venv_dir.exists():
        shutil.rmtree(venv_dir)
    subprocess.run(["uv", "venv", str(venv_dir)], check=True, cwd=tempfile.gettempdir())
    py = venv_dir / "bin" / "python"
    subprocess.run(
        ["uv", "pip", "install", "--python", str(py), PYPI_SPEC],
        check=True,
        cwd=tempfile.gettempdir(),
        env=_clean_env(),
    )
    proc = subprocess.run(
        [str(py), "-c", "import importlib.metadata as m; print(m.version('matryca-plumber'))"],
        capture_output=True,
        text=True,
        check=True,
        env=_clean_env(),
        cwd=tempfile.gettempdir(),
    )
    if proc.stdout.strip() != EXPECTED:
        _fail(f"expected {EXPECTED}, got {proc.stdout.strip()!r}")
    return py


def _run(py: Path, graph: Path, code: str, *, shadow: bool) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(py), "-c", code],
        env=_env(graph, shadow=shadow),
        capture_output=True,
        text=True,
        cwd=tempfile.gettempdir(),
        timeout=900,
    )


def _assert_wheel_import(py: Path) -> None:
    code = """
from pathlib import Path
import src.shadow.subtree as s
mod = Path(s.__file__).resolve()
assert "site-packages" in str(mod), mod
print(mod)
"""
    proc = _run(py, Path(tempfile.gettempdir()), code, shadow=False)
    if proc.returncode != 0:
        _fail(f"import provenance: {proc.stderr or proc.stdout}")
    _ok(f"imports from PyPI wheel ({proc.stdout.strip()})")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("vault", nargs="?", help="Existing vault root (optional)")
    args = parser.parse_args()

    print(f"=== post-publish smoke PyPI {EXPECTED} ===")
    with tempfile.TemporaryDirectory(prefix="mp-postpublish-a5-") as tmp:
        tmp_path = Path(tmp)
        venv = tmp_path / "venv"
        py = _install(venv)
        _assert_wheel_import(py)

        if args.vault:
            graph = Path(args.vault).resolve()
            if not (graph / "pages").is_dir():
                _fail(f"vault missing pages/: {graph}")
            mode = "real-vault-copy"
        else:
            graph = tmp_path / "vault"
            _write_temp_vault(graph)
            mode = "temp-vault"
        _ok(f"mode={mode} graph={graph}")

        baseline = _markdown_fingerprint(graph)
        db = _shadow_db(graph)

        print("\n-- flag OFF --")
        if db.exists():
            # real soak may start with leftover cache; record only, do not delete
            _ok("pre-existing shadow.sqlite present (left untouched for flag-off probe)")
        code_off = f"""
from pathlib import Path
from src.shadow.config import shadow_db_enabled
from src.shadow.health import ShadowHealthState, resolve_shadow_health
from src.shadow.bootstrap import rebuild_shadow_from_graph
g = Path({str(graph)!r})
assert shadow_db_enabled() is False
assert resolve_shadow_health(g) == ShadowHealthState.DISABLED
rebuild_shadow_from_graph(g)  # no-op when flag off
print("disabled")
"""
        proc = _run(py, graph, code_off, shadow=False)
        if proc.returncode != 0:
            _fail(f"flag-off: {proc.stderr or proc.stdout}")
        if mode == "temp-vault" and db.exists():
            _fail("flag-off created shadow.sqlite on fresh vault")
        _ok("flag-off: health DISABLED, no create on fresh vault")

        print("\n-- flag ON bootstrap --")
        code_on = f"""
from pathlib import Path
from src.shadow.bootstrap import rebuild_shadow_from_graph, ensure_shadow_runtime_at_startup
from src.shadow.connection import open_shadow_db
from src.shadow.health import ShadowHealthState, resolve_shadow_health
from src.shadow.meta import (
    META_GENERATION, META_INDEXED_PAGE_COUNT, META_LAST_SYNC_ERROR,
    META_SOURCE_PAGE_COUNT, get_meta, set_meta,
)
from src.shadow.query import search_blocks_fts
from src.shadow.state_api import resolve_shadow_db_state_for_api
from src.shadow.subtree import SubtreeStatus, query_subtree_by_block_uuid

g = Path({str(graph)!r})
rebuild_shadow_from_graph(g)
assert resolve_shadow_health(g) == ShadowHealthState.READY
conn = open_shadow_db(g)
try:
    gen = get_meta(conn, META_GENERATION)
    src = get_meta(conn, META_SOURCE_PAGE_COUNT)
    idx = get_meta(conn, META_INDEXED_PAGE_COUNT)
    assert src == idx, (src, idx)
    # Prefer seeded UUID on temp vault; else a parent that has a direct child (#289)
    anchor = {BLOCK_UUID!r}
    if not conn.execute(
        "SELECT 1 FROM blocks WHERE block_uuid=?", (anchor,)
    ).fetchone():
        sql = (
            "SELECT p.block_uuid FROM blocks p "
            "JOIN blocks c ON c.parent_rowid = p.rowid "
            "ORDER BY p.rowid LIMIT 1"
        )
        parent_row = conn.execute(sql).fetchone()
        if parent_row is None:
            raise AssertionError("no parent/child pair for CTE truncation probe")
        anchor = parent_row[0]
    result = query_subtree_by_block_uuid(conn, anchor, max_depth=1)
    assert result.status is SubtreeStatus.TRUNCATED, (result.status, anchor)
    assert len(result.nodes) == 1, len(result.nodes)
    hits = search_blocks_fts(conn, "a", limit=5)
    assert isinstance(hits, list)
    set_meta(conn, META_LAST_SYNC_ERROR, "rebuild failed at /tmp/SENSITIVE-VAULT/shadow.sqlite")
    conn.commit()
finally:
    conn.close()
snap = resolve_shadow_db_state_for_api(g)
assert snap.state == "error", snap
assert snap.last_sync_error == {REDACTED!r}, snap.last_sync_error
assert "SENSITIVE-VAULT" not in (snap.last_sync_error or "")
# second startup idempotent after clearing error for warm path
conn = open_shadow_db(g)
try:
    set_meta(conn, META_LAST_SYNC_ERROR, "")
    conn.commit()
    gen2 = get_meta(conn, META_GENERATION)
finally:
    conn.close()
ensure_shadow_runtime_at_startup(g)
ensure_shadow_runtime_at_startup(g)
conn = open_shadow_db(g)
try:
    assert get_meta(conn, META_GENERATION) == gen2
finally:
    conn.close()
print(gen)
print(src)
print(idx)
"""
        proc = _run(py, graph, code_on, shadow=True)
        if proc.returncode != 0:
            _fail(f"flag-on: {proc.stderr or proc.stdout}")
        lines = [ln for ln in proc.stdout.strip().splitlines() if ln.strip()]
        generation, source, indexed = lines[-3], lines[-2], lines[-1]
        _ok(f"flag-on ready generation={generation} source={source} indexed={indexed}")
        _ok("#289 TRUNCATED (when child exists) + #293 path redaction")
        _ok("second startup idempotent (generation preserved)")

        after = _markdown_fingerprint(graph)
        if after != baseline:
            _fail("markdown fingerprint drift")
        _ok("markdown bytes unchanged")

    print("\n=== ALL POST-PUBLISH A5 SMOKE CHECKS PASSED ===")


if __name__ == "__main__":
    main()
