"""Synthetic authority controls; these never admit an official/native installation."""

from __future__ import annotations

import copy
import hashlib
import importlib
import importlib.util
import json
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from scripts.release_qualification.bundle import BundleBinding


def _authority() -> ModuleType:
    name = "scripts.release_qualification.windows_installation"
    assert importlib.util.find_spec(name) is not None, "Accepted L authority module is missing."
    return importlib.import_module(name)


def _binding() -> BundleBinding:
    return BundleBinding(
        source_commit="a" * 40,
        source_tree="b" * 40,
        version="2.0.1rc4",
        wheel_name="matryca_plumber-2.0.1rc4-py3-none-any.whl",
        wheel_size=100,
        wheel_sha256="1" * 64,
        sdist_name="matryca_plumber-2.0.1rc4.tar.gz",
        sdist_size=200,
        sdist_sha256="2" * 64,
        wheel_inventory_sha256="3" * 64,
        sdist_inventory_sha256="4" * 64,
    )


def _literal_payload(module: str, path: str) -> bytes:
    # Independently transcribed from the accepted pinned-source payload addendum.
    return (
        f"#!{path}\n# -*- coding: utf-8 -*-\nimport sys\nfrom {module} import main\n"
        'if __name__ == "__main__":\n'
        '    if sys.argv[0].endswith("-script.pyw"):\n'
        "        sys.argv[0] = sys.argv[0][:-11]\n"
        '    elif sys.argv[0].endswith(".exe"):\n'
        "        sys.argv[0] = sys.argv[0][:-4]\n"
        "    sys.exit(main())\n"
    ).encode()


def _descriptor_document(kind: str = "wheel") -> dict[str, Any]:
    path = r"C:\Owned\python.exe" if kind == "wheel" else r"D:\Other\python.exe"
    return {
        "schema_version": 1,
        "source_commit": "a" * 40,
        "source_tree": "b" * 40,
        "binding_sha256": hashlib.sha256(_binding().to_json().encode()).hexdigest(),
        "kind": kind,
        "artifact_name": getattr(_binding(), f"{kind}_name"),
        "artifact_size": getattr(_binding(), f"{kind}_size"),
        "artifact_sha256": getattr(_binding(), f"{kind}_sha256"),
        "installation_evidence_sha256": "5" * 64,
        "installer": {
            "name": "uv",
            "version": "0.12.19",
            "source_commit": "bea138450f0e620a4ce5765b0e38cff7b9f0799f",
            "archive_sha256": "6dbb02d79e419522f1c500f0adb1cddcff0cda7d59b0d66ea7f5e3b4a1b2f5f0",
            "executable_sha256": "f94eddb81f3addca6ef8f2361a70c3edde31adcbd1000a55fc6674306ae0b1e7",
            "admission_sha256": "67adfa8e8687d206eec738e7e4e455e59249bb0a42ef477d02d2e852f0aa5ce0",
        },
        "template": {
            "profile": "windows-x64-console-nonrelocatable/v1",
            "size": 45_056,
            "git_blob": "c6d3881fc6b7d3ef0c6d3c08d505ab2b4c0ad9c4",
            "sha256": "0447a4febf43fdd958e4236129d6050b1dad64c124c43355d557542b3229cae8",
        },
        "recipe_sha256": "6" * 64,
        "interpreter": {
            "path": path,
            "path_sha256": hashlib.sha256(path.encode()).hexdigest(),
            "executable_sha256": "7" * 64,
            "implementation": "CPython",
            "version": "3.12.14",
        },
        "scripts": [
            {
                "name": name,
                "target": module + ":main",
                "payload_sha256": hashlib.sha256(_literal_payload(module, path)).hexdigest(),
            }
            for name, module in (
                ("matryca", "src.cli"),
                ("matryca-logseq-llm-wiki", "src.main"),
                ("matryca-plumber", "src.plumber_entry"),
            )
        ],
    }


def _proof_document(kind: str = "wheel") -> dict[str, Any]:
    descriptor = _descriptor_document(kind)
    return {
        "schema_version": 1,
        "profile": "windows-x64-console-nonrelocatable/v1",
        "descriptor_sha256": hashlib.sha256(json.dumps(descriptor).encode()).hexdigest(),
        "installation_evidence_sha256": descriptor["installation_evidence_sha256"],
        "installer": descriptor["installer"],
        "template": descriptor["template"],
        "recipe_sha256": descriptor["recipe_sha256"],
        "interpreter": {k: v for k, v in descriptor["interpreter"].items() if k != "path"},
        "scripts": [
            {**s, "launcher_size": 50_000, "launcher_sha256": str(i) * 64}
            for i, s in enumerate(descriptor["scripts"], 1)
        ],
    }


