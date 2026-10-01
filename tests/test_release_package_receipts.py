"""Adversarial tests for the sanitized cross-platform release receipts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest
from scripts import qualify_release_package as release_cli
from scripts.release_qualification.build_environment import ExpectedBuildEnvironmentBindings
from scripts.release_qualification.bundle import BundleBinding
from scripts.release_qualification.focused import FocusedPlatform, focused_nodes
from scripts.release_qualification.receipts import ReceiptVerification, verify_receipts

SOURCE_COMMIT = "a" * 40
SOURCE_TREE = "b" * 40
ARTIFACT_DIGEST = "c" * 64
LOCK_DIGEST = hashlib.sha256(
    (Path(__file__).resolve().parents[1] / "uv.lock").read_bytes()
).hexdigest()
DEPENDENCY_DIGEST = hashlib.sha256(b"[]").hexdigest()
BUILD_LOCK_DIGEST = "9" * 64
PROVISIONING_RECIPE_DIGEST = "a" * 64
TARGET_BINDINGS = {
    "linux-x64": ("d" * 64, "e" * 64),
    "macos-arm64": ("f" * 64, "0" * 64),
    "windows-x64": ("1" * 64, "2" * 64),
}


def _expected_build_environment_document() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "build_lock_sha256": BUILD_LOCK_DIGEST,
        "provisioning_recipe_sha256": PROVISIONING_RECIPE_DIGEST,
        "targets": {
            target: {
                "descriptor_sha256": digests[0],
                "provisioning_evidence_sha256": digests[1],
            }
            for target, digests in TARGET_BINDINGS.items()
        },
    }


def _expected_build_environments() -> ExpectedBuildEnvironmentBindings:
    raw = json.dumps(
        _expected_build_environment_document(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return ExpectedBuildEnvironmentBindings.from_bytes(raw)


def _replace_build_manifests(build: dict[str, Any], packages: list[dict[str, str]]) -> None:
    for field in (
        "provisioned_packages",
        "before_hooks_packages",
        "after_hooks_packages",
        "after_build_packages",
    ):
        build[field] = [dict(package) for package in packages]


def _binding() -> BundleBinding:
    return BundleBinding(
        source_commit=SOURCE_COMMIT,
        source_tree=SOURCE_TREE,
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


def _installed(kind: str, platform: str) -> dict[str, Any]:
    operating_system = {"linux": "linux", "macos": "darwin", "windows": "windows"}[platform]
    architecture = "arm64" if platform == "macos" else "x86_64"
    return {
        "kind": kind,
        "operating_system": operating_system,
        "architecture": architecture,
        "python_version": "3.12.8",
        "version": "2.0.1rc4",
        "location_class": "isolated-venv-site-packages",
        "record_sha256": "5" * 64,
        "resource_sha256": "6" * 64,
        "dependency_sha256": DEPENDENCY_DIGEST,
        "dependencies": [],
        "build_generator": {"name": "setuptools", "version": "84.0.0"},
        "tck_outcomes": ["PASS", "PASS", "PASS"],
    }


def _platform_receipt(platform: FocusedPlatform, architecture: str) -> dict[str, Any]:
    binding = _binding()
    selected_nodes = focused_nodes(platform)
    return {
        "run_id": "77",
        "source_sha": SOURCE_COMMIT,
        "source_tree": SOURCE_TREE,
        "artifact_id": "42",
        "artifact_digest": ARTIFACT_DIGEST,
        "os": platform,
        "architecture": architecture,
        "lock_sha256": LOCK_DIGEST,
        "uv": {"version": "0.12.16", "sha256": "7" * 64},
        "wheel": {
            "name": binding.wheel_name,
            "size": binding.wheel_size,
            "sha256": binding.wheel_sha256,
            "inventory_sha256": binding.wheel_inventory_sha256,
            "installed": _installed("wheel", platform),
        },
        "sdist": {
            "name": binding.sdist_name,
            "size": binding.sdist_size,
            "sha256": binding.sdist_sha256,
            "inventory_sha256": binding.sdist_inventory_sha256,
            "installed": _installed("sdist", platform),
        },
        "sdist_build": {
            "schema_version": 2,
            "source_commit": SOURCE_COMMIT,
            "source_tree": SOURCE_TREE,
            "binding_sha256": hashlib.sha256(binding.to_json().encode("utf-8")).hexdigest(),
            "sdist_name": binding.sdist_name,
            "sdist_size": binding.sdist_size,
            "sdist_sha256": binding.sdist_sha256,
            "wheel_name": binding.wheel_name,
            "wheel_size": 150,
            "wheel_sha256": "8" * 64,
            "build_lock_sha256": BUILD_LOCK_DIGEST,
            "environment_descriptor_sha256": TARGET_BINDINGS[f"{platform}-{architecture}"][0],
            "provisioning_recipe_sha256": PROVISIONING_RECIPE_DIGEST,
            "provisioning_evidence_sha256": TARGET_BINDINGS[f"{platform}-{architecture}"][1],
            "target_os": platform,
            "target_architecture": architecture,
            "python_implementation": "CPython",
            "python_version": "3.12.8",
            "python_executable_sha256": "3" * 64,
            "uv_version": "0.12.16",
            "uv_sha256": "7" * 64,
            "backend": "setuptools.build_meta",
            "backend_version": "84.0.0",
            "static_requirement_records": [
                {
                    "expression": "setuptools>=61",
                    "marker_applicable": True,
                    "satisfier": {"name": "setuptools", "version": "84.0.0"},
                },
                {
                    "expression": "wheel",
                    "marker_applicable": True,
                    "satisfier": {"name": "wheel", "version": "0.45.1"},
                },
            ],
            "dynamic_requirement_records": [
                {
                    "expression": "platform-only>=2; sys_platform == 'win32'",
                    "marker_applicable": platform == "windows",
                    "satisfier": (
                        {"name": "platform-only", "version": "2.1.0"}
                        if platform == "windows"
                        else None
                    ),
                },
                {
                    "expression": "mac-only>=2; sys_platform == 'darwin'",
                    "marker_applicable": platform == "macos",
                    "satisfier": (
                        {"name": "mac-only", "version": "2.1.0"} if platform == "macos" else None
                    ),
                },
                {
                    "expression": "wheel>=0.45",
                    "marker_applicable": True,
                    "satisfier": {"name": "wheel", "version": "0.45.1"},
                },
            ],
            "provisioned_packages": [
                {"name": "mac-only", "version": "2.1.0"},
                {"name": "platform-only", "version": "2.1.0"},
                {"name": "setuptools", "version": "84.0.0"},
                {"name": "wheel", "version": "0.45.1"},
            ],
            "before_hooks_packages": [
                {"name": "mac-only", "version": "2.1.0"},
                {"name": "platform-only", "version": "2.1.0"},
                {"name": "setuptools", "version": "84.0.0"},
                {"name": "wheel", "version": "0.45.1"},
            ],
            "after_hooks_packages": [
                {"name": "mac-only", "version": "2.1.0"},
                {"name": "platform-only", "version": "2.1.0"},
                {"name": "setuptools", "version": "84.0.0"},
                {"name": "wheel", "version": "0.45.1"},
            ],
            "after_build_packages": [
                {"name": "mac-only", "version": "2.1.0"},
                {"name": "platform-only", "version": "2.1.0"},
                {"name": "setuptools", "version": "84.0.0"},
                {"name": "wheel", "version": "0.45.1"},
            ],
        },
        "focused": {
            "source_commit": SOURCE_COMMIT,
            "platform": platform,
            "selected": len(selected_nodes),
            "selected_nodes": list(selected_nodes),
            "passed": len(selected_nodes),
            "failed": 0,
            "skipped": 0,
        },
    }


def _write_receipts(tmp_path: Path, *, duplicate_linux: bool = False) -> Path:
    receipts = tmp_path / "receipts"
    receipts.mkdir()
    rows = (
        (("linux", "x64"), ("linux", "x64"), ("windows", "x64"))
        if duplicate_linux
        else (("linux", "x64"), ("macos", "arm64"), ("windows", "x64"))
    )
    for index, (platform, architecture) in enumerate(rows):
        (receipts / f"row-{index}.json").write_text(
            json.dumps(_platform_receipt(cast(FocusedPlatform, platform), architecture)),
            encoding="utf-8",
        )
    return receipts


def _verify(receipt_dir: Path, **overrides: Any) -> ReceiptVerification:
    options: dict[str, Any] = {
        "expected_commit": SOURCE_COMMIT,
        "expected_tree": SOURCE_TREE,
        "expected_binding": _binding(),
        "artifact_id": "42",
        "artifact_digest": ARTIFACT_DIGEST,
        "run_id": "77",
        "expected_platform_count": 3,
        "expected_build_environments": _expected_build_environments(),
    }
    options.update(overrides)
    return verify_receipts(receipt_dir, **options)


def test_three_complete_canonical_rows_are_accepted(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)

    result = _verify(receipt_dir)

    assert result.to_dict() == {
        "run_id": "77",
        "source_commit": SOURCE_COMMIT,
        "source_tree": SOURCE_TREE,
        "artifact_id": "42",
        "artifact_digest": ARTIFACT_DIGEST,
        "lock_sha256": LOCK_DIGEST,
        "build_lock_sha256": BUILD_LOCK_DIGEST,
        "platforms": ("linux/x64", "macos/arm64", "windows/x64"),
    }


def test_missing_platform_receipt_is_rejected(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)
    (receipt_dir / "row-2.json").unlink()

    with pytest.raises(ValueError, match="exactly 3 platform receipt files"):
        _verify(receipt_dir)


def test_duplicate_platform_and_missing_expected_platform_are_rejected(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path, duplicate_linux=True)

    with pytest.raises(ValueError, match="exactly one receipt for each required platform"):
        _verify(receipt_dir)


def test_archive_identity_must_match_independent_binding(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)
    _mutate(receipt_dir, 0, lambda row: row["wheel"].update(sha256="8" * 64))

    with pytest.raises(ValueError, match="wheel receipt does not match independent binding"):
        _verify(receipt_dir)


def test_focused_counts_must_match_frozen_nodes_without_skips(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)
    _mutate(receipt_dir, 0, lambda row: row["focused"].update(skipped=1))

    with pytest.raises(ValueError, match="Focused test receipt is incomplete or failed"):
        _verify(receipt_dir)


def test_focused_nodes_must_match_exact_platform_selection(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)
    _mutate(receipt_dir, 1, lambda row: row["focused"].update(selected_nodes=[]))

    with pytest.raises(ValueError, match="Focused test receipt is incomplete or failed"):
        _verify(receipt_dir)


def test_wheel_and_sdist_dependency_digests_must_match(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)
    dependency_pairs = [["example-dependency", "1.0"]]
    dependency_digest = hashlib.sha256(
        json.dumps(dependency_pairs, separators=(",", ":")).encode()
    ).hexdigest()
    _mutate(
        receipt_dir,
        0,
        lambda row: row["sdist"]["installed"].update(
            dependencies=[{"name": "example-dependency", "version": "1.0"}],
            dependency_sha256=dependency_digest,
        ),
    )

    with pytest.raises(ValueError, match="dependency digest differs between wheel and sdist"):
        _verify(receipt_dir)


def test_dependency_records_must_match_their_canonical_digest(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)
    _mutate(
        receipt_dir,
        0,
        lambda row: row["wheel"]["installed"].update(
            dependencies=[{"name": "example-dependency", "version": "1.0"}]
        ),
    )

    with pytest.raises(ValueError, match="dependency records do not match their digest"):
        _verify(receipt_dir)


def test_dependency_records_must_be_canonical_sorted_and_unique(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)
    dependencies = [
        {"name": "zeta", "version": "1"},
        {"name": "alpha", "version": "1"},
    ]
    _mutate(
        receipt_dir,
        0,
        lambda row: row["wheel"]["installed"].update(dependencies=dependencies),
    )

    with pytest.raises(ValueError, match="dependencies are not in canonical order"):
        _verify(receipt_dir)


def test_dependency_records_must_not_repeat_distribution_names(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)
    dependencies = [
        {"name": "example-dependency", "version": "1.0"},
        {"name": "example-dependency", "version": "2.0"},
    ]
    _mutate(
        receipt_dir,
        0,
        lambda row: row["wheel"]["installed"].update(dependencies=dependencies),
    )

    with pytest.raises(ValueError, match="dependencies are not in canonical order"):
        _verify(receipt_dir)


def test_dependency_record_count_is_bounded(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)
    _mutate(
        receipt_dir,
        0,
        lambda row: row["wheel"]["installed"].update(dependencies=[{} for _ in range(4097)]),
    )

    with pytest.raises(ValueError, match="exceed the count limit"):
        _verify(receipt_dir)


def test_build_generators_are_exact_sanitized_records(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)
    _mutate(
        receipt_dir,
        0,
        lambda row: row["wheel"]["installed"].update(
            build_generator={"name": "setuptools", "version": "../84.0.0"}
        ),
    )

    with pytest.raises(ValueError, match="build generator record is invalid"):
        _verify(receipt_dir)


def test_sdist_build_receipt_must_bind_original_source_and_temporary_wheel(
    tmp_path: Path,
) -> None:
    receipt_dir = _write_receipts(tmp_path)
    _mutate(receipt_dir, 0, lambda row: row["sdist_build"].update(sdist_sha256="9" * 64))

    with pytest.raises(ValueError, match="sdist build receipt does not match the bound source"):
        _verify(receipt_dir)


@pytest.mark.parametrize("field", ["source_commit", "source_tree", "binding_sha256"])
def test_sdist_build_receipt_must_bind_exact_source_and_bundle(tmp_path: Path, field: str) -> None:
    receipt_dir = _write_receipts(tmp_path)
    _mutate(receipt_dir, 0, lambda row: row["sdist_build"].update({field: "9" * 64}))

    with pytest.raises(ValueError, match="sdist build receipt does not match the bound source"):
        _verify(receipt_dir)


def test_sdist_build_receipt_must_match_platform_uv_and_python(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)
    _mutate(receipt_dir, 1, lambda row: row["sdist_build"].update(uv_version="0.12.15"))

    with pytest.raises(ValueError, match="sdist build receipt does not match its platform uv"):
        _verify(receipt_dir)


def test_sdist_build_receipt_rejects_legacy_schema_and_manifest_drift(tmp_path: Path) -> None:
    legacy_root = tmp_path / "legacy"
    legacy_root.mkdir()
    legacy_receipts = _write_receipts(legacy_root)
    _mutate(legacy_receipts, 0, lambda row: row["sdist_build"].update(schema_version=1))

    with pytest.raises(ValueError, match="sdist build receipt does not match the bound source"):
        _verify(legacy_receipts)

    drift_root = tmp_path / "drift"
    drift_root.mkdir()
    drift_receipts = _write_receipts(drift_root)

    def drift_after_build(row: dict[str, Any]) -> None:
        row["sdist_build"]["after_build_packages"][-1]["version"] = "0.46.0"

    _mutate(drift_receipts, 0, drift_after_build)

    with pytest.raises(ValueError, match="package manifests differ across qualification stages"):
        _verify(drift_receipts)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("build_lock_sha256", "8" * 64, "build lock digest differs"),
        ("environment_descriptor_sha256", "8" * 64, "environment descriptor differs"),
        ("provisioning_recipe_sha256", "8" * 64, "provisioning recipe differs"),
        ("provisioning_evidence_sha256", "8" * 64, "provisioning evidence differs"),
        ("target_os", "freebsd", "target does not match"),
        ("target_architecture", "arm64", "target does not match"),
        ("python_implementation", "PyPy", "implementation is unsupported"),
        ("python_executable_sha256", "invalid", "Python executable digest"),
    ],
)
def test_sdist_build_receipt_rejects_unbound_environment_values(
    tmp_path: Path, field: str, value: str, message: str
) -> None:
    receipt_dir = _write_receipts(tmp_path)
    _mutate(receipt_dir, 0, lambda row: row["sdist_build"].update({field: value}))

    with pytest.raises(ValueError, match=message):
        _verify(receipt_dir)


@pytest.mark.parametrize("field", ["marker_applicable", "satisfier"])
def test_receipt_rejects_forged_requirement_marker_or_satisfier(tmp_path: Path, field: str) -> None:
    receipt_dir = _write_receipts(tmp_path)

    def mutate_requirement(row: dict[str, Any]) -> None:
        if field == "marker_applicable":
            record = row["sdist_build"]["dynamic_requirement_records"][0]
            record[field] = True
            record["satisfier"] = {"name": "platform-only", "version": "2.1.0"}
        else:
            record = row["sdist_build"]["dynamic_requirement_records"][2]
            record[field]["version"] = "0.45.2"

    _mutate(receipt_dir, 0, mutate_requirement)

    message = (
        "marker applicability is forged" if field == "marker_applicable" else "satisfier is forged"
    )
    with pytest.raises(ValueError, match=message):
        _verify(receipt_dir)


def test_receipt_accepts_inapplicable_marker_with_null_satisfier(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)
    row = json.loads((receipt_dir / "row-0.json").read_text(encoding="utf-8"))
    requirement = row["sdist_build"]["dynamic_requirement_records"][0]

    assert requirement["marker_applicable"] is False
    assert requirement["satisfier"] is None
    _verify(receipt_dir)


def test_aggregator_requires_independent_build_environment_bindings() -> None:
    with pytest.raises(SystemExit) as missing_argument:
        release_cli._parser().parse_args(
            [
                "verify-receipts",
                "--receipt-dir",
                "receipts",
                "--expected-commit",
                SOURCE_COMMIT,
                "--expected-tree",
                SOURCE_TREE,
                "--expected-binding",
                _binding().to_json(),
                "--artifact-id",
                "42",
                "--artifact-digest",
                ARTIFACT_DIGEST,
                "--run-id",
                "77",
            ]
        )
    assert missing_argument.value.code == 2

    missing_target = _expected_build_environment_document()
    del missing_target["targets"]["windows-x64"]
    with pytest.raises(ValueError, match="exact target set"):
        ExpectedBuildEnvironmentBindings.from_bytes(
            json.dumps(missing_target, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )

    bindings = _expected_build_environment_document()
    linux_binding = bindings["targets"]["linux-x64"]
    encoded = json.dumps(bindings, sort_keys=True, separators=(",", ":"))
    target_entry = '"linux-x64":' + json.dumps(linux_binding, sort_keys=True, separators=(",", ":"))
    duplicate_target = encoded.replace(target_entry, f"{target_entry},{target_entry}", 1)
    with pytest.raises(ValueError, match="duplicate object key"):
        ExpectedBuildEnvironmentBindings.from_bytes(duplicate_target.encode("utf-8"))


def test_sdist_build_receipt_must_bind_temporary_wheel_digest(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)
    _mutate(receipt_dir, 0, lambda row: row["sdist_build"].update(wheel_sha256="invalid"))

    with pytest.raises(ValueError, match="temporary wheel digest must be a lowercase SHA-256"):
        _verify(receipt_dir)


def test_sdist_installed_generator_must_match_observed_backend(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)

    def mutation(row: dict[str, Any]) -> None:
        build = row["sdist_build"]
        build["backend_version"] = "85.0.0"
        build["static_requirement_records"][0]["satisfier"]["version"] = "85.0.0"
        _replace_build_manifests(
            build,
            [
                {"name": "setuptools", "version": "85.0.0"},
                {"name": "wheel", "version": "0.45.1"},
            ],
        )

    _mutate(receipt_dir, 0, mutation)

    with pytest.raises(
        ValueError, match="sdist install generator differs from observed build backend"
    ):
        _verify(receipt_dir)


def test_wheel_generator_may_differ_from_sdist_build_backend(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)
    _mutate(
        receipt_dir,
        0,
        lambda row: row["wheel"]["installed"].update(
            build_generator={"name": "setuptools", "version": "83.0.0"}
        ),
    )

    _verify(receipt_dir)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("local_path", "/private/tmp/build", "sdist build receipt fields are invalid"),
        ("stdout", "raw backend output", "sdist build receipt fields are invalid"),
        ("backend", "file:///private/tmp/backend", "sdist build backend is unsupported"),
    ],
)
def test_sdist_build_receipt_rejects_paths_secrets_and_raw_output(
    tmp_path: Path, field: str, value: str, message: str
) -> None:
    receipt_dir = _write_receipts(tmp_path)
    _mutate(receipt_dir, 0, lambda row: row["sdist_build"].update({field: value}))

    with pytest.raises(ValueError, match=message):
        _verify(receipt_dir)


def test_sdist_build_manifest_must_be_sorted_unique_and_bounded(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)

    def mutation(row: dict[str, Any]) -> None:
        _replace_build_manifests(
            row["sdist_build"],
            [
                {"name": "wheel", "version": "0.45.1"},
                {"name": "setuptools", "version": "84.0.0"},
            ],
        )

    _mutate(receipt_dir, 0, mutation)

    with pytest.raises(ValueError, match="build package manifest is not canonical"):
        _verify(receipt_dir)


def test_sdist_build_package_manifest_count_is_bounded(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)
    _mutate(
        receipt_dir,
        0,
        lambda row: row["sdist_build"].update(
            provisioned_packages=[
                {"name": f"package-{index:04d}", "version": "1.0"} for index in range(4097)
            ]
        ),
    )

    with pytest.raises(
        ValueError, match="build package manifest is invalid or exceeds its count limit"
    ):
        _verify(receipt_dir)


def test_sdist_build_static_requirement_must_be_satisfied(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)

    def mutation(row: dict[str, Any]) -> None:
        build = row["sdist_build"]
        build["backend_version"] = "60.0.0"
        _replace_build_manifests(
            build,
            [
                {"name": "setuptools", "version": "60.0.0"},
                {"name": "wheel", "version": "0.45.1"},
            ],
        )
        row["sdist"]["installed"]["build_generator"].update(version="60.0.0")

    _mutate(receipt_dir, 0, mutation)

    with pytest.raises(ValueError, match="not satisfied by the observed build environment"):
        _verify(receipt_dir)


def test_sdist_build_static_requirements_must_match_checked_out_source(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)
    _mutate(
        receipt_dir,
        0,
        lambda row: row["sdist_build"]["static_requirement_records"][0].update(
            expression="setuptools>=70"
        ),
    )

    with pytest.raises(
        ValueError, match="static build requirements differ from checked-out source metadata"
    ):
        _verify(receipt_dir)


def test_sdist_build_rejects_static_requirement_extras(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)
    extra_requirement = "setuptools[security]>=61"
    _mutate(
        receipt_dir,
        0,
        lambda row: row["sdist_build"]["static_requirement_records"][0].update(
            expression=extra_requirement
        ),
    )

    with pytest.raises(ValueError, match="extras are not permitted"):
        _verify(receipt_dir)


def test_sdist_build_dynamic_requirement_must_bind_observed_package(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)
    _mutate(
        receipt_dir,
        0,
        lambda row: row["sdist_build"]["dynamic_requirement_records"][2]["satisfier"].update(
            version="9.9.9"
        ),
    )

    with pytest.raises(ValueError, match="satisfier is forged or incompatible"):
        _verify(receipt_dir)


def test_sdist_build_accepts_dynamic_requirement_bound_to_installed_package(
    tmp_path: Path,
) -> None:
    receipt_dir = _write_receipts(tmp_path)
    _mutate(
        receipt_dir,
        0,
        lambda row: row["sdist_build"].update(
            dynamic_requirement_records=[
                {
                    "expression": "wheel>=0.45",
                    "marker_applicable": True,
                    "satisfier": {"name": "wheel", "version": "0.45.1"},
                }
            ]
        ),
    )

    _verify(receipt_dir)


def test_sdist_build_accepts_no_dynamic_requirement_records(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)
    _mutate(
        receipt_dir,
        0,
        lambda row: row["sdist_build"].update(dynamic_requirement_records=[]),
    )

    _verify(receipt_dir)


def test_sdist_build_rejects_dynamic_constraint_mismatch(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)
    _mutate(
        receipt_dir,
        0,
        lambda row: row["sdist_build"]["dynamic_requirement_records"][2].update(
            expression="wheel>=99"
        ),
    )

    with pytest.raises(ValueError, match="satisfier version does not satisfy its expression"):
        _verify(receipt_dir)


def test_sdist_build_rejects_unbound_dynamic_marker(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)
    _mutate(
        receipt_dir,
        0,
        lambda row: row["sdist_build"]["dynamic_requirement_records"][2].update(
            expression="wheel>=0.45; platform_release == 'x'"
        ),
    )

    with pytest.raises(ValueError, match="unbound platform marker"):
        _verify(receipt_dir)


def test_sdist_build_rejects_unbound_dynamic_extra_marker(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)
    _mutate(
        receipt_dir,
        0,
        lambda row: row["sdist_build"]["dynamic_requirement_records"][2].update(
            expression="wheel>=0.45; extra == 'speedups'"
        ),
    )

    with pytest.raises(ValueError, match="unbound platform marker"):
        _verify(receipt_dir)


def test_sdist_build_rejects_unknown_marker_context(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)
    _mutate(
        receipt_dir,
        0,
        lambda row: row["sdist_build"]["dynamic_requirement_records"][2].update(
            expression="wheel>=0.45; unknown_context == 'x'"
        ),
    )

    with pytest.raises(ValueError, match="invalid build requirement record"):
        _verify(receipt_dir)


@pytest.mark.parametrize("marker_name", ["extras", "dependency_groups"])
def test_sdist_build_rejects_unbound_dynamic_context_marker(
    tmp_path: Path, marker_name: str
) -> None:
    receipt_dir = _write_receipts(tmp_path)
    _mutate(
        receipt_dir,
        0,
        lambda row: row["sdist_build"]["dynamic_requirement_records"][2].update(
            expression=f"wheel>=0.45; {marker_name} == 'speedups'"
        ),
    )

    with pytest.raises(ValueError, match="unbound platform marker"):
        _verify(receipt_dir)


def test_sdist_build_rejects_dynamic_requirement_extras(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)
    _mutate(
        receipt_dir,
        0,
        lambda row: row["sdist_build"]["dynamic_requirement_records"][2].update(
            expression="wheel[speedups]>=0.45"
        ),
    )

    with pytest.raises(ValueError, match="extras are not permitted"):
        _verify(receipt_dir)


def test_sdist_build_rejects_direct_url_requirement(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)
    direct_url = "setuptools @ https://example.invalid/setuptools.whl"
    _mutate(
        receipt_dir,
        0,
        lambda row: row["sdist_build"]["static_requirement_records"][0].update(
            expression=direct_url
        ),
    )

    with pytest.raises(ValueError, match="unverifiable URL"):
        _verify(receipt_dir)


def test_all_rows_must_bind_the_same_lock_digest(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)
    _mutate(receipt_dir, 1, lambda row: row.update(lock_sha256="9" * 64))

    with pytest.raises(ValueError, match="does not match the checked-out uv.lock"):
        _verify(receipt_dir)


@pytest.mark.parametrize("forbidden_key", ["freeze", "pip_freeze", "local_path"])
def test_unsanitized_or_unrecognized_fields_are_rejected(
    tmp_path: Path, forbidden_key: str
) -> None:
    receipt_dir = _write_receipts(tmp_path)
    _mutate(receipt_dir, 0, lambda row: row.update({forbidden_key: ["private/local/value"]}))

    with pytest.raises(ValueError, match="receipt fields are invalid"):
        _verify(receipt_dir)


def test_receipt_json_with_duplicate_keys_is_rejected(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)
    (receipt_dir / "row-0.json").write_text('{"run_id":"1","run_id":"2"}')

    with pytest.raises(ValueError, match="duplicate JSON object key"):
        _verify(receipt_dir)


def test_unexpected_receipt_file_is_rejected(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)
    (receipt_dir / "notes.txt").write_text("not a receipt")

    with pytest.raises(ValueError, match="Receipt directory must contain only regular JSON files"):
        _verify(receipt_dir)


def test_receipt_file_size_is_bounded(tmp_path: Path) -> None:
    receipt_dir = _write_receipts(tmp_path)
    (receipt_dir / "row-0.json").write_text(" " * (256 * 1024 + 1))

    with pytest.raises(ValueError, match="receipt file size limit exceeded"):
        _verify(receipt_dir)


def test_cli_verify_receipts_emits_only_sanitized_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    receipt_dir = _write_receipts(tmp_path)
    expected_environments = tmp_path / "expected-build-environments.json"
    expected_environments.write_text(
        json.dumps(_expected_build_environment_document()), encoding="utf-8"
    )

    result = release_cli.main(
        [
            "verify-receipts",
            "--receipt-dir",
            str(receipt_dir),
            "--expected-commit",
            SOURCE_COMMIT,
            "--expected-tree",
            SOURCE_TREE,
            "--expected-binding",
            _binding().to_json(),
            "--artifact-id",
            "42",
            "--artifact-digest",
            ARTIFACT_DIGEST,
            "--run-id",
            "77",
            "--expected-build-environments",
            str(expected_environments),
            "--expected-platform-count",
            "3",
        ]
    )

    captured = capsys.readouterr()
    assert result == 0
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "run_id": "77",
        "source_commit": SOURCE_COMMIT,
        "source_tree": SOURCE_TREE,
        "artifact_id": "42",
        "artifact_digest": ARTIFACT_DIGEST,
        "lock_sha256": LOCK_DIGEST,
        "build_lock_sha256": BUILD_LOCK_DIGEST,
        "platforms": ["linux/x64", "macos/arm64", "windows/x64"],
    }
    assert str(receipt_dir) not in captured.out


def _mutate(receipt_dir: Path, index: int, mutation: Any) -> None:
    path = receipt_dir / f"row-{index}.json"
    row = json.loads(path.read_text(encoding="utf-8"))
    mutation(row)
    path.write_text(json.dumps(row), encoding="utf-8")
