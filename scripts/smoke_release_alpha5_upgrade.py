#!/usr/bin/env python3
"""Operational upgrade smoke: PyPI a4 → local a5 wheel on one vault.

Verifies #289 (CTE max_depth=1 → TRUNCATED) and #293 (state API path redaction).

Run from repo root after ``uv build`` (wheel ``2.0.0a5``):
    uv run python scripts/smoke_release_alpha5_upgrade.py
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPI_SPEC = "matryca-plumber==2.0.0a4"
WHEEL_GLOB = "matryca_plumber-2.0.0a5-*.whl"
EXPECTED_WHEEL_VERSION = "2.0.0a5"
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


def _write_vault(graph: Path) -> None:
    (graph / "pages").mkdir(parents=True)
    (graph / "journals").mkdir(parents=True)
    (graph / "pages" / "Alpha.md").write_text(
        f"- alpha shadow term\n  id:: {BLOCK_UUID}\n  - child block\n    id:: {CHILD_UUID}\n",
        encoding="utf-8",
    )
    (graph / "journals" / "2026_07_19.md").write_text(
        "- journal entry\n  id:: 33333333-3333-4333-8333-333333333333\n",
        encoding="utf-8",
    )


def _markdown_fingerprint(graph: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(graph.rglob("*.md")):
        if ".matryca_semantic_cache" in path.parts:
            continue
        rel = path.relative_to(graph).as_posix()
        h.update(rel.encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def _find_wheel() -> Path:
    wheels = sorted((ROOT / "dist").glob(WHEEL_GLOB))
    if not wheels:
        _fail(f"wheel not found ({WHEEL_GLOB}); run uv build first")
    return wheels[-1]


def _install_pypi_venv(venv_dir: Path) -> Path:
    if venv_dir.exists():
        shutil.rmtree(venv_dir)
    py = venv_dir / "bin" / "python"
    subprocess.run(["uv", "venv", str(venv_dir)], check=True, cwd=tempfile.gettempdir())
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
    if proc.stdout.strip() != "2.0.0a4":
        _fail(f"PyPI bootstrap expected 2.0.0a4, got {proc.stdout.strip()!r}")
    return py


def _install_wheel_venv(wheel: Path, venv_dir: Path) -> Path:
    if venv_dir.exists():
        shutil.rmtree(venv_dir)
    py = venv_dir / "bin" / "python"
    subprocess.run(["uv", "venv", str(venv_dir)], check=True, cwd=tempfile.gettempdir())
    subprocess.run(
        ["uv", "pip", "install", "--python", str(py), str(wheel)],
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
    if proc.stdout.strip() != EXPECTED_WHEEL_VERSION:
        _fail(f"wheel expected {EXPECTED_WHEEL_VERSION}, got {proc.stdout.strip()!r}")
    return py


def _run_py(
    py: Path,
    graph: Path,
    code: str,
    *,
    shadow: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(py), "-c", code],
        env=_env(graph, shadow=shadow),
        capture_output=True,
        text=True,
        cwd=tempfile.gettempdir(),
        timeout=180,
    )


def _shadow_db(graph: Path) -> Path:
    return graph / ".matryca_semantic_cache" / "shadow.sqlite"


def _read_meta(db: Path) -> dict[str, str]:
    conn = sqlite3.connect(db)
    try:
        return {str(k): str(v) for k, v in conn.execute("SELECT key, value FROM shadow_meta")}
    finally:
        conn.close()


def _assert_import_provenance(py: Path) -> None:
    code = f"""
from pathlib import Path
import src.shadow.subtree as s
root = Path({str(ROOT)!r}).resolve()
mod = Path(s.__file__).resolve()
assert str(root) not in str(mod), (root, mod)
assert "site-packages" in str(mod), mod
print(mod)
"""
    proc = _run_py(py, Path(tempfile.gettempdir()), code, shadow=False)
    if proc.returncode != 0:
        _fail(f"import provenance: {proc.stderr or proc.stdout}")
    _ok(f"imports from wheel ({proc.stdout.strip()})")


def _bootstrap_a4(py: Path, graph: Path) -> str:
    code = f"""
from pathlib import Path
from src.shadow.bootstrap import rebuild_shadow_from_graph
from src.shadow.health import ShadowHealthState, resolve_shadow_health
from src.shadow.meta import get_meta, META_GENERATION
from src.shadow.connection import open_shadow_db
g = Path({str(graph)!r})
rebuild_shadow_from_graph(g)
assert resolve_shadow_health(g) == ShadowHealthState.READY
conn = open_shadow_db(g)
try:
    gen = get_meta(conn, META_GENERATION)
