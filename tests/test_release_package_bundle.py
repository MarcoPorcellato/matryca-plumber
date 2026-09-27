"""Synthetic adversarial tests for release-bundle verification."""

from __future__ import annotations

import hashlib
import io
import json
import os
import struct
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest
import scripts.build_release_artifacts as release_builder
import scripts.release_qualification.bundle as bundle_module
from scripts.release_qualification.bundle import (
    BundleBinding,
    build_binding,
    canonical_manifest,
    verify_handoff,
)

VERSION = "2.0.1rc4"
WHEEL_NAME = "matryca_plumber-2.0.1rc4-py3-none-any.whl"
SDIST_NAME = "matryca_plumber-2.0.1rc4.tar.gz"
PREFIX = "matryca_plumber-2.0.1rc4"
RESOURCE = "contracts/plumber.graph.read/v1/schema.json"
WHEEL_RESOURCE = f"src/contract_artifacts/{RESOURCE}"
TCK_SOURCE = "scripts/run_plumber_graph_read_v1_tck.py"
WHEEL_TCK = "src/contract_artifacts/tck/run_plumber_graph_read_v1_tck.py"
MODULE = "src/worker.py"
FRONTEND = "frontend/dist/assets/app.js"
SOURCE_BYTES = {
    "pyproject.toml": b"[project]\nname='matryca-plumber'\nversion='2.0.1rc4'\n",
    "README.md": b"Synthetic release package fixture.\n",
    "MANIFEST.in": b"graft contracts\n",
    "setup.py": b"from setuptools import setup\nsetup()\n",
    "LICENSE": b"Apache License 2.0\n",
    "NOTICE": b"Copyright 2026\n",
    "src/__init__.py": b"",
    MODULE: b"VALUE = 1\n",
    "tests/test_sample.py": b"def test_sample():\n    assert True\n",
    "frontend/__init__.py": b"",
    **{
        name: f"fixture resource: {name}\n".encode()
        for name in release_builder._SOURCE_CONTRACT_RESOURCE_MEMBERS
    },
}
FRONTEND_BYTES = {
    "frontend/dist/index.html": b"<!doctype html>\n",
    FRONTEND: b"export const value = 1;\n",
}
WHEEL_METADATA = {
    f"{PREFIX}.dist-info/METADATA": (
        b"Metadata-Version: 2.4\nName: matryca-plumber\nVersion: 2.0.1rc4\n\n"
    ),
    f"{PREFIX}.dist-info/WHEEL": b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\n",
    f"{PREFIX}.dist-info/entry_points.txt": b"[console_scripts]\nmatryca=src.cli:main\n",
    f"{PREFIX}.dist-info/top_level.txt": b"frontend\nsrc\n",
    f"{PREFIX}.dist-info/RECORD": b"",
    f"{PREFIX}.dist-info/licenses/LICENSE": SOURCE_BYTES["LICENSE"],
    f"{PREFIX}.dist-info/licenses/NOTICE": SOURCE_BYTES["NOTICE"],
}

