"""Check that ordinary installed evidence cannot be moved to another matrix row."""

import dataclasses
import hashlib
import json
from pathlib import Path
from typing import Literal

import pytest
from scripts.release_qualification.bundle import BundleBinding
from scripts.release_qualification.installed import BuildGenerator, InstalledReceipt


def _pair() -> BundleBinding:
    return BundleBinding(
        "a" * 40,
        "b" * 40,
        "2.1.0rc1",
        "matryca_plumber-2.1.0rc1-py3-none-any.whl",
        81,
        "c" * 64,
        "matryca_plumber-2.1.0rc1.tar.gz",
        97,
        "d" * 64,
        "e" * 64,
        "f" * 64,
    )


def _receipt(kind: Literal["wheel", "sdist"] = "sdist") -> InstalledReceipt:
    packages = (("logseq-matryca-parser", "1.11.4"), ("pydantic", "2.13.4"))
    return InstalledReceipt(
        kind,
        "darwin",
        "arm64",
        "3.13.18",
        "2.1.0rc1",
        "isolated-venv-site-packages",
        "0" * 64,
        "1" * 64,
        hashlib.sha256(json.dumps(packages, separators=(",", ":")).encode()).hexdigest(),
        packages,
        BuildGenerator("setuptools", "84.1.0"),
        ("PASS", "PASS", "PASS"),
    )


def test_sdist_report_keeps_original_archive_identity(tmp_path: Path) -> None:
    from scripts.release_qualification.first_stable_installed import write_installed_row

    destination = tmp_path / "installed.json"
    write_installed_row(
        destination,
        "current-macos-arm64-cpython-3.13.18-sdist",
        "v2.1.0-rc.1",
        _pair(),
        dict(_receipt().dependencies),
        _receipt(),
    )
    payload = json.loads(destination.read_bytes())
    assert payload["row_key"] == "current-macos-arm64-cpython-3.13.18-sdist"
    assert payload["source_commit"] == "a" * 40
    assert payload["source_tree"] == "b" * 40
    assert payload["original_artifact"] == {
        "name": "matryca_plumber-2.1.0rc1.tar.gz",
        "size": 97,
        "sha256": "d" * 64,
    }
    assert payload["installed"]["dependencies"][0] == {
        "name": "logseq-matryca-parser",
        "version": "1.11.4",
    }
    with pytest.raises(FileExistsError):
        write_installed_row(
            destination,
            "current-macos-arm64-cpython-3.13.18-sdist",
            "v2.1.0-rc.1",
            _pair(),
            dict(_receipt().dependencies),
            _receipt(),
        )


@pytest.mark.parametrize(
    ("row", "changes"),
    [
        ("current-macos-arm64-cpython-3.13.18-sdist", {"kind": "wheel"}),
        ("current-macos-arm64-cpython-3.13.18-sdist", {"architecture": "x86_64"}),
        ("current-macos-arm64-cpython-3.13.18-sdist", {"operating_system": "linux"}),
        ("current-macos-arm64-cpython-3.13.18-sdist", {"python_version": "3.13.17"}),
        ("current-macos-arm64-cpython-3.13.18-sdist", {"version": "2.1.0a4"}),
        ("current-macos-arm64-cpython-3.13.18-sdist", {"location_class": "editable"}),
        ("current-macos-arm64-cpython-3.13.18-sdist", {"tck_outcomes": ("PASS", "SKIP", "PASS")}),
        ("current-macos-arm64-cpython-3.13.18-sdist", {"dependency_sha256": "f" * 64}),
        ("minimum-macos-arm64-cpython-3.13.18-sdist", {}),
        ("current-windows-x64-cpython-3.13.18-sdist", {}),
    ],
)
def test_invalid_installed_slot_never_writes_report(
    tmp_path: Path, row: str, changes: dict[str, object]
) -> None:
    from scripts.release_qualification.first_stable_installed import write_installed_row

    destination = tmp_path / "installed.json"
    receipt = _receipt()
    with pytest.raises(ValueError):
        write_installed_row(
            destination,
            row,
            "v2.1.0-rc.1",
            _pair(),
            dict(receipt.dependencies),
            dataclasses.replace(receipt, **changes),  # type: ignore[arg-type]
        )
    assert not destination.exists()


def test_matching_parser_is_not_enough_when_closure_differs(tmp_path: Path) -> None:
    from scripts.release_qualification.first_stable_installed import write_installed_row

    destination = tmp_path / "installed.json"
    with pytest.raises(ValueError, match="closure"):
        write_installed_row(
            destination,
            "current-macos-arm64-cpython-3.13.18-sdist",
            "v2.1.0-rc.1",
            _pair(),
            {"logseq-matryca-parser": "1.11.4", "pydantic": "2.13.3"},
            _receipt(),
        )
    assert not destination.exists()


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_integrated_verifier_receives_only_the_original_of_the_selected_kind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: Literal["wheel", "sdist"]
) -> None:
    from scripts.release_qualification import first_stable_installed as adapter

    originals = tmp_path / "dist"
    originals.mkdir()
    pair = _pair()
    (originals / pair.wheel_name).write_bytes(b"original wheel")
    (originals / pair.sdist_name).write_bytes(b"original sdist")
    installed_python = tmp_path / "env/bin/python"
    receipt = _receipt(kind)

    def verify(
        python: Path,
        binding: BundleBinding,
        source_root: Path,
        selected_kind: Literal["wheel", "sdist"],
        *,
        artifact: Path,
        policy: str,
    ) -> InstalledReceipt:
        assert python == installed_python
        assert binding == pair
        assert source_root == tmp_path
        assert selected_kind == kind
        assert artifact.parent == originals
        assert artifact.read_bytes() == f"original {kind}".encode()
        assert policy == "og-alpha3"
        return receipt

    monkeypatch.setattr(adapter, "verify_installed", verify)
    report = tmp_path / "installed.json"
    adapter.verify_and_write_installed_row(
        output=report,
        row_key=f"current-macos-arm64-cpython-3.13.18-{kind}",
        candidate_tag="v2.1.0-rc.1",
        binding=pair,
        expected_dependencies=dict(receipt.dependencies),
        installed_python=installed_python,
        source_root=tmp_path,
        originals=originals,
    )
    artifact = json.loads(report.read_bytes())["original_artifact"]
    assert artifact["sha256"] == ("c" if kind == "wheel" else "d") * 64


def test_verifier_failure_is_not_installation_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts.release_qualification import first_stable_installed as adapter

    def fail(*_args: object, **_kwargs: object) -> InstalledReceipt:
        raise ValueError("original archive authentication failed")

    monkeypatch.setattr(adapter, "verify_installed", fail)
    output = tmp_path / "installed.json"
    with pytest.raises(ValueError, match="archive authentication"):
        adapter.verify_and_write_installed_row(
            output=output,
            row_key="current-macos-arm64-cpython-3.13.18-wheel",
            candidate_tag="v2.1.0-rc.1",
            binding=_pair(),
            expected_dependencies=dict(_receipt().dependencies),
            installed_python=tmp_path / "env/bin/python",
            source_root=tmp_path,
            originals=tmp_path / "dist",
        )
    assert not output.exists()
