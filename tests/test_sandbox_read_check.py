"""Smoke test for sandbox read_text CI guard."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from scripts import check_graph_read_sandbox as sandbox_check


def test_sandbox_read_check_passes_on_clean_tree() -> None:
    repo = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(repo / "scripts" / "check_graph_read_sandbox.py")],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_gateway_namespace_is_scanned_without_an_allowlist_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    relative_roots = tuple(
        root.relative_to(sandbox_check.REPO_ROOT) for root in sandbox_check.SCAN_ROOTS
    )
    assert Path("matryca_plumber") in relative_roots, "gateway namespace is outside the scan"
    root = tmp_path / "synthetic"
    path = root / "matryca_plumber/graph_gateway/read.py"
    path.parent.mkdir(parents=True)
    path.write_text("value = path.read_text()\n", encoding="utf-8")
    monkeypatch.setattr(sandbox_check, "REPO_ROOT", root)
    monkeypatch.setattr(sandbox_check, "SCAN_ROOTS", tuple(root / item for item in relative_roots))
    assert sandbox_check.main() == 1