def _expected_document() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source_commit": "a" * 40,
        "source_tree": "b" * 40,
        "binding_sha256": hashlib.sha256(_binding().to_json().encode()).hexdigest(),
        "targets": {f"windows-x64/{kind}": _proof_document(kind) for kind in ("wheel", "sdist")},
    }


@pytest.mark.parametrize(
    "name,module",
    [
        ("matryca", "src.cli"),
        ("matryca-logseq-llm-wiki", "src.main"),
        ("matryca-plumber", "src.plumber_entry"),
    ],
)
@pytest.mark.parametrize("path", [r"C:\Owned\python.exe", r"D:\Spazio è\python.exe"])
def test_payload_preserves_complete_shebang_and_fixed_body(
    name: str, module: str, path: str
) -> None:
    assert _authority().console_script_payload(
        name, module + ":main", interpreter_display_path=path
    ) == _literal_payload(module, path)


@pytest.mark.parametrize(
    "path",
    [
        "python.exe",
        "C:python.exe",
        r"\\server\env\python.exe",
        r"C:\env\..\python.exe",
        r"C:\env\NUL.txt",
        r"C:\COM¹\python.exe",
        "C:\\env.\\python.exe",
        "C:\\env \\python.exe",
        "C:\\env\\p:ads.exe",
        "C:\\env\\x\n.exe",
        "C:\\\\env\\python.exe",
        r"\\.\C:\python.exe",
    ],
)
def test_windows_path_rejects_aliases_and_devices(path: str) -> None:
    with pytest.raises(ValueError):
        _authority().canonical_windows_interpreter_path(path)


def test_windows_caller_path_normalization_is_narrow() -> None:
    assert (
        _authority().canonical_windows_interpreter_path(r"\\?\c:\Owned\python.exe")
        == r"C:\Owned\python.exe"
    )
    assert (
        _authority().canonical_windows_interpreter_path("c:/Owned/python.exe")
        == r"C:\Owned\python.exe"
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", True),
        ("schema_version", 2),
        ("source_commit", "A" * 40),
        ("artifact_size", True),
        ("artifact_name", "../x.whl"),
        ("kind", "zip"),
        ("extra", 1),
        ("recipe_sha256", "bad"),
    ],
)
def test_descriptor_rejects_malformed_top_level(field: str, value: object) -> None:
    data = _descriptor_document()
    data[field] = value
    with pytest.raises(ValueError):
        _authority().WindowsInstallationDescriptor.from_bytes(json.dumps(data).encode())


@pytest.mark.parametrize(
    "section,field,value",
    [
        ("installer", "version", "0.12.20"),
        ("installer", "executable_sha256", "0" * 64),
        ("template", "size", True),
        ("template", "sha256", "0" * 64),
        ("interpreter", "path_sha256", "0" * 64),
        ("interpreter", "version", "3.13.15"),
        ("interpreter", "implementation", "PyPy"),
        ("interpreter", "path", "c:/Owned/python.exe"),
    ],
)
def test_descriptor_rejects_wrong_nested_authority(section: str, field: str, value: object) -> None:
    data = _descriptor_document()
    data[section][field] = value
    with pytest.raises(ValueError):
        _authority().WindowsInstallationDescriptor.from_bytes(json.dumps(data).encode())


@pytest.mark.parametrize(
    "mutation", ["missing", "extra", "order", "body-only", "foreign-path", "target"]
)
def test_descriptor_requires_three_independently_bound_scripts(mutation: str) -> None:
    data = _descriptor_document()
    if mutation == "missing":
        data["scripts"].pop()
    elif mutation == "extra":
        data["scripts"].append(copy.deepcopy(data["scripts"][0]))
    elif mutation == "order":
        data["scripts"].reverse()
    elif mutation == "target":
        data["scripts"][0]["target"] = "other:main"
    else:
        payload = _literal_payload("src.cli", r"C:\Wrong\python.exe")
        if mutation == "body-only":
            payload = payload.split(b"\n", 1)[1]
        data["scripts"][0]["payload_sha256"] = hashlib.sha256(payload).hexdigest()
    with pytest.raises(ValueError):
        _authority().WindowsInstallationDescriptor.from_bytes(json.dumps(data).encode())


