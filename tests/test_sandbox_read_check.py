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


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "import importlib.metadata\n"
            "def read_identity():\n"
            "    try:\n"
            "        distribution = importlib.metadata.distribution('matryca-plumber')\n"
            "        raw_identity = distribution.read_text('direct_url.json')\n"
            "    except importlib.metadata.PackageNotFoundError:\n"
            "        raw_identity = None\n",
            0,
        ),
        (
            "from pathlib import Path\n"
            "distribution = Path('identity.json')\n"
            "distribution.read_text('direct_url.json')\n",
            1,
        ),
        (
            "import importlib.metadata\n"
            "distribution = importlib.metadata.distribution('matryca-plumber')\n"
            "distribution.read_text(filename)\n",
            1,
        ),
        (
            "import importlib.metadata\n"
            "distribution = importlib.metadata.distribution(distribution_name)\n"
            "distribution.read_text('direct_url.json')\n",
            1,
        ),
        (
            "import importlib.metadata\n"
            "distribution = importlib.metadata.distribution('matryca-plumber')\n"
            "distribution.read_text('other.json')\n",
            1,
        ),
        (
            "import importlib.metadata\n"
            "def read_identity():\n"
            "    distribution = importlib.metadata.distribution('matryca-plumber')\n"
            "    distribution = object()\n"
            "    distribution.read_text('direct_url.json')\n",
            1,
        ),
        (
            "import importlib.metadata\n"
            "def read_identity():\n"
            "    distribution = importlib.metadata.distribution('matryca-plumber')\n"
            "    if uncertain:\n"
            "        distribution = object()\n"
            "    distribution.read_text('direct_url.json')\n",
            1,
        ),
        (
            "import importlib.metadata\n"
            "def read_identity(importlib):\n"
            "    distribution = importlib.metadata.distribution('matryca-plumber')\n"
            "    distribution.read_text('direct_url.json')\n",
            1,
        ),
        (
            "import importlib.metadata\n"
            "import fake_module as importlib\n"
            "distribution = importlib.metadata.distribution('matryca-plumber')\n"
            "distribution.read_text('direct_url.json')\n",
            1,
        ),
        (
            "import importlib.metadata\n"
            "from fake_module import importlib\n"
            "distribution = importlib.metadata.distribution('matryca-plumber')\n"
            "distribution.read_text('direct_url.json')\n",
            1,
        ),
        (
            "import importlib.metadata\n"
            "def read_identity(distribution):\n"
            "    distribution = importlib.metadata.distribution('matryca-plumber')\n"
            "    distribution.read_text('direct_url.json')\n",
            1,
        ),
        (
            "import importlib.metadata\n"
            "importlib.metadata.distribution = lambda _name: object()\n"
            "distribution = importlib.metadata.distribution('matryca-plumber')\n"
            "distribution.read_text('direct_url.json')\n",
            1,
        ),
        (
            "import importlib.metadata\n"
            "del importlib.metadata.distribution\n"
            "distribution = importlib.metadata.distribution('matryca-plumber')\n"
            "distribution.read_text('direct_url.json')\n",
            1,
        ),
        (
            "import importlib.metadata\n"
            "FakeDistribution.read_text = fake_read_text\n"
            "distribution = importlib.metadata.distribution('matryca-plumber')\n"
            "distribution.read_text('direct_url.json')\n",
            1,
        ),
        (
            "distribution = fake_distribution('matryca-plumber')\n"
            "distribution.read_text('direct_url.json')\n",
            1,
        ),
        (
            "import importlib.metadata\n"
            "from fake_module import *\n"
            "distribution = importlib.metadata.distribution('matryca-plumber')\n"
            "distribution.read_text('direct_url.json')\n",
            1,
        ),
        (
            "import importlib.metadata\n"
            "escaped_module = importlib\n"
            "escaped_module.metadata.distribution = fake_distribution\n"
            "distribution = importlib.metadata.distribution('matryca-plumber')\n"
            "distribution.read_text('direct_url.json')\n",
            1,
        ),
        (
            "import importlib.metadata\n"
            "mutate(importlib)\n"
            "distribution = importlib.metadata.distribution('matryca-plumber')\n"
            "distribution.read_text('direct_url.json')\n",
            1,
        ),
    ],
)
def test_metadata_read_exception_requires_proven_distribution_binding(
    source: str,
    expected: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "synthetic"
    path = root / "matryca_plumber/graph_gateway/identity.py"
    path.parent.mkdir(parents=True)
    path.write_text(source, encoding="utf-8")
    monkeypatch.setattr(sandbox_check, "REPO_ROOT", root)
    monkeypatch.setattr(sandbox_check, "SCAN_ROOTS", (root / "matryca_plumber",))

    assert sandbox_check.main() == expected