SDIST_EGG_INFO = "matryca_plumber.egg-info"
SDIST_METADATA = {
    "PKG-INFO": b"Metadata-Version: 2.4\nName: matryca-plumber\nVersion: 2.0.1rc4\n\n",
    "setup.cfg": b"[egg_info]\ntag_build =\n",
    f"{SDIST_EGG_INFO}/PKG-INFO": (
        b"Metadata-Version: 2.4\nName: matryca-plumber\nVersion: 2.0.1rc4\n\n"
    ),
    f"{SDIST_EGG_INFO}/SOURCES.txt": b"fixture\n",
    f"{SDIST_EGG_INFO}/dependency_links.txt": b"",
    f"{SDIST_EGG_INFO}/entry_points.txt": b"[console_scripts]\nmatryca=src.cli:main\n",
    f"{SDIST_EGG_INFO}/requires.txt": b"pydantic>=2\n",
    f"{SDIST_EGG_INFO}/top_level.txt": b"frontend\nsrc\n",
}
METADATA_CLASSES = [
    "wheel.dist-info.METADATA",
    "wheel.dist-info.WHEEL",
    "wheel.dist-info.RECORD",
    "wheel.dist-info.entry_points.txt",
    "wheel.dist-info.top_level.txt",
    "wheel.dist-info.licenses.LICENSE",
    "wheel.dist-info.licenses.NOTICE",
    "sdist.PKG-INFO",
    "sdist.setup.cfg",
    "sdist.egg-info.PKG-INFO",
    "sdist.egg-info.SOURCES.txt",
    "sdist.egg-info.dependency_links.txt",
    "sdist.egg-info.entry_points.txt",
    "sdist.egg-info.requires.txt",
    "sdist.egg-info.top_level.txt",
]


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_repo(tmp_path: Path) -> tuple[Path, str, str, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    for name, payload in SOURCE_BYTES.items():
        destination = repo / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Release Test",
            "-c",
            "user.email=release-test@example.invalid",
            "commit",
            "-qm",
            "release fixture",
        ],
        cwd=repo,
        check=True,
    )
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=repo, text=True).strip()
    ledger = tmp_path / "content-ledger.json"
    content = {
        "schema_version": 1,
        "source_commit": commit,
        "source_tree": tree,
        "version": VERSION,
        "selected_source_files": [
            {"name": name, "sha256": _sha256(payload)}
            for name, payload in sorted(SOURCE_BYTES.items())
        ],
        "frontend_files": [
            {"name": name, "sha256": _sha256(payload)}
            for name, payload in sorted(FRONTEND_BYTES.items())
        ],
        "generated_metadata_classes": METADATA_CLASSES,
    }
    ledger.write_text(json.dumps(content), encoding="utf-8")
    return repo, commit, tree, ledger


def _wheel_members(*, omit: str | None = None) -> dict[str, bytes]:
    members = {
        **{name: payload for name, payload in SOURCE_BYTES.items() if name.startswith("src/")},
        **{
            f"src/contract_artifacts/{name}": payload
            for name, payload in SOURCE_BYTES.items()
            if name.startswith("contracts/")
        },
        **{
            f"src/contract_artifacts/tck/{Path(name).name}": payload
            for name, payload in SOURCE_BYTES.items()
            if name in release_builder._SOURCE_CONTRACT_RESOURCE_MEMBERS
            and name.startswith("scripts/")
        },
        **{
            name: payload
            for name, payload in SOURCE_BYTES.items()
            if name == "frontend/__init__.py"
        },
        **FRONTEND_BYTES,
        **WHEEL_METADATA,
    }
    if omit is not None:
        members.pop(omit, None)
    return members


def _sdist_members(*, omit: str | None = None) -> dict[str, bytes]:
    members = {
        **{f"{PREFIX}/{name}": payload for name, payload in SOURCE_BYTES.items()},
        **{f"{PREFIX}/{name}": payload for name, payload in FRONTEND_BYTES.items()},
        **{f"{PREFIX}/{name}": payload for name, payload in SDIST_METADATA.items()},
    }
    if omit is not None:
        members.pop(f"{PREFIX}/{omit}", None)
    return members


def _write_pair(
    dist: Path,
    *,
    wheel_members: dict[str, bytes] | None = None,
    sdist_members: dict[str, bytes] | None = None,
    sdist_directories: tuple[str, ...] = (),
) -> tuple[Path, Path]:
    dist.mkdir(parents=True, exist_ok=True)
    wheel = dist / WHEEL_NAME
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, payload in (wheel_members or _wheel_members()).items():
            archive.writestr(name, payload)
    sdist = dist / SDIST_NAME
    with tarfile.open(sdist, "w:gz") as archive:
        for name, payload in (sdist_members or _sdist_members()).items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
        for name in sdist_directories:
            info = tarfile.TarInfo(f"{PREFIX}/{name}")
            info.type = tarfile.DIRTYPE
            archive.addfile(info)
    return wheel, sdist


def _patch_wheel_eocd(path: Path, *, offset: int, fmt: str, value: int) -> None:
    with path.open("r+b") as stream:
        contents = stream.read()
        eocd = contents.rfind(b"PK\x05\x06")
        assert eocd >= 0
        stream.seek(eocd + offset)
        stream.write(struct.pack(fmt, value))


def _binding(tmp_path: Path, dist: Path) -> BundleBinding:
    repo, commit, _tree, ledger = _write_repo(tmp_path)
    return build_binding(repo, dist, ledger, commit)