@pytest.mark.parametrize(
    "raw",
    [
        b'{"schema_version":1,"schema_version":1}',
        b"NaN",
        b"\xff",
        b"[" * 2000,
        b"{}" + b" " * 262_144,
    ],
    ids=["duplicate", "constant", "utf8", "recursive", "oversized"],
)
def test_descriptor_rejects_duplicate_malformed_and_bounded_json(raw: bytes) -> None:
    with pytest.raises(ValueError):
        _authority().WindowsInstallationDescriptor.from_bytes(raw)


def test_external_descriptor_hash_and_original_archive_are_required(tmp_path: Path) -> None:
    module = _authority()
    path = tmp_path / "descriptor.json"
    raw = json.dumps(_descriptor_document()).encode()
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        module.load_windows_installation_descriptor(path, expected_sha256="0" * 64)
    parsed = module.load_windows_installation_descriptor(
        path, expected_sha256=hashlib.sha256(raw).hexdigest()
    )
    parsed.verify_binding(_binding(), "wheel")
    with pytest.raises(ValueError):
        parsed.verify_binding(_binding(), "sdist")


def test_authority_reader_rejects_symlink_and_bound_before_read(tmp_path: Path) -> None:
    module = _authority()
    target = tmp_path / "data"
    target.write_bytes(b"1234")
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(ValueError):
        module.read_authority_file(link, limit=4)
    with pytest.raises(ValueError):
        module.read_authority_file(target, limit=3)
    parent_link = tmp_path / "alias"
    parent_link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        module.read_authority_file(parent_link / "data", limit=4)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", True),
        ("extra", "private"),
        ("descriptor_sha256", "bad"),
        ("profile", "gui"),
    ],
)
def test_proof_rejects_forged_schema_and_unknown_fields(field: str, value: object) -> None:
    data = _proof_document()
    data[field] = value
    with pytest.raises(ValueError):
        _authority().WindowsLauncherProof.from_dict(data)


def test_expected_bindings_keep_wheel_sdist_distinct_and_validate_external_hash(
    tmp_path: Path,
) -> None:
    module = _authority()
    raw = json.dumps(_expected_document()).encode()
    path = tmp_path / "expected.json"
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        module.load_expected_windows_installation_bindings(path, expected_sha256="0" * 64)
    expected = module.load_expected_windows_installation_bindings(
        path, expected_sha256=hashlib.sha256(raw).hexdigest()
    )
    expected.verify_binding(_binding())
    assert expected.for_kind("wheel").to_dict() != expected.for_kind("sdist").to_dict()
    assert "path" not in expected.for_kind("wheel").to_dict()["interpreter"]
    bad = _expected_document()
    bad["targets"].pop("windows-x64/sdist")
    with pytest.raises(ValueError):
        module.ExpectedWindowsInstallationBindings.from_bytes(json.dumps(bad).encode())


@pytest.mark.parametrize("mutation", ["schema", "nested-pin", "scripts-list", "script-none"])
def test_constructor_bypassed_proof_cannot_serialize_invalid_authority(mutation: str) -> None:
    module = _authority()
    proof = module.WindowsLauncherProof.from_dict(_proof_document())
    if mutation == "schema":
        bad = replace(proof, schema_version=True)
    elif mutation == "nested-pin":
        bad = replace(proof, installer=replace(proof.installer, version="0.12.20"))
    elif mutation == "scripts-list":
        bad = replace(proof, scripts=list(proof.scripts))
    else:
        bad = replace(proof, scripts=(None, *proof.scripts[1:]))
    with pytest.raises(ValueError):
        bad.to_dict()


@pytest.mark.parametrize("mutation", ["schema", "targets-list", "duplicate", "nested-pin"])
def test_constructor_bypassed_expectations_reject_mutable_or_invalid_targets(mutation: str) -> None:
    module = _authority()
    expected = module.ExpectedWindowsInstallationBindings.from_bytes(
        json.dumps(_expected_document()).encode()
    )
    if mutation == "schema":
        bad = replace(expected, schema_version=True)
    elif mutation == "targets-list":
        bad = replace(expected, targets=list(expected.targets))
    elif mutation == "duplicate":
        bad = replace(expected, targets=(expected.targets[0], expected.targets[0]))
    else:
        key, proof = expected.targets[0]
        bad_proof = replace(proof, template=replace(proof.template, size=True))
        bad = replace(expected, targets=((key, bad_proof), expected.targets[1]))
    with pytest.raises(ValueError):
        bad.verify_binding(_binding())