finally:
    conn.close()
print(gen)
"""
    proc = _run_py(py, graph, code)
    if proc.returncode != 0:
        _fail(f"a4 bootstrap: {proc.stderr or proc.stdout}")
    generation = proc.stdout.strip()
    if not generation:
        _fail("missing generation after a4 bootstrap")
    _ok(f"PyPI a4 bootstrap (generation={generation})")
    return generation


def _check_289_293(py: Path, graph: Path) -> None:
    """#289 CTE truncation status + #293 state API path redaction."""
    leak = f"/tmp/SENSITIVE-VAULT/shadow.sqlite::{_shadow_db(graph)}"
    code = f"""
from pathlib import Path
from src.shadow.connection import open_shadow_db
from src.shadow.health import ShadowHealthState, resolve_shadow_health
from src.shadow.meta import META_LAST_SYNC_ERROR, set_meta
from src.shadow.state_api import resolve_shadow_db_state_for_api
from src.shadow.subtree import SubtreeStatus, query_subtree_by_block_uuid

g = Path({str(graph)!r})
assert resolve_shadow_health(g) == ShadowHealthState.READY
conn = open_shadow_db(g)
try:
    result = query_subtree_by_block_uuid(conn, {BLOCK_UUID!r}, max_depth=1)
    assert result.status is SubtreeStatus.TRUNCATED, result.status
    uuids = {{node.block_uuid for node in result.nodes}}
    assert uuids == {{{BLOCK_UUID!r}}}, uuids
    assert {CHILD_UUID!r} not in uuids
    set_meta(conn, META_LAST_SYNC_ERROR, "rebuild failed at {leak}")
    conn.commit()
finally:
    conn.close()

snap = resolve_shadow_db_state_for_api(g)
assert snap.state == "error", snap
assert snap.last_sync_error == {REDACTED!r}, snap.last_sync_error
assert "SENSITIVE-VAULT" not in (snap.last_sync_error or "")
assert {str(_shadow_db(graph))!r} not in (snap.last_sync_error or "")
print("289-293")
"""
    proc = _run_py(py, graph, code)
    if proc.returncode != 0:
        _fail(f"#289/#293 checks: {proc.stderr or proc.stdout}")
    _ok("#289 max_depth=1 TRUNCATED + #293 last_sync_error redacted")


def main() -> None:
    print("=== smoke: PyPI a4 → local a5 wheel upgrade (#289/#293) ===")
    subprocess.run(["uv", "build", "-q"], check=True, cwd=ROOT)
    wheel = _find_wheel()
    _ok(f"built wheel {wheel.name}")

    with tempfile.TemporaryDirectory(prefix="mp-smoke-a5-upgrade-") as tmp:
        graph = Path(tmp) / "vault"
        _write_vault(graph)
        baseline_md = _markdown_fingerprint(graph)

        print("\n-- phase 1: PyPI 2.0.0a4 bootstrap --")
        venv_a4 = Path(tmp) / "venv-a4"
        py_a4 = _install_pypi_venv(venv_a4)
        generation_a4 = _bootstrap_a4(py_a4, graph)
        db = _shadow_db(graph)
        if not db.is_file():
            _fail("shadow.sqlite missing after a4 bootstrap")

        print("\n-- phase 2: wheel 2.0.0a5 upgrade --")
        venv_a5 = Path(tmp) / "venv-a5"
        py_a5 = _install_wheel_venv(wheel, venv_a5)
        _assert_import_provenance(py_a5)

        warm = _run_py(
            py_a5,
            graph,
            f"""
from pathlib import Path
from src.shadow.bootstrap import ensure_shadow_runtime_at_startup
ensure_shadow_runtime_at_startup(Path({str(graph)!r}))
print("warm")
""",
        )
        if warm.returncode != 0:
            _fail(f"a5 warm startup: {warm.stderr or warm.stdout}")

        meta_a5 = _read_meta(db)
        if meta_a5.get("generation") != generation_a4:
            _fail(
                f"generation changed after upgrade: {generation_a4} → {meta_a5.get('generation')}"
            )
        _ok("generation/meta preserved across a4→a5")

        _check_289_293(py_a5, graph)

        after_md = _markdown_fingerprint(graph)
        if baseline_md != after_md:
            _fail("markdown fingerprint drift after upgrade smoke")

        _ok("markdown vault bytes unchanged")

    print("\n=== ALL A4→A5 UPGRADE SMOKE CHECKS PASSED ===")


if __name__ == "__main__":
    main()