def test_build_binding_accepts_exact_single_pair_with_normalized_version(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    _write_pair(dist)

    binding = _binding(tmp_path, dist)

    assert binding.version == VERSION
    assert binding.wheel_name == WHEEL_NAME
    assert binding.sdist_name == SDIST_NAME
    assert binding.wheel_size == (dist / WHEEL_NAME).stat().st_size
    assert len(binding.wheel_sha256) == 64
    assert len(binding.wheel_inventory_sha256) == 64


@pytest.mark.parametrize(
    ("wheel_members", "sdist_members", "extra_files", "message"),
    [
        (_wheel_members(omit=MODULE), _sdist_members(omit=MODULE), (), "missing"),
        (_wheel_members(omit=FRONTEND), _sdist_members(omit=FRONTEND), (), "missing"),
        (_wheel_members(omit=WHEEL_RESOURCE), _sdist_members(omit=RESOURCE), (), "missing"),
        (_wheel_members(), _sdist_members(), ("unexpected.whl",), "exactly one"),
        (_wheel_members(), _sdist_members(), ("unexpected.tar.gz",), "exactly one"),
        (_wheel_members(), _sdist_members(), ("notes.txt",), "unexpected"),
        (
            {**_wheel_members(), WHEEL_RESOURCE: b'{"schema":"changed"}\n'},
            _sdist_members(),
            (),
            "digest",
        ),
        (
            {**_wheel_members(), MODULE: b"VALUE = 2\n"},
            _sdist_members(),
            (),
            "digest",
        ),
    ],
)
def test_build_binding_rejects_incomplete_or_unowned_payload(
    tmp_path: Path,
    wheel_members: dict[str, bytes],
    sdist_members: dict[str, bytes],
    extra_files: tuple[str, ...],
    message: str,
) -> None:
    dist = tmp_path / "dist"
    _write_pair(dist, wheel_members=wheel_members, sdist_members=sdist_members)
    for name in extra_files:
        (dist / name).write_bytes(b"unexpected")
    repo, commit, _tree, ledger = _write_repo(tmp_path)

    with pytest.raises(ValueError, match=message):
        build_binding(repo, dist, ledger, commit)


def test_build_binding_rejects_duplicate_normalized_archive_member(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    _write_pair(dist)
    with (
        pytest.warns(UserWarning, match="Duplicate name"),
        zipfile.ZipFile(dist / WHEEL_NAME, "a") as archive,
    ):
        archive.writestr("src/worker.py", b"duplicate")
    repo, commit, _tree, ledger = _write_repo(tmp_path)

    with pytest.raises(ValueError, match="(?i)duplicate"):
        build_binding(repo, dist, ledger, commit)


def test_build_binding_rejects_case_colliding_archive_member(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    members = _wheel_members()
    members["SRC/worker.py"] = b"collision"
    _write_pair(dist, wheel_members=members)
    repo, commit, _tree, ledger = _write_repo(tmp_path)

    with pytest.raises(ValueError, match="Case-colliding"):
        build_binding(repo, dist, ledger, commit)


def test_build_binding_rejects_coordinated_ledger_and_archive_omission(
    tmp_path: Path,
) -> None:
    dist = tmp_path / "dist"
    _write_pair(
        dist,
        wheel_members=_wheel_members(omit=MODULE),
        sdist_members=_sdist_members(omit=MODULE),
    )
    repo, commit, _tree, ledger = _write_repo(tmp_path)
    content = json.loads(ledger.read_text(encoding="utf-8"))
    content["selected_source_files"] = [
        item for item in content["selected_source_files"] if item["name"] != MODULE
    ]
    ledger.write_text(json.dumps(content), encoding="utf-8")

    with pytest.raises(ValueError, match="Git tree|selected source"):
        build_binding(repo, dist, ledger, commit)


def test_build_binding_rejects_unexpected_sdist_directory(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    _write_pair(dist, sdist_directories=("unowned/empty",))
    repo, commit, _tree, ledger = _write_repo(tmp_path)

    with pytest.raises(ValueError, match="directory|unexpected"):
        build_binding(repo, dist, ledger, commit)


@pytest.mark.parametrize("archive_kind", ["wheel", "sdist"])
def test_build_binding_bounds_archive_member_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, archive_kind: str
) -> None:
    monkeypatch.setattr(bundle_module, "_MAX_ARCHIVE_MEMBER_BYTES", 5, raising=False)
    dist = tmp_path / "dist"
    wheel, sdist = _write_pair(dist)

    with pytest.raises(ValueError, match="member size limit"):
        if archive_kind == "wheel":
            bundle_module._read_wheel(wheel)
        else:
            bundle_module._read_sdist(sdist, PREFIX)


@pytest.mark.parametrize("archive_kind", ["wheel", "sdist"])
def test_build_binding_bounds_archive_member_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, archive_kind: str
) -> None:
    monkeypatch.setattr(bundle_module, "_MAX_ARCHIVE_MEMBER_COUNT", 3, raising=False)
    dist = tmp_path / "dist"
    wheel, sdist = _write_pair(dist)

    with pytest.raises(ValueError, match="member count limit"):
        if archive_kind == "wheel":
            bundle_module._read_wheel(wheel)
        else:
            bundle_module._read_sdist(sdist, PREFIX)


def test_build_binding_bounds_total_decompressed_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bundle_module, "_MAX_ARCHIVE_TOTAL_BYTES", 5, raising=False)
    dist = tmp_path / "dist"
    wheel, _sdist = _write_pair(dist)

    with pytest.raises(ValueError, match="total decompressed size limit"):
        bundle_module._read_wheel(wheel)


@pytest.mark.parametrize(
    ("offset", "fmt", "value", "message"),
    [
        (10, "<H", 10_001, "member count limit"),
        (12, "<I", 16 * 1024 * 1024 + 1, "central directory size limit"),
    ],
)
def test_wheel_eocd_bounds_are_checked_before_zipfile_parsing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    offset: int,
    fmt: str,
    value: int,
    message: str,
) -> None:
    dist = tmp_path / "dist"
    wheel, _sdist = _write_pair(dist)
    _patch_wheel_eocd(wheel, offset=offset, fmt=fmt, value=value)
    if offset == 10:
        _patch_wheel_eocd(wheel, offset=8, fmt=fmt, value=value)

    def forbidden_zipfile_open(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("zipfile must not parse an unbounded central directory")

    monkeypatch.setattr(zipfile, "ZipFile", forbidden_zipfile_open)

    with pytest.raises(ValueError, match=message):
        bundle_module._read_wheel(wheel)


@pytest.mark.parametrize(
    ("offset", "fmt", "value", "message"),
    [
        (4, "<H", 1, "(?i)multi-disk"),
        (10, "<H", 0xFFFF, "ZIP64"),
    ],
)
def test_wheel_eocd_rejects_unsupported_zip_shapes_before_parsing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    offset: int,
    fmt: str,
    value: int,
    message: str,
) -> None:
    dist = tmp_path / "dist"
    wheel, _sdist = _write_pair(dist)
    _patch_wheel_eocd(wheel, offset=offset, fmt=fmt, value=value)

    def forbidden_zipfile_open(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("unsupported ZIP shapes must fail before ZipFile parsing")

    monkeypatch.setattr(zipfile, "ZipFile", forbidden_zipfile_open)

    with pytest.raises(ValueError, match=message):
        bundle_module._read_wheel(wheel)


def test_wheel_eocd_rejects_later_signature_in_comment_before_zipfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dist = tmp_path / "dist"
    wheel, _sdist = _write_pair(dist)
    with zipfile.ZipFile(wheel, "a") as archive:
        archive.comment = b"comment-prefix-PK\x05\x06" + (b"\x00" * 22) + b"tail"

    def forbidden_zipfile_open(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("preflight must not select a different EOCD than ZipFile")

    monkeypatch.setattr(zipfile, "ZipFile", forbidden_zipfile_open)

    with pytest.raises(ValueError, match="end-of-central-directory|malformed"):
        bundle_module._read_wheel(wheel)


@pytest.mark.parametrize("unsafe_name", ["../escape.py", "/absolute.py", "src\\worker.py"])
def test_build_binding_rejects_unsafe_archive_member_names(
    tmp_path: Path, unsafe_name: str
) -> None:
    dist = tmp_path / "dist"
    wheel_members = _wheel_members()
    wheel_members[unsafe_name] = b"unsafe"
    _write_pair(dist, wheel_members=wheel_members)
    repo, commit, _tree, ledger = _write_repo(tmp_path)

    with pytest.raises(ValueError, match="path"):
        build_binding(repo, dist, ledger, commit)


def test_build_binding_rejects_wheel_link_member(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    _write_pair(dist)
    with zipfile.ZipFile(dist / WHEEL_NAME, "a") as archive:
        info = zipfile.ZipInfo("src/link.py")
        info.create_system = 3
        info.external_attr = 0o120777 << 16
        archive.writestr(info, b"target")
    repo, commit, _tree, ledger = _write_repo(tmp_path)

    with pytest.raises(ValueError, match="Link or special"):
        build_binding(repo, dist, ledger, commit)


@pytest.mark.parametrize("name", ["src/__pycache__/worker.pyc", "src/worker.pyo"])
def test_build_binding_rejects_compiled_cache_members(tmp_path: Path, name: str) -> None:
    dist = tmp_path / "dist"
    members = _wheel_members()
    members[name] = b"compiled"
    _write_pair(dist, wheel_members=members)
    repo, commit, _tree, ledger = _write_repo(tmp_path)

    with pytest.raises(ValueError, match="Compiled Python"):
        build_binding(repo, dist, ledger, commit)


def test_build_binding_rejects_sdist_special_members(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    _write_pair(dist)
    with tarfile.open(dist / SDIST_NAME, "w:gz") as archive:
        for name, payload in _sdist_members().items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
        info = tarfile.TarInfo(f"{PREFIX}/src/fifo")
        info.type = tarfile.FIFOTYPE
        archive.addfile(info)
    repo, commit, _tree, ledger = _write_repo(tmp_path)

    with pytest.raises(ValueError, match="special"):
        build_binding(repo, dist, ledger, commit)


def test_build_binding_rejects_metadata_drift(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    members = _wheel_members()
    members[f"{PREFIX}.dist-info/METADATA"] = (
        b"Metadata-Version: 2.4\nName: matryca-plumber\nVersion: 2.0.1rc3\n\n"
    )
    _write_pair(dist, wheel_members=members)
    repo, commit, _tree, ledger = _write_repo(tmp_path)

    with pytest.raises(ValueError, match="metadata version"):
        build_binding(repo, dist, ledger, commit)


def test_build_binding_rejects_metadata_name_drift(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    members = _wheel_members()
    members[f"{PREFIX}.dist-info/METADATA"] = (
        b"Metadata-Version: 2.4\nName: other-package\nVersion: 2.0.1rc4\n\n"
    )
    _write_pair(dist, wheel_members=members)
    repo, commit, _tree, ledger = _write_repo(tmp_path)

    with pytest.raises(ValueError, match="package name"):
        build_binding(repo, dist, ledger, commit)


@pytest.mark.parametrize("missing_name", [WHEEL_NAME, SDIST_NAME])
def test_build_binding_rejects_missing_distribution(tmp_path: Path, missing_name: str) -> None:
    dist = tmp_path / "dist"
    _write_pair(dist)
    (dist / missing_name).unlink()
    repo, commit, _tree, ledger = _write_repo(tmp_path)

    with pytest.raises(ValueError, match="exactly one"):
        build_binding(repo, dist, ledger, commit)


def test_verify_handoff_rejects_together_replaced_archives_and_manifest(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    _write_pair(dist)
    expected = _binding(tmp_path, dist)
    manifest = dist / "SHA256SUMS"
    manifest.write_text(
        f"{expected.wheel_sha256}  {expected.wheel_name}\n"
        f"{expected.sdist_sha256}  {expected.sdist_name}\n",
        encoding="ascii",
    )

    replacement_wheel = _wheel_members()
    replacement_wheel[MODULE] = b"VALUE = 99\n"
    replacement_sdist = _sdist_members()
    replacement_sdist[f"{PREFIX}/{MODULE}"] = b"VALUE = 99\n"
    _write_pair(dist, wheel_members=replacement_wheel, sdist_members=replacement_sdist)
    changed = hashlib.sha256((dist / WHEEL_NAME).read_bytes()).hexdigest()
    changed_sdist = hashlib.sha256((dist / SDIST_NAME).read_bytes()).hexdigest()
    manifest.write_text(
        f"{changed}  {WHEEL_NAME}\n{changed_sdist}  {SDIST_NAME}\n",
        encoding="ascii",
    )

    with pytest.raises(ValueError, match="binding|digest"):
        verify_handoff(dist, manifest, expected)


def test_verify_handoff_accepts_exact_pair_and_canonical_manifest(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    _write_pair(dist)
    expected = _binding(tmp_path, dist)
    manifest = dist / "SHA256SUMS"
    manifest.write_bytes(canonical_manifest(expected))

    verify_handoff(dist, manifest, expected)


def test_verify_handoff_requires_manifest_inside_dist_directory(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    _write_pair(dist)
    expected = _binding(tmp_path, dist)
    canonical = dist / "SHA256SUMS"
    canonical.write_bytes(canonical_manifest(expected))
    external = tmp_path / "SHA256SUMS"
    external.write_bytes(canonical_manifest(expected))

    with pytest.raises(ValueError, match="dist/SHA256SUMS|inside"):
        verify_handoff(dist, external, expected)


def test_verify_handoff_rejects_malformed_or_extra_manifest_lines(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    _write_pair(dist)
    expected = _binding(tmp_path, dist)
    manifest = dist / "SHA256SUMS"
    manifest.write_text("bad\n", encoding="ascii")

    with pytest.raises(ValueError, match="manifest"):
        verify_handoff(dist, manifest, expected)


def test_build_binding_rejects_source_commit_and_tree_mismatch(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    _write_pair(dist)
    repo, commit, tree, ledger = _write_repo(tmp_path)
    content = json.loads(ledger.read_text(encoding="utf-8"))
    content["source_tree"] = "0" * 40 if tree != "0" * 40 else "1" * 40
    ledger.write_text(json.dumps(content), encoding="utf-8")

    with pytest.raises(ValueError, match="tree"):
        build_binding(repo, dist, ledger, commit)

    with pytest.raises(ValueError, match="commit"):
        build_binding(repo, dist, ledger, "f" * 40)


def test_binding_json_is_compact_and_round_trips_with_strict_fields(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    _write_pair(dist)
    binding = _binding(tmp_path, dist)

    encoded = binding.to_json()
    decoded = BundleBinding.from_json(encoded)

    assert "\n" not in encoded
    assert decoded == binding


def test_binding_json_rejects_malformed_fields() -> None:
    with pytest.raises(ValueError, match="binding"):
        BundleBinding.from_json('{"source_commit":"not-a-commit"}')


def test_missing_expected_binding_environment_value_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("EXPECTED_BINDING_JSON", raising=False)
    env = os.environ.copy()
    env.pop("EXPECTED_BINDING_JSON", None)
    script = Path(__file__).parents[1] / "scripts" / "qualify_release_package.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "verify-handoff",
            "--dist-dir",
            str(tmp_path / "download"),
            "--manifest",
            str(tmp_path / "download" / "SHA256SUMS"),
        ],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )

    assert result.returncode != 0
    assert "EXPECTED_BINDING_JSON is required" in result.stderr


def test_malformed_expected_binding_fails_before_handoff_checks(tmp_path: Path) -> None:
    script = Path(__file__).parents[1] / "scripts" / "qualify_release_package.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "verify-handoff",
            "--dist-dir",
            str(tmp_path / "download"),
            "--manifest",
            str(tmp_path / "download" / "SHA256SUMS"),
        ],
        capture_output=True,
        check=False,
        env={**os.environ, "EXPECTED_BINDING_JSON": "{}"},
        text=True,
    )

    assert result.returncode != 0
    assert "Invalid binding fields" in result.stderr


def test_build_handoff_missing_github_output_writes_no_success_value(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.pop("GITHUB_OUTPUT", None)
    script = Path(__file__).parents[1] / "scripts" / "qualify_release_package.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "build-handoff",
            "--repo-root",
            str(tmp_path / "nonexistent-repo"),
            "--dist-dir",
            str(tmp_path / "dist"),
            "--ledger",
            str(tmp_path / "ledger.json"),
            "--expected-commit",
            "a" * 40,
        ],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )

    assert result.returncode != 0
    assert "GITHUB_OUTPUT is required" in result.stderr
