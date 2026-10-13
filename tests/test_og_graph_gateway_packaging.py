"""Synthetic namespace inventories; no installation, build or operational artifact."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

import pytest
from scripts import build_release_artifacts as builder
from scripts.release_qualification import bundle, installed

# Independent expectation: never derive this list from the implementation under test.
GATEWAY_MEMBERS = (
    "matryca_plumber/__init__.py",
    "matryca_plumber/graph_gateway/__init__.py",
    "matryca_plumber/graph_gateway/__main__.py",
    "matryca_plumber/graph_gateway/bootstrap.py",
    "matryca_plumber/graph_gateway/profile.py",
    "matryca_plumber/graph_gateway/wire.py",
    "matryca_plumber/graph_gateway/runtime.py",
)


def _source_hashes() -> dict[str, str]:
    return {name: hashlib.sha256(name.encode()).hexdigest() for name in GATEWAY_MEMBERS}


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_gateway_source_projection_is_exact_and_preserves_hashes(kind: str) -> None:
    source = {"src/__init__.py": "0" * 64, **_source_hashes()}
    projector = (
        bundle._expected_wheel_source_files
        if kind == "wheel"
        else bundle._expected_sdist_source_files
    )
    projection = projector(source)
    assert projection == source, "the independently selected namespace must be authenticated"


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
@pytest.mark.parametrize("member", GATEWAY_MEMBERS)
@pytest.mark.parametrize("fault", ["missing", "tampered"])
def test_gateway_inventory_rejects_each_missing_or_tampered_member(
    kind: str, member: str, fault: str
) -> None:
    source = _source_hashes()
    projector = (
        bundle._expected_wheel_source_files
        if kind == "wheel"
        else bundle._expected_sdist_source_files
    )
    expected = projector(source)
    assert set(expected) == set(GATEWAY_MEMBERS), "gateway source projection is missing"
    members = {name: bundle._Member(name, 1, digest) for name, digest in source.items()}
    if fault == "missing":
        del members[member]
    else:
        members[member] = bundle._Member(member, 1, "f" * 64)
    with pytest.raises(ValueError, match="missing|digest"):
        bundle._verify_inventory(members, expected, set(), kind)


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
@pytest.mark.parametrize("fault", ["partial", "unknown", "bytecode", "alias", "escape"])
def test_gateway_projection_rejects_partial_or_unowned_namespace(kind: str, fault: str) -> None:
    source = _source_hashes()
    if fault == "partial":
        del source[GATEWAY_MEMBERS[0]]
    else:
        name = {
            "unknown": "matryca_plumber/secret.py",
            "bytecode": "matryca_plumber/__pycache__/secret.pyc",
            "alias": "matryca_plumber/graph_gateway/./wire.py",
            "escape": "matryca_plumber/../secret.py",
        }[fault]
        source[name] = "1" * 64
    with pytest.raises(ValueError):
        if kind == "wheel":
            bundle._expected_wheel_source_files(source)
        else:
            bundle._expected_sdist_source_files(source)


def test_builder_required_namespace_is_independently_enumerated() -> None:
    assert set(GATEWAY_MEMBERS) <= builder._REQUIRED_MEMBERS
    assert set(GATEWAY_MEMBERS) <= builder._REQUIRED_SDIST_MEMBERS
    assert len(builder._PUBLIC_CONTRACT_RESOURCE_MEMBERS) == 26


def test_installed_payload_map_includes_exact_namespace_without_a_prefix_escape(
    tmp_path: Path,
) -> None:
    tracked = set(GATEWAY_MEMBERS) | builder._SOURCE_CONTRACT_RESOURCE_MEMBERS
    payload = installed._payload_map(tmp_path, tracked)
    assert all(payload.get(name) == tmp_path / name for name in GATEWAY_MEMBERS)
    with pytest.raises(ValueError):
        installed._payload_map(tmp_path, tracked | {"matryca_plumber/unowned.py"})


def _authenticated_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: Literal["wheel", "sdist"],
    names: set[str],
) -> tuple[Path, bundle.BundleBinding]:
    data = b"synthetic non-executable archive input"
    payloads = {name: name.encode() for name in names}
    metadata_name = "matryca_plumber-2.0.1rc4.dist-info/METADATA" if kind == "wheel" else "PKG-INFO"
    payloads[metadata_name] = b"synthetic metadata"
    members = {
        name: bundle._Member(name, len(value), hashlib.sha256(value).hexdigest())
        for name, value in payloads.items()
    }
    inventory = bundle._inventory_digest(members)
    binding = bundle.BundleBinding(
        "a" * 40,
        "b" * 40,
        "2.0.1rc4",
        "matryca_plumber-2.0.1rc4-py3-none-any.whl",
        len(data),
        hashlib.sha256(data).hexdigest(),
        "matryca_plumber-2.0.1rc4.tar.gz",
        len(data),
        hashlib.sha256(data).hexdigest(),
        inventory,
        inventory,
    )
    artifact = tmp_path / (binding.wheel_name if kind == "wheel" else binding.sdist_name)
    artifact.write_bytes(data)
    monkeypatch.setattr(bundle, "_read_wheel", lambda path: (members, payloads))
    monkeypatch.setattr(bundle, "_read_sdist", lambda path, prefix: (members, payloads, set()))
    return artifact, binding


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_authenticated_archive_retains_all_namespace_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: Literal["wheel", "sdist"]
) -> None:
    artifact, binding = _authenticated_input(tmp_path, monkeypatch, kind, set(GATEWAY_MEMBERS))
    payload, _ = installed._authenticated_archive(artifact, binding, kind)
    assert set(GATEWAY_MEMBERS) <= set(payload), "authenticated gateway payload was discarded"


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
@pytest.mark.parametrize("member", GATEWAY_MEMBERS)
def test_authenticated_archive_rejects_partial_namespace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: Literal["wheel", "sdist"], member: str
) -> None:
    artifact, binding = _authenticated_input(
        tmp_path, monkeypatch, kind, set(GATEWAY_MEMBERS) - {member}
    )
    with pytest.raises(ValueError):
        installed._authenticated_archive(artifact, binding, kind)


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
@pytest.mark.parametrize("extra", ["secret.py", "__pycache__/x.pyc", "graph_gateway/../x.py"])
def test_authenticated_archive_rejects_unknown_namespace_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: Literal["wheel", "sdist"], extra: str
) -> None:
    names = set(GATEWAY_MEMBERS) | {f"matryca_plumber/{extra}"}
    artifact, binding = _authenticated_input(tmp_path, monkeypatch, kind, names)
    with pytest.raises(ValueError):
        installed._authenticated_archive(artifact, binding, kind)


def _metadata_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, top_level: bytes
) -> tuple[Path, dict[str, tuple[int, str]]]:
    root = tmp_path / "synthetic.dist-info"
    files = {
        "METADATA": b"synthetic",
        "WHEEL": (
            b"Wheel-Version: 1.0\nGenerator: setuptools (80.9.0)\n"
            b"Root-Is-Purelib: true\nTag: py3-none-any\n"
        ),
        "entry_points.txt": b"[console_scripts]\n",
        "top_level.txt": top_level,
        "licenses/LICENSE": b"synthetic",
        "licenses/NOTICE": b"synthetic",
        "RECORD": b"",
    }
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    monkeypatch.setattr(installed, "_expected_scripts", lambda path: {})
    payload = {name: (0, "a" * 64) for name in GATEWAY_MEMBERS}
    payload.update({"src/__init__.py": (0, "a" * 64), "frontend/__init__.py": (0, "a" * 64)})
    return root, payload


def test_installed_top_level_metadata_accepts_exact_sorted_namespace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, payload = _metadata_directory(tmp_path, monkeypatch, b"frontend\nmatryca_plumber\nsrc\n")
    try:
        scripts, generator = installed._verify_generated_metadata(root, tmp_path, payload, "wheel")
    except ValueError as error:
        if str(error) != (
            "Installed top-level package metadata differs from the authenticated payload."
        ):
            raise
        pytest.fail("the authenticated namespace is missing from top-level metadata admission")
    assert scripts == {}
    assert (generator.name, generator.version) == ("setuptools", "80.9.0")


@pytest.mark.parametrize(
    "names",
    [
        b"frontend\nsrc\n",
        b"frontend\nmatryca_plumber\nsrc\nmatryca_plumber\n",
        b"frontend\nmatryca_plumber\nsecret\nsrc\n",
    ],
)
def test_installed_top_level_metadata_cannot_omit_duplicate_or_add_namespace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, names: bytes
) -> None:
    root, payload = _metadata_directory(tmp_path, monkeypatch, names)
    with pytest.raises(ValueError, match="top-level"):
        installed._verify_generated_metadata(root, tmp_path, payload, "wheel")


@pytest.mark.parametrize("fault", ["symlink", "bytecode"])
def test_namespace_scope_rejects_symlinks_and_bytecode(tmp_path: Path, fault: str) -> None:
    root = tmp_path / "namespace"
    root.mkdir()
    if fault == "symlink":
        (root / "escape.py").symlink_to(tmp_path / "outside.py")
    else:
        (root / "cached.pyc").write_bytes(b"synthetic")
    with pytest.raises(ValueError, match="symlink|bytecode"):
        installed._scope_files(root, label="package")


def test_quality_configuration_includes_namespace_without_relaxing_thresholds() -> None:
    import tomllib

    root = Path(__file__).resolve().parents[1]
    with (root / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)
    tools = project["tool"]
    assert "matryca_plumber*" in tools["setuptools"]["packages"]["find"]["include"]
    assert "matryca_plumber" in tools["ruff"]["src"]
    assert "--cov=matryca_plumber" in tools["pytest"]["ini_options"]["addopts"]
    assert "--cov-fail-under=70" in tools["pytest"]["ini_options"]["addopts"]
    with (root / "MANIFEST.in").open(encoding="utf-8") as stream:
        assert "graft matryca_plumber" in stream.read().splitlines()
    with (root / "Makefile").open(encoding="utf-8") as stream:
        contents = stream.read()
    assert "--select S --ignore S101 src matryca_plumber" in contents
    assert "mypy src/ matryca_plumber/ tests/" in contents


def _probe_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, dict[str, Any], list[list[str]]]:
    """Inject data only; neither the fake interpreter nor package bytes are executed."""
    env = tmp_path / "synthetic-environment"
    site = env / "site"
    origins: dict[str, dict[str, str | None]] = {}
    for name in ("src/__init__.py", "frontend/__init__.py", *GATEWAY_MEMBERS):
        path = site / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic, never executed")
    for name, member in (
        ("matryca_plumber", GATEWAY_MEMBERS[0]),
        ("matryca_plumber.graph_gateway", GATEWAY_MEMBERS[1]),
    ):
        origins[name] = {"file": str(site / member), "spec": str(site / member)}
    result: dict[str, Any] = {
        "src": str(site / "src/__init__.py"),
        "frontend": str(site / "frontend/__init__.py"),
        "python": "3.12.13",
        "os": "darwin",
        "machine": "arm64",
        "deps": [],
        "gateway": origins,
    }
    calls: list[list[str]] = []

    def injected(argv: list[str], **kwargs: Any) -> tuple[int, str, str]:
        calls.append(argv)
        return 0, json.dumps(result), ""

    monkeypatch.setattr(installed, "_run_bounded", injected)
    return env, site, result, calls


def test_installed_probe_accepts_exact_declared_namespace_origins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env, site, _, calls = _probe_fixture(tmp_path, monkeypatch)
    result = installed._isolated_probe(env / "not-executed-python", env, site, tmp_path / "source")
    assert result == (
        site.resolve(),
        (site / "src/__init__.py").resolve(),
        hashlib.sha256(b"[]").hexdigest(),
        "3.12.13",
        "darwin",
        "arm64",
        (),
    )
    assert len(calls) == 1
    assert "__main__" not in calls[0][calls[0].index("-c") + 1]


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "foreign-file",
        "foreign-spec",
        "absent-spec",
        "extra",
        "in-site-foreign",
        "file-spec-disagreement",
    ],
)
def test_installed_probe_rejects_missing_or_foreign_namespace_origins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    env, site, result, calls = _probe_fixture(tmp_path, monkeypatch)
    origins = result["gateway"]
    foreign = tmp_path / "foreign.py"
    foreign.write_bytes(b"synthetic")
    if fault == "missing":
        del result["gateway"]
    elif fault == "foreign-file":
        origins["matryca_plumber"]["file"] = str(foreign)
    elif fault == "foreign-spec":
        origins["matryca_plumber.graph_gateway"]["spec"] = str(foreign)
    elif fault == "absent-spec":
        origins["matryca_plumber"]["spec"] = None
    elif fault == "extra":
        origins["unexpected"] = dict(origins["matryca_plumber"])
    elif fault == "in-site-foreign":
        wrong = str(site / "matryca_plumber/graph_gateway/runtime.py")
        origins["matryca_plumber"] = {"file": wrong, "spec": wrong}
    elif fault == "file-spec-disagreement":
        origins["matryca_plumber"]["spec"] = str(site / "matryca_plumber/graph_gateway/__init__.py")
    with pytest.raises(ValueError, match="namespace|provenance"):
        installed._isolated_probe(env / "not-executed-python", env, site, tmp_path / "source")
    assert len(calls) == 1
    assert "__main__" not in calls[0][calls[0].index("-c") + 1]


def _record_inventory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, ...]:
    """Isolate namespace/RECORD ownership; no virtual environment or launcher is made."""
    env, source = tmp_path / "synthetic-environment", tmp_path / "synthetic-source"
    site = env / "site"
    dist_info = site / "synthetic.dist-info"
    payloads = {name: b"# synthetic bytes\n" for name in GATEWAY_MEMBERS}
    payloads.update({"src/__init__.py": b"", "frontend/__init__.py": b""})
    expected: dict[str, Path] = {}
    archive: dict[str, tuple[int, str]] = {}
    entries: dict[str, tuple[Path, str, str]] = {}
    for name, value in payloads.items():
        source_path, installed_path = source / name, site / name
        for path in (source_path, installed_path):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
        digest = hashlib.sha256(value).digest()
        expected[name] = source_path
        archive[name] = (len(value), digest.hex())
        encoded = base64.urlsafe_b64encode(digest).decode().rstrip("=")
        entries[name] = (installed_path, f"sha256={encoded}", str(len(value)))
    for filename, value in (("METADATA", b"synthetic metadata"), ("RECORD", b"")):
        path = dist_info / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
        name = path.relative_to(site).as_posix()
        encoded = base64.urlsafe_b64encode(hashlib.sha256(value).digest()).decode().rstrip("=")
        entries[name] = (path, f"sha256={encoded}", str(len(value)))
        if filename == "METADATA":
            archive[name] = (len(value), hashlib.sha256(value).hexdigest())
    entries["synthetic.dist-info/RECORD"] = (dist_info / "RECORD", "", "")
    generator = installed.BuildGenerator(name="setuptools", version="80.9.0")
    monkeypatch.setattr(installed, "_verify_generated_metadata", lambda *args: ({}, generator))
    monkeypatch.setattr(installed, "_verify_entry_point_scripts", lambda *args: None)
    monkeypatch.setattr(installed, "_RESOURCE_FILES", ())
    return (
        site,
        env,
        source,
        dist_info,
        expected,
        archive,
        {"METADATA": b"synthetic metadata"},
        "wheel",
        entries,
    )


def test_namespace_inventory_requires_ownership_before_acceptance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _record_inventory(tmp_path, monkeypatch)
    try:
        result = installed._verify_inventory(*inputs)
    except ValueError as error:
        if not str(error).startswith(
            "Installed distribution RECORD contains an unowned path: matryca_plumber/"
        ):
            raise
        pytest.fail("the authenticated namespace is not included in installed ownership")
    assert len(result) == 3


@pytest.mark.parametrize("fault", ["missing-record", "unowned", "rewritten-record", "bytes-only"])
def test_namespace_record_and_archive_binding_reject_forgery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    inputs = _record_inventory(tmp_path, monkeypatch)
    entries = inputs[-1]
    member = GATEWAY_MEMBERS[0]
    message = "absent from RECORD"
    if fault == "missing-record":
        del entries[member]
    elif fault == "unowned":
        path = inputs[0] / "matryca_plumber/unowned.py"
        path.write_bytes(b"unowned")
        entries["matryca_plumber/unowned.py"] = (path, "sha256=wrong", "7")
        message = "unlisted|unowned"
    else:
        path = entries[member][0]
        path.write_bytes(b"# altered bytes\n")
        message = "RECORD hash does not match"
        if fault == "rewritten-record":
            value = path.read_bytes()
            encoded = base64.urlsafe_b64encode(hashlib.sha256(value).digest()).decode().rstrip("=")
            entries[member] = (path, f"sha256={encoded}", str(len(value)))
            message = "differs from authenticated archive inventory"
    with pytest.raises(ValueError, match=message):
        installed._verify_inventory(*inputs)
