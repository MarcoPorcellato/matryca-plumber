#!/usr/bin/env python3
"""Verify the published PyPI ``matryca-plumber==2.0.0b1`` wheel in isolation.

The smoke uses only a temporary virtual environment and a synthetic temporary
vault. It never imports from the checkout and never touches an operator vault.

    uv run python scripts/smoke_postpublish_beta1_pypi.py
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PYPI_SPEC = "matryca-plumber==2.0.0b1"
EXPECTED_VERSION = "2.0.0b1"
BLOCK_UUID = "11111111-1111-4111-8111-111111111111"
CHILD_UUID = "22222222-2222-4222-8222-222222222222"


def _fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def _ok(label: str) -> None:
    print(f"OK  {label}")


def _clean_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    return env


def _shadow_env(graph: Path, *, enabled: bool) -> dict[str, str]:
    env = _clean_env()
    env["LOGSEQ_GRAPH_PATH"] = str(graph)
    env["MATRYCA_MCP_ENABLED"] = "false"
    if enabled:
        env["MATRYCA_SHADOW_DB_ENABLED"] = "true"
    else:
        env.pop("MATRYCA_SHADOW_DB_ENABLED", None)
    return env


def _shadow_db(graph: Path) -> Path:
    return graph / ".matryca_semantic_cache" / "shadow.sqlite"


def _markdown_fingerprint(graph: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(graph.rglob("*.md")):
        relative = path.relative_to(graph).as_posix()
        digest.update(relative.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _write_vault(graph: Path) -> None:
    (graph / "pages").mkdir(parents=True)
    (graph / "journals").mkdir(parents=True)
    (graph / "pages" / "Alpha.md").write_text(
        f"- alpha shadow term\n  id:: {BLOCK_UUID}\n  - child block\n    id:: {CHILD_UUID}\n",
        encoding="utf-8",
    )


def _install(venv_dir: Path) -> Path:
    if venv_dir.exists():
        shutil.rmtree(venv_dir)
    subprocess.run(
        ["uv", "venv", str(venv_dir)],
        check=True,
        cwd=tempfile.gettempdir(),
        env=_clean_env(),
    )
    python = venv_dir / "bin" / "python"
    subprocess.run(
        ["uv", "pip", "install", "--python", str(python), PYPI_SPEC],
        check=True,
        cwd=tempfile.gettempdir(),
        env=_clean_env(),
    )
    version = subprocess.run(
        [
            str(python),
            "-c",
            "import importlib.metadata as m; print(m.version('matryca-plumber'))",
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=tempfile.gettempdir(),
        env=_clean_env(),
    ).stdout.strip()
    if version != EXPECTED_VERSION:
        _fail(f"expected {EXPECTED_VERSION}, got {version!r}")
    return python


def _run(
    python: Path,
    graph: Path,
    code: str,
    *,
    shadow_enabled: bool,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(python), "-c", code],
        capture_output=True,
        text=True,
        timeout=900,
        cwd=tempfile.gettempdir(),
        env=_shadow_env(graph, enabled=shadow_enabled),
    )


def _assert_wheel_import(python: Path, graph: Path) -> None:
    code = """
from pathlib import Path
import src.shadow.bootstrap as bootstrap
module = Path(bootstrap.__file__).resolve()
assert "site-packages" in str(module), module
print(module)
"""
    result = _run(python, graph, code, shadow_enabled=False)
    if result.returncode != 0:
        _fail(f"import provenance: {result.stderr or result.stdout}")
    _ok(f"imports from published wheel ({result.stdout.strip()})")


def _assert_flag_off(python: Path, graph: Path) -> None:
    code = f"""
from pathlib import Path
from src.shadow.bootstrap import rebuild_shadow_from_graph
from src.shadow.config import shadow_db_enabled
from src.shadow.health import ShadowHealthState, resolve_shadow_health
graph = Path({str(graph)!r})
assert shadow_db_enabled() is False
assert resolve_shadow_health(graph) is ShadowHealthState.DISABLED
rebuild_shadow_from_graph(graph)
"""
    result = _run(python, graph, code, shadow_enabled=False)
    if result.returncode != 0:
        _fail(f"flag-off: {result.stderr or result.stdout}")
    if _shadow_db(graph).exists():
        _fail("flag-off created shadow.sqlite")
    _ok("flag-off preserves DISABLED health and creates no Shadow DB")


def _assert_flag_on(python: Path, graph: Path) -> None:
    code = f"""
from pathlib import Path
from src.shadow.bootstrap import ensure_shadow_runtime_at_startup, rebuild_shadow_from_graph
from src.shadow.connection import open_shadow_db
from src.shadow.health import ShadowHealthState, resolve_shadow_health
from src.shadow.meta import META_GENERATION, get_meta
from src.shadow.query import search_blocks_fts
from src.shadow.state_api import resolve_shadow_db_state_for_api
from src.shadow.subtree import SubtreeStatus, query_subtree_by_block_uuid

graph = Path({str(graph)!r})
rebuild_shadow_from_graph(graph)
assert resolve_shadow_health(graph) is ShadowHealthState.READY
connection = open_shadow_db(graph)
try:
    generation = get_meta(connection, META_GENERATION)
    tables = {{
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }}
    assert "quarantined_pages" in tables
    hits = search_blocks_fts(connection, "alpha", limit=5)
    assert hits
    subtree = query_subtree_by_block_uuid(
        connection,
        {BLOCK_UUID!r},
        max_depth=1,
    )
    assert subtree.status is SubtreeStatus.TRUNCATED, subtree.status
    assert len(subtree.nodes) == 1, len(subtree.nodes)
finally:
    connection.close()

snapshot = resolve_shadow_db_state_for_api(graph)
assert snapshot.state == "ready", snapshot
assert snapshot.quarantined_page_count == 0, snapshot
ensure_shadow_runtime_at_startup(graph)
connection = open_shadow_db(graph)
try:
    assert get_meta(connection, META_GENERATION) == generation
finally:
    connection.close()
print(generation)
"""
    result = _run(python, graph, code, shadow_enabled=True)
    if result.returncode != 0:
        _fail(f"flag-on: {result.stderr or result.stdout}")
    generation = result.stdout.strip().splitlines()[-1]
    _ok(f"flag-on reaches READY generation={generation}")
    _ok("FTS, subtree truncation, quarantine schema, and state API verified")
    _ok("warm startup preserves the generation")


def main() -> None:
    print(f"=== post-publish smoke PyPI {EXPECTED_VERSION} ===")
    with tempfile.TemporaryDirectory(prefix="mp-postpublish-b1-") as temporary:
        root = Path(temporary)
        graph = root / "vault"
        _write_vault(graph)
        baseline = _markdown_fingerprint(graph)

        python = _install(root / "venv")
        _assert_wheel_import(python, graph)
        _assert_flag_off(python, graph)
        _assert_flag_on(python, graph)

        if _markdown_fingerprint(graph) != baseline:
            _fail("Markdown fingerprint drift")
        _ok("Markdown bytes unchanged")

    print("=== ALL POST-PUBLISH BETA.1 SMOKE CHECKS PASSED ===")


if __name__ == "__main__":
    main()
