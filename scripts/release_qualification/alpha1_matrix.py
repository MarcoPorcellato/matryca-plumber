"""Explicit experimental OG qualification, separate from legacy RC4 receipt policy.

Expected identities originate in the selected source and authenticated upstream
job outputs. Submitted row claims are never used to manufacture expectations.
"""

from __future__ import annotations

import hashlib
import json
import platform
import re
import sys
import tempfile
import tomllib
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, cast

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from scripts.build_release_artifacts import (
    LockedBuildEnvironment,
    build_release_artifacts,
    verify_locked_build_environment,
)
from scripts.release_qualification import bundle, installed, sdist_build
from scripts.release_qualification.build_environment import (
    BuildEnvironmentDescriptor,
    _parse_json_object,
)
from scripts.release_qualification.bundle import BundleBinding

POLICY = "og-alpha2"
VERSION = "2.1.0a2"
RESOURCE_ROOT = Path("matryca_plumber/graph_gateway/resources/og-v1")
ROWS = tuple(
    (system, architecture, minor, kind)
    for system, architecture in (("linux", "x64"), ("macos", "arm64"))
    for minor in ("3.12", "3.13")
    for kind in ("wheel", "sdist")
)
OPERATIONAL_CHECKS = (
    "installed-origin",
    "resource-and-code-byte-authentication",
    "schema-golden-bindings",
    "same-root-repeatability",
    "relocation-invariance",
    "source-change-sensitivity",
    "globally-unique-success-session-identities",
    "strict-invalid-root-error",
    "native-timeout-cleanup",
    "native-stdout-overflow-cleanup",
    "native-stderr-overflow-cleanup",
    "native-same-group-survivor-kill-escalation",
    "injected-cleanup-interruption-fallback",
)
_STATIC_TCKS = ["PASS", "PASS", "PASS"]
_ROW_FIELDS = {
    "schema_version",
    "row",
    "run_id",
    "run_attempt",
    "binding_sha256",
    "inputs_sha256",
    "job_name",
    "status",
    "qualification",
    "cleanup",
    "runtime",
    "installed",
    "operational",
    "build",
}


def row_job_name(system: str, architecture: str, minor: str) -> str:
    """Match the explicit upstream job names, not a submitted display-name claim."""
    return f"OG {system}-{architecture} Python {minor}"


JOB_NAMES = (
    "Build OG alpha",
    "Source OG controls",
    "Windows OG refusal",
    *(
        row_job_name(system, architecture, minor)
        for system, architecture in (("linux", "x64"), ("macos", "arm64"))
        for minor in ("3.12", "3.13")
    ),
)
ARTIFACT_KEYS = (
    "build",
    "source-controls",
    "windows-refusal",
    "linux312",
    "linux313",
    "macos312",
    "macos313",
)


def canonical(value: object) -> bytes:
    """Canonical finite JSON bytes, including type distinctions."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value: object) -> str:
    """Bind the exact canonical JSON representation."""
    return hashlib.sha256(canonical(value)).hexdigest()


def document(raw: bytes) -> dict[str, Any]:
    """Bound JSON and reject duplicate keys and non-standard constants."""
    return _parse_json_object(raw, "Alpha qualification")


def read_document(path: Path) -> dict[str, Any]:
    """Read only a bounded regular evidence file."""
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 262_144:
        raise ValueError("Alpha evidence must be a bounded regular file.")
    with path.open("rb") as stream:
        return document(stream.read(262_145))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _digest_value(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


@dataclass(frozen=True, slots=True)
class MatrixContext:
    """Source-derived expectations; do not construct this from a submitted row."""

    binding: BundleBinding
    run_id: str
    run_attempt: int
    resources: dict[str, Any]
    source_controls: dict[str, Any]
    build_lock_sha256: str
    recipe_sha256: str
    build_packages: tuple[tuple[str, str], ...]
    requirements: tuple[str, ...]

    @property
    def inputs_sha256(self) -> str:
        """Bind resources, fixtures, golden bytes, exact dependencies and run identity."""
        return digest(asdict(self))


def source_context(
    source: Path, binding: BundleBinding, run_id: str, run_attempt: int
) -> MatrixContext:
    """Recompute expectations from the clean selected tree, never from test reports."""
    bundle._validate_binding(binding, policy=POLICY)
    installed._verify_source(source, binding)
    _require(
        isinstance(run_id, str) and re.fullmatch(r"[1-9][0-9]*", run_id) is not None,
        "Invalid workflow run ID.",
    )
    _require(type(run_attempt) is int and run_attempt > 0, "Invalid workflow run attempt.")
    root = source / RESOURCE_ROOT
    descriptor = read_document(root / "descriptor.json")
    manifest = read_document(root / "manifest.json")
    _require(descriptor["qualification"] == "unqualified", "Source profile qualification changed.")
    assets = []
    for name, expected in sorted(manifest["files"].items()):
        _require(bundle._canonical_member_name(name) == name, "Invalid resource path.")
        path = root / name
        _require(
            not path.is_symlink() and path.is_file() and path.stat().st_size <= 16_777_216,
            "Invalid source resource.",
        )
        observed = hashlib.sha256(path.read_bytes()).hexdigest()
        _require(observed == expected, "Source resource digest mismatch.")
        assets.append({"path": name, "sha256": observed})
    modules = []
    for item in descriptor["code_modules"]:
        name = bundle._canonical_member_name(item["path"])
        observed = hashlib.sha256(
            (source / "matryca_plumber/graph_gateway" / name).read_bytes()
        ).hexdigest()
        _require(observed == item["sha256"], "Source TCK/consumer digest mismatch.")
        modules.append({"path": name, "sha256": observed})
    resources = {
        "assets": assets,
        "code_modules": sorted(modules, key=lambda item: item["path"]),
        "descriptor_sha256": hashlib.sha256((root / "descriptor.json").read_bytes()).hexdigest(),
        "manifest_sha256": hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest(),
    }
    cases = read_document(root / "tck-cases.json")
    profile = read_document(root / "dependency-profile.json")
    _require(
        profile["project"] == {"name": "matryca-plumber", "version": VERSION}
        and profile["parser"] == {"name": "logseq-matryca-parser", "version": "1.9.0"},
        "Source dependency profile identity mismatch.",
    )
    _require(
        profile["lock_sha256"] == hashlib.sha256((source / "uv.lock").read_bytes()).hexdigest(),
        "Source root lock differs from the packaged dependency profile.",
    )
    lock = source / "release-qualification-build/uv.lock"
    packages = tuple(
        sorted(
            (item["name"], item["version"])
            for item in tomllib.loads(lock.read_text())["package"]
            if "registry" in item.get("source", {})
        )
    )
    requirements = tuple(
        line.rstrip(" \\")
        for line in (root / "requirements-og-v1-parser-1.9.0.txt").read_text().splitlines()
        if line and not line.startswith((" ", "#", "--"))
    )
    return MatrixContext(
        binding,
        run_id,
        run_attempt,
        resources,
        cases["source_unit_controls"],
        hashlib.sha256(lock.read_bytes()).hexdigest(),
        hashlib.sha256(
            (source / "release-qualification-build/provisioning-recipe.json").read_bytes()
        ).hexdigest(),
        packages,
        requirements,
    )


def _runtime_dependencies(context: MatrixContext, runtime: dict[str, Any]) -> list[dict[str, str]]:
    environment = cast(dict[str, str], default_environment())
    environment.update(
        python_version=".".join(runtime["version"].split(".")[:2]),
        python_full_version=runtime["version"],
        implementation_name="cpython",
        platform_python_implementation="CPython",
        sys_platform="linux" if runtime["system"] == "linux" else "darwin",
        platform_system="Linux" if runtime["system"] == "linux" else "Darwin",
        platform_machine="x86_64" if runtime["architecture"] == "x64" else "arm64",
        os_name="posix",
        extra="",
    )
    packages: dict[str, str] = {}
    for raw in context.requirements:
        requirement = Requirement(raw)
        _require(
            requirement.url is None and len(requirement.specifier) == 1,
            "Dependency profile must be exactly pinned.",
        )
        specifier = next(iter(requirement.specifier))
        _require(
            specifier.operator == "==" and "*" not in specifier.version,
            "Dependency profile is not exact.",
        )
        if requirement.marker is None or requirement.marker.evaluate(environment):
            name = canonicalize_name(requirement.name)
            if name in {"matryca-plumber", "pip"}:
                continue
            _require(name not in packages, "Duplicate applicable dependency.")
            packages[name] = specifier.version
    return [{"name": name, "version": version} for name, version in sorted(packages.items())]


def _verify_build(
    context: MatrixContext, build: dict[str, Any], key: str, system: str, architecture: str
) -> None:
    binding = context.binding
    expected = {
        "instance": key,
        "schema_version": 2,
        "source_commit": binding.source_commit,
        "source_tree": binding.source_tree,
        "binding_sha256": digest(asdict(binding)),
        "sdist_name": binding.sdist_name,
        "sdist_size": binding.sdist_size,
        "sdist_sha256": binding.sdist_sha256,
        "wheel_name": binding.wheel_name,
        "build_lock_sha256": context.build_lock_sha256,
        "provisioning_recipe_sha256": context.recipe_sha256,
        "target_os": system,
        "target_architecture": architecture,
        "python_implementation": "CPython",
        "backend": "setuptools.build_meta",
        "backend_version": dict(context.build_packages)["setuptools"],
    }
    for name, value in expected.items():
        _require(
            type(build.get(name)) is type(value) and build[name] == value,
            f"Alpha sdist build binding mismatch: {name}.",
        )
    _require(
        isinstance(build.get("python_version"), str)
        and re.fullmatch(r"3\.12\.[0-9]+", build["python_version"]) is not None,
        "Sdist builds require independent CPython 3.12.",
    )
    for name in (
        "wheel_sha256",
        "environment_descriptor_sha256",
        "provisioning_evidence_sha256",
        "python_executable_sha256",
        "uv_sha256",
    ):
        _require(_digest_value(build.get(name)), "Missing exact sdist build identity.")
    _require(
        type(build.get("wheel_size")) is int and build["wheel_size"] > 0,
        "Invalid temporary wheel size.",
    )
    _require(build.get("uv_version") == "0.12.19", "Unexpected qualification uv version.")
    packages = [{"name": name, "version": version} for name, version in context.build_packages]
    descriptor_value = build.get("environment_descriptor")
    provisioning = build.get("provisioning_evidence")
    if not isinstance(descriptor_value, dict) or not isinstance(provisioning, dict):
        raise ValueError("Complete build descriptor and provisioning evidence are required.")
    descriptor = BuildEnvironmentDescriptor.from_bytes(canonical(descriptor_value))
    _require(
        digest(descriptor_value) == build["environment_descriptor_sha256"]
        and digest(provisioning) == build["provisioning_evidence_sha256"],
        "Build evidence byte identity mismatch.",
    )
    for name in (
        "source_commit",
        "source_tree",
        "binding_sha256",
        "sdist_name",
        "sdist_size",
        "sdist_sha256",
        "build_lock_sha256",
        "provisioning_recipe_sha256",
        "provisioning_evidence_sha256",
        "uv_version",
        "uv_sha256",
        "target_os",
        "target_architecture",
        "python_implementation",
        "python_version",
        "python_executable_sha256",
    ):
        _require(
            getattr(descriptor, name) == build[name], "Build descriptor/receipt identity differs."
        )
    _require(
        descriptor.packages == context.build_packages
        and provisioning.get("instance") == key
        and provisioning.get("run_id") == context.run_id
        and type(provisioning.get("run_attempt")) is int
        and provisioning["run_attempt"] == context.run_attempt
        and provisioning.get("operation") == "uv-sync-locked-no-install-project",
        "Build provisioning is not bound to this source/run/instance.",
    )
    for name in (
        "provisioned_packages",
        "before_hooks_packages",
        "after_hooks_packages",
        "after_build_packages",
    ):
        _require(build.get(name) == packages, "Unprovisioned or changed sdist build packages.")
    for name in ("static_requirement_records", "dynamic_requirement_records"):
        _require(isinstance(build.get(name), list), "Missing build requirement observations.")
        for record in build[name]:
            _require(
                isinstance(record, dict)
                and set(record) == {"expression", "marker_applicable", "satisfier"},
                "Malformed build requirement observation.",
            )
            satisfier = record["satisfier"]
            pair = None if satisfier is None else (satisfier["name"], satisfier["version"])
            observed = sdist_build.BuildRequirementRecord(
                record["expression"], record["marker_applicable"], pair
            )
            observed.validate(
                dict(context.build_packages),
                target_os=system,
                target_architecture=architecture,
                python_implementation="CPython",
                python_version=build["python_version"],
            )

    _require(
        [item["expression"] for item in build["static_requirement_records"]]
        == ["setuptools>=61", "wheel"],
        "Static build requirement coverage is incomplete.",
    )


def verify_row(
    context: MatrixContext, row: dict[str, Any], expected: tuple[str, str, str, str]
) -> None:
    """Authenticate one full installed and operational result against fixed expectations."""
    system, architecture, minor, kind = expected
    key = f"{system}-{architecture}-{minor}-{kind}"
    _require(set(row) == _ROW_FIELDS, "Malformed alpha row fields.")
    values = {
        "schema_version": 1,
        "row": key,
        "run_id": context.run_id,
        "run_attempt": context.run_attempt,
        "binding_sha256": digest(asdict(context.binding)),
        "inputs_sha256": context.inputs_sha256,
        "job_name": row_job_name(system, architecture, minor),
        "status": "pass",
        "qualification": "unqualified",
        "cleanup": "verified",
    }
    for name, value in values.items():
        _require(
            type(row.get(name)) is type(value) and row[name] == value,
            f"Alpha row binding mismatch: {name}.",
        )
    runtime = row["runtime"]
    _require(
        isinstance(runtime, dict)
        and set(runtime)
        == {"implementation", "version", "system", "architecture", "executable_sha256"},
        "Malformed runtime identity.",
    )
    _require(
        runtime["implementation"] == "CPython"
        and runtime["system"] == system
        and runtime["architecture"] == architecture
        and isinstance(runtime["version"], str)
        and re.fullmatch(re.escape(minor) + r"\.[0-9]+", runtime["version"]) is not None
        and _digest_value(runtime["executable_sha256"]),
        "Runtime does not match its planned row.",
    )
    receipt = row["installed"]
    _require(
        isinstance(receipt, dict)
        and set(receipt) == set(installed.InstalledReceipt.__dataclass_fields__),
        "Missing full installed verification.",
    )
    os_name, machine = ("Linux", "x86_64") if system == "linux" else ("Darwin", "arm64")
    _require(
        receipt["kind"] == kind
        and receipt["operating_system"] == os_name.lower()
        and receipt["architecture"] == machine
        and receipt["python_version"] == runtime["version"]
        and receipt["version"] == VERSION
        and receipt["location_class"] == "isolated-venv-site-packages"
        and list(receipt["tck_outcomes"]) == _STATIC_TCKS,
        "Installed verification identity or static TCK mismatch.",
    )
    for name in ("record_sha256", "resource_sha256", "dependency_sha256"):
        _require(_digest_value(receipt[name]), "Incomplete installed inventory evidence.")
    versions = dict(context.build_packages)
    _require(
        receipt["build_generator"]
        in (
            {"name": "setuptools", "version": versions["setuptools"]},
            {"name": "bdist_wheel", "version": versions["wheel"]},
        ),
        "Installed wheel generator differs from the locked build.",
    )
    dependencies = _runtime_dependencies(context, runtime)
    _require(
        receipt["dependencies"] == dependencies
        and receipt["dependency_sha256"]
        == digest([[item["name"], item["version"]] for item in dependencies]),
        "Installed dependencies differ from the exact profile.",
    )
    report = row["operational"]
    _require(
        isinstance(report, dict)
        and type(report.get("schema_version")) is int
        and report["schema_version"] == 1
        and report.get("profile") == "plumber.og.operational/v1"
        and report.get("status") == "pass"
        and report.get("qualification") == "unqualified"
        and report.get("reason") == "black_box_controls_passed",
        "Operational report is incomplete or not PASS.",
    )
    _require(
        report.get("resources") == context.resources,
        "Operational resources differ from selected source.",
    )
    _require(
        report.get("cleanup") == {"status": "verified", "retained_owned_synthetic_root": False},
        "Operational cleanup is uncertain.",
    )
    checks = report.get("checks")
    _require(
        isinstance(checks, list) and len(checks) == len(OPERATIONAL_CHECKS),
        "Operational control inventory is incomplete.",
    )
    _require(
        {
            item.get("id")
            for item in checks
            if isinstance(item, dict) and item.get("status") == "pass"
        }
        == set(OPERATIONAL_CHECKS),
        "Operational control outcomes are incomplete or duplicated.",
    )
    environment = report.get("environment", {})
    _require(
        environment.get("installed_origin") is True
        and environment.get("editable") is False
        and environment.get("operating_system") == os_name
        and environment.get("architecture") == machine
        and environment.get("python_version") == runtime["version"]
        and environment.get("plumber_version") == VERSION
        and environment.get("parser_version") == "1.9.0"
        and _digest_value(environment.get("sha256")),
        "Operational environment binding failed.",
    )
    _require(
        report.get("evidence_limits", {}).get("source_unit_controls")
        == {"status": "mapped_not_executed_by_installed_tck", "tests": context.source_controls},
        "Source controls must remain separately qualified, not relabeled.",
    )
    if kind == "wheel":
        _require(row["build"] is None, "Original wheel row must not claim an sdist build.")
    else:
        _require(isinstance(row["build"], dict), "Original sdist row needs its own build.")
        _verify_build(context, row["build"], key, system, architecture)


def verify_matrix(
    context: MatrixContext,
    rows: list[dict[str, Any]],
    jobs: list[dict[str, Any]],
    source: dict[str, Any],
    windows: dict[str, Any],
    *,
    public_input: bool = False,
) -> dict[str, Any]:
    """Fail closed unless all eight rows and independent upstream jobs are complete."""
    bundle._validate_binding(context.binding, policy=POLICY)
    _require(
        type(context.run_attempt) is int and context.run_attempt > 0, "Invalid expected attempt."
    )
    _require(len(rows) == len(ROWS), "Alpha requires exactly eight installed rows.")
    indexed = {row.get("row"): row for row in rows}
    _require(len(indexed) == len(ROWS), "Duplicate alpha rows.")
    descriptors: set[str] = set()
    for expected in ROWS:
        key = "-".join(expected)
        _require(key in indexed, "Missing or extra alpha row.")
        row = indexed[key]
        verify_row(context, row, expected)
        if expected[3] == "sdist":
            descriptors.add(row["build"]["environment_descriptor_sha256"])
    _require(len(descriptors) == 4, "Four distinct sdist build environments are required.")
    if public_input:
        _require(context.run_attempt == 1, "Public qualification must be attempt one.")
    job_names = ("Admit public OG alpha", *JOB_NAMES[1:]) if public_input else JOB_NAMES
    for name in job_names:
        matching = [job for job in jobs if job.get("name") == name]
        _require(len(matching) == 1, "Missing or duplicate upstream job.")
        job = matching[0]
        _require(
            job.get("status") == "completed"
            and job.get("conclusion") == "success"
            and type(job.get("run_id")) is int
            and str(job["run_id"]) == context.run_id
            and job.get("head_sha") == context.binding.source_commit,
            "An upstream job did not succeed on the exact source.",
        )
    for report in (source, windows):
        for name, value in {
            "source_commit": context.binding.source_commit,
            "source_tree": context.binding.source_tree,
            "run_id": context.run_id,
            "run_attempt": context.run_attempt,
            "status": "pass",
        }.items():
            _require(
                type(report.get(name)) is type(value) and report[name] == value,
                "Source/refusal evidence is stale or incomplete.",
            )
    _require(
        source.get("selectors") == context.source_controls
        and source.get("qualification") == "source-only"
        and type(source.get("cases")) is int
        and source["cases"] > 0
        and _digest_value(source.get("junit_sha256")),
        "Separate source-control evidence is missing.",
    )
    _require(
        windows.get("qualification") == "refusal-only"
        and windows.get("system") == "Windows"
        and windows.get("architecture") == "AMD64"
        and type(windows.get("exit_code")) is int
        and windows["exit_code"] == 7
        and windows.get("error") == "unsupported_platform"
        and type(windows.get("graph_accesses")) is int
        and windows["graph_accesses"] == 0,
        "Windows refusal is not proven before graph access.",
    )
    return {
        "schema_version": 1,
        "status": "pass",
        "qualification": "unqualified",
        "version": VERSION,
        "source_commit": context.binding.source_commit,
        "source_tree": context.binding.source_tree,
        "run_id": context.run_id,
        "run_attempt": context.run_attempt,
        "inputs_sha256": context.inputs_sha256,
        "rows": sorted(indexed),
        "evidence_limits": (
            "experimental OG source/artifact qualification only; "
            "no publication, stable support or Trama admission"
        ),
    }


def locked_build_selection(
    source: Path, python: Path, uv: Path
) -> tuple[LockedBuildEnvironment, dict[str, Any]]:
    """Measure caller-provisioned tools, then independently check the source lock."""
    executable, implementation, version = sdist_build._python_identity(python)
    _require(uv.is_absolute(), "Qualification uv path must be absolute.")
    uv_digest = sdist_build._sha256_file(uv.resolve(strict=True))
    selected_uv, _ = sdist_build._safe_uv(uv, uv_digest)
    uv_version = sdist_build._read_uv_version(selected_uv)
    _require(uv_version == "0.12.19", "Alpha hosted qualification requires uv 0.12.19.")
    lock = source / "release-qualification-build/uv.lock"
    lock_digest = hashlib.sha256(lock.read_bytes()).hexdigest()
    packages = tuple(
        sorted(
            (item["name"], item["version"])
            for item in tomllib.loads(lock.read_text())["package"]
            if "registry" in item.get("source", {})
        )
    )
    selected = LockedBuildEnvironment(
        python.absolute(),
        selected_uv,
        sdist_build._sha256_file(executable),
        uv_digest,
        lock_digest,
        packages,
    )
    verify_locked_build_environment(source, selected)
    system, architecture = sdist_build._native_marker_target()
    _require(
        (system, architecture) in (("linux", "x64"), ("macos", "arm64")),
        "Unsupported alpha build worker.",
    )
    record = {
        "python_implementation": implementation,
        "python_version": version,
        "python_executable_sha256": selected.python_sha256,
        "uv_version": uv_version,
        "uv_sha256": uv_digest,
        "build_lock_sha256": lock_digest,
        "target_os": system,
        "target_architecture": architecture,
        "packages": [{"name": name, "version": value} for name, value in packages],
    }
    return selected, record


def build_alpha(
    source: Path, dist: Path, ledger: Path, python: Path, uv: Path, expected_commit: str
) -> tuple[BundleBinding, dict[str, Any]]:
    """Use the canonical frontend/sdist/wheel sequence with enforced locked tools."""
    _require(
        bundle._git_value(source, "HEAD") == expected_commit,
        "Alpha build source does not match selection.",
    )
    _require(
        not installed._git_value(source, "status", "--porcelain", "--untracked-files=all"),
        "Alpha build requires a clean source.",
    )
    _require(
        tomllib.loads((source / "pyproject.toml").read_text())["project"]["version"] == VERSION,
        "Alpha build version differs from policy.",
    )
    selected, record = locked_build_selection(source, python, uv)
    frontend_versions = {}
    for tool, pattern in (("node", r"v22\.[0-9]+\.[0-9]+"), ("npm", r"[0-9]+\.[0-9]+\.[0-9]+")):
        observed = sdist_build._run_bounded([tool, "--version"], timeout=10, capture=True)
        _require(observed.returncode == 0, "Could not measure canonical frontend tool.")
        version = observed.stdout.decode("ascii").strip()
        _require(re.fullmatch(pattern, version) is not None, "Invalid canonical frontend tool.")
        frontend_versions[tool + "_version"] = version
    build_release_artifacts(source, dist, content_ledger_path=ledger, locked_build=selected)
    binding = bundle.build_binding(source, dist, ledger, expected_commit, policy=POLICY)
    verify_locked_build_environment(source, selected)
    return binding, {
        **record,
        **frontend_versions,
        "source_commit": binding.source_commit,
        "source_tree": binding.source_tree,
        "binding_sha256": digest(asdict(binding)),
    }


def _descriptor(
    context: MatrixContext,
    selected: LockedBuildEnvironment,
    record: dict[str, Any],
    key: str,
    output: Path,
) -> tuple[Path, str]:
    """Bind each separately provisioned build instance before consuming the sdist."""
    binding = context.binding
    provisioning = {
        "run_id": context.run_id,
        "run_attempt": context.run_attempt,
        "instance": key,
        "operation": "uv-sync-locked-no-install-project",
        "environment": record,
    }
    packages = record["packages"]
    value = {
        "schema_version": 1,
        "source_commit": binding.source_commit,
        "source_tree": binding.source_tree,
        "binding_sha256": digest(asdict(binding)),
        "sdist_name": binding.sdist_name,
        "sdist_size": binding.sdist_size,
        "sdist_sha256": binding.sdist_sha256,
        "build_lock_sha256": selected.lock_sha256,
        "provisioning_recipe_sha256": context.recipe_sha256,
        "provisioning_evidence_sha256": digest(provisioning),
        "uv_version": record["uv_version"],
        "uv_sha256": selected.uv_sha256,
        "target_os": record["target_os"],
        "target_architecture": record["target_architecture"],
        "python_implementation": "CPython",
        "python_version": record["python_version"],
        "python_executable_sha256": selected.python_sha256,
        "packages": packages,
        "packages_sha256": digest(packages),
    }
    raw = canonical(value)
    BuildEnvironmentDescriptor.from_bytes(raw)
    descriptor = output / "build-environment.json"
    with descriptor.open("xb") as stream:
        stream.write(raw)
    with (output / "provisioning-evidence.json").open("xb") as stream:
        stream.write(canonical(provisioning))
    return descriptor, hashlib.sha256(raw).hexdigest()


def run_row(
    context: MatrixContext,
    source: Path,
    dist: Path,
    runtime_python: Path,
    build_python: Path,
    uv: Path,
    minor: str,
    kind: Literal["wheel", "sdist"],
    work: Path,
    report_path: Path,
) -> dict[str, Any]:
    """Consume preprovisioned environments; execute no user graph or dependency resolver."""
    _require(
        minor in ("3.12", "3.13") and kind in ("wheel", "sdist"), "Invalid alpha row selection."
    )
    bundle.verify_handoff(dist, dist / "SHA256SUMS", context.binding, policy=POLICY)
    system, architecture = sdist_build._native_marker_target()
    expected = (system, architecture, minor, kind)
    _require(expected in ROWS, "Worker is outside the alpha native matrix.")
    key = "-".join(expected)
    _require(not work.exists() and not work.is_symlink(), "Alpha row work root must be fresh.")
    work.mkdir(mode=0o700)
    _environment, _site, version, os_name, machine = installed._selected_environment(runtime_python)
    implementation_status, implementation_bytes, _stderr = installed._run_bounded(
        [
            str(runtime_python),
            "-I",
            "-S",
            "-c",
            "import platform; print(platform.python_implementation())",
        ],
        cwd=work,
        timeout=30,
    )
    implementation = implementation_bytes.decode("ascii").strip()
    _require(
        implementation_status == 0 and implementation == "CPython",
        "Runtime must be measured CPython.",
    )
    _require(
        re.fullmatch(re.escape(minor) + r"\.[0-9]+", version) is not None,
        "Runtime Python differs from selected minor.",
    )
    python_sha = sdist_build._sha256_file(runtime_python.resolve(strict=True))
    runtime = {
        "implementation": implementation,
        "version": version,
        "system": system,
        "architecture": architecture,
        "executable_sha256": python_sha,
    }
    binding = context.binding
    original = dist / (binding.wheel_name if kind == "wheel" else binding.sdist_name)
    install_wheel = original
    build: dict[str, Any] | None = None
    if kind == "sdist":
        _require(
            runtime_python.parent.parent.resolve() != build_python.parent.parent.resolve(),
            "Runtime and build environments must be separate.",
        )
        selected, record = locked_build_selection(source, build_python, uv)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        _require(
            not report_path.parent.is_symlink(), "Row evidence directory must not be a symlink."
        )
        descriptor, descriptor_sha = _descriptor(context, selected, record, key, report_path.parent)
        wheel_output = work / "temporary-wheel"
        wheel_output.mkdir(mode=0o700)
        receipt = sdist_build.prepare_sdist_build(
            original,
            binding,
            source,
            build_python,
            selected.uv,
            selected.uv_sha256,
            wheel_output,
            environment_descriptor=descriptor,
            expected_build_environment_sha256=descriptor_sha,
            policy=POLICY,
        )
        build = {
            **receipt.to_dict(),
            "instance": key,
            "environment_descriptor": read_document(descriptor),
            "provisioning_evidence": read_document(
                descriptor.parent / "provisioning-evidence.json"
            ),
        }
        _verify_build(context, build, key, system, architecture)
        install_wheel = wheel_output / binding.wheel_name
        _require(
            bundle._archive_sha256(install_wheel) == (receipt.wheel_size, receipt.wheel_sha256),
            "Temporary wheel differs from its build receipt.",
        )
    result = sdist_build._run_bounded(
        [
            str(uv),
            "pip",
            "install",
            "--no-config",
            "--offline",
            "--no-deps",
            "--no-python-downloads",
            "--python",
            str(runtime_python),
            str(install_wheel),
        ],
        timeout=120,
        capture=True,
    )
    _require(
        result.returncode == 0,
        "Could not install the authenticated candidate without dependencies.",
    )
    installed_receipt = installed.verify_installed(
        runtime_python, binding, source, kind, artifact=original, policy=POLICY
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    _require(
        not report_path.exists() and not report_path.is_symlink(),
        "Operational report must be fresh.",
    )
    with tempfile.TemporaryDirectory(prefix="alpha-installed-cwd-", dir=work) as isolated:
        result = sdist_build._run_bounded(
            [
                str(runtime_python),
                "-I",
                "-B",
                "-m",
                "matryca_plumber.graph_gateway.tck",
                "--report",
                str(report_path),
            ],
            cwd=Path(isolated),
            timeout=900,
            capture=True,
        )
    sys.stdout.buffer.write(result.stdout)
    _require(
        result.returncode == 0, "Installed operational TCK failed; retain its complete report."
    )
    report = read_document(report_path)
    _require(
        sdist_build._sha256_file(runtime_python.resolve(strict=True)) == python_sha,
        "Runtime executable changed during qualification.",
    )
    _require(
        installed_receipt.operating_system == os_name and installed_receipt.architecture == machine,
        "Runtime platform identity changed.",
    )
    bundle.verify_handoff(dist, dist / "SHA256SUMS", binding, policy=POLICY)
    row = document(
        canonical(
            {
                "schema_version": 1,
                "row": key,
                "run_id": context.run_id,
                "run_attempt": context.run_attempt,
                "binding_sha256": digest(asdict(binding)),
                "inputs_sha256": context.inputs_sha256,
                "job_name": row_job_name(system, architecture, minor),
                "status": "pass",
                "qualification": "unqualified",
                "cleanup": "verified",
                "runtime": runtime,
                "installed": installed_receipt.to_dict(),
                "operational": report,
                "build": build,
            }
        )
    )
    verify_row(context, row, expected)
    return row


def source_selectors(context: MatrixContext) -> list[str]:
    """Flatten the exact versioned source-unit control map, preserving unique selectors."""
    selectors = []
    for value in context.source_controls.values():
        for selector in [value] if isinstance(value, str) else value:
            _require(
                isinstance(selector, str)
                and re.fullmatch(
                    r"tests/test_[a-z0-9_]+\.py::test_[A-Za-z0-9_]+(?:\[[A-Za-z0-9_-]+\])?",
                    selector,
                )
                is not None,
                "Invalid source-control selector.",
            )
            if selector not in selectors:
                selectors.append(selector)
    _require(bool(selectors), "Source control map is empty.")
    return selectors


def run_source_controls(
    context: MatrixContext, source: Path, python: Path, work: Path, report: Path
) -> dict[str, Any]:
    """Use ordinary pytest and JUnit, not a private execution observer."""
    _require(not work.exists() and not work.is_symlink(), "Source-control output must be fresh.")
    work.mkdir(mode=0o700)
    selectors = source_selectors(context)
    report.parent.mkdir(parents=True, exist_ok=True)
    _require(not report.exists() and not report.is_symlink(), "Source JUnit must be fresh.")
    result = sdist_build._run_bounded(
        [
            str(python),
            "-B",
            "-m",
            "pytest",
            "-q",
            "-o",
            "addopts=",
            "--junitxml",
            str(report),
            "--basetemp",
            str(work / "pytest"),
            *selectors,
        ],
        cwd=source,
        timeout=900,
        capture=True,
    )
    sys.stdout.buffer.write(result.stdout)
    _require(result.returncode == 0, "Exact-source controls failed.")
    _require(
        report.is_file() and not report.is_symlink() and report.stat().st_size <= 262_144,
        "Missing bounded source JUnit evidence.",
    )
    raw = report.read_bytes()
    _require(
        b"<!DOCTYPE" not in raw and b"<!ENTITY" not in raw,
        "Source JUnit must not declare entities.",
    )
    tree = ET.fromstring(raw)
    cases = tree.findall(".//testcase")
    _require(
        len(cases) >= len(selectors) and all(not list(case) for case in cases),
        "A required source control failed, skipped or was not executed.",
    )
    identities = {(case.get("classname"), case.get("name")) for case in cases}
    _require(len(identities) == len(cases), "Duplicate source control cases.")
    for selector in selectors:
        file, name = selector.split("::")
        classname = file[:-3].replace("/", ".")
        _require(
            any(
                cls == classname
                and observed is not None
                and (observed == name or ("[" not in name and observed.startswith(name + "[")))
                for cls, observed in identities
            ),
            "Source control selector missing from actual JUnit cases.",
        )
    return {
        "source_commit": context.binding.source_commit,
        "source_tree": context.binding.source_tree,
        "run_id": context.run_id,
        "run_attempt": context.run_attempt,
        "selectors": context.source_controls,
        "status": "pass",
        "qualification": "source-only",
        "junit_sha256": hashlib.sha256(raw).hexdigest(),
        "cases": len(cases),
    }


def run_windows_refusal(
    source: Path, python: Path, run_id: str, run_attempt: int
) -> dict[str, Any]:
    """Native refusal probe; audit graph access before loading the source bootstrap."""
    _require(
        platform.system() == "Windows" and platform.machine() == "AMD64",
        "Windows refusal requires a native x64 runner.",
    )
    script = """import json,os,runpy,sys
accesses=[]
forbidden=os.path.abspath('never-open-synthetic-graph')
def audit(event,args):
    if (event in ('open','os.listdir','os.scandir') and args
            and isinstance(args[0],(str,bytes,os.PathLike))):
        if os.path.abspath(os.fsdecode(args[0])).startswith(forbidden):
            accesses.append(event)
            raise RuntimeError('graph access before platform refusal')
sys.addaudithook(audit)
namespace=runpy.run_path(sys.argv[1],run_name='alpha_refusal_bootstrap')
code=namespace['main'](['snapshot','--graph-root',forbidden,'--expect-descriptor-sha256','0'*64])
print(json.dumps({'exit_code':code,'graph_accesses':len(accesses)},separators=(',',':')))
"""
    code, stdout, stderr = installed._run_bounded(
        [
            str(python),
            "-I",
            "-B",
            "-c",
            script,
            str(source / "matryca_plumber/graph_gateway/bootstrap.py"),
        ],
        cwd=source,
        timeout=30,
        output_limit=4096,
    )
    probe = document(stdout)
    _require(
        code == 0
        and probe == {"exit_code": 7, "graph_accesses": 0}
        and stderr == b'{"error":"unsupported_platform"}\n',
        "Windows did not refuse before graph access.",
    )
    return {
        "source_commit": bundle._git_value(source, "HEAD"),
        "source_tree": bundle._git_value(source, "HEAD^{tree}"),
        "run_id": run_id,
        "run_attempt": run_attempt,
        "system": "Windows",
        "architecture": "AMD64",
        "status": "pass",
        "qualification": "refusal-only",
        "exit_code": 7,
        "error": "unsupported_platform",
        "graph_accesses": 0,
    }


def verify_artifacts(
    context: MatrixContext,
    expected: dict[str, Any],
    artifacts: list[dict[str, Any]],
    *,
    public_input: bool = False,
) -> dict[str, dict[str, Any]]:
    """Bind downloaded artifacts to independently carried upstream outputs and REST metadata."""
    keys = ("admission", *ARTIFACT_KEYS[1:]) if public_input else ARTIFACT_KEYS
    _require(set(expected) == set(keys), "Incomplete upstream artifact bindings.")
    family = "og-public" if public_input else "og-alpha"
    prefix = f"{family}-{context.run_id}-{context.run_attempt}-"
    selected = [
        item
        for item in artifacts
        if isinstance(item.get("name"), str) and item["name"].startswith(prefix)
    ]
    _require(len(selected) == len(ARTIFACT_KEYS), "Missing or extra current-attempt artifacts.")
    output: dict[str, dict[str, Any]] = {}
    for key in keys:
        binding = expected[key]
        _require(
            isinstance(binding, dict)
            and set(binding) == {"id", "sha256"}
            and isinstance(binding["id"], str)
            and re.fullmatch(r"[1-9][0-9]*", binding["id"]) is not None
            and _digest_value(binding["sha256"]),
            "Malformed independently expected artifact identity.",
        )
        matches = [item for item in selected if item["name"] == prefix + key]
        _require(len(matches) == 1, "Duplicate or absent artifact name.")
        item = matches[0]
        run = item.get("workflow_run", {})
        _require(
            type(item.get("id")) is int
            and str(item["id"]) == binding["id"]
            and item.get("digest") == "sha256:" + binding["sha256"]
            and item.get("expired") is False
            and type(run.get("id")) is int
            and str(run["id"]) == context.run_id
            and run.get("head_sha") == context.binding.source_commit,
            "Artifact ID, digest, run or source identity mismatch.",
        )
        output[key] = item
    _require(
        len({item["id"] for item in output.values()}) == len(ARTIFACT_KEYS),
        "Reused upstream artifact ID.",
    )
    return output


def verify_canonical_build(context: MatrixContext, build: dict[str, Any]) -> None:
    """Authenticate publisher build identities before any installed consumer runs."""
    for key, value in {
        "source_commit": context.binding.source_commit,
        "source_tree": context.binding.source_tree,
        "binding_sha256": digest(asdict(context.binding)),
        "build_lock_sha256": context.build_lock_sha256,
        "python_implementation": "CPython",
        "uv_version": "0.12.19",
        "target_os": "linux",
        "target_architecture": "x64",
        "packages": [
            {"name": name, "version": version} for name, version in context.build_packages
        ],
    }.items():
        _require(build.get(key) == value, "Canonical build environment mismatch.")
    _require(
        isinstance(build.get("python_version"), str)
        and re.fullmatch(r"3\.12\.[0-9]+", build["python_version"]) is not None
        and _digest_value(build.get("python_executable_sha256"))
        and _digest_value(build.get("uv_sha256")),
        "Canonical build interpreter identity is incomplete.",
    )
    _require(
        isinstance(build.get("node_version"), str)
        and re.fullmatch(r"v22\.[0-9]+\.[0-9]+", build["node_version"]) is not None
        and isinstance(build.get("npm_version"), str)
        and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", build["npm_version"]) is not None,
        "Canonical frontend tool identity is incomplete.",
    )


def aggregate_downloads(
    context: MatrixContext,
    downloads: Path,
    jobs: dict[str, Any],
    artifacts: dict[str, Any],
    expected_artifacts: dict[str, Any],
    expected_build: dict[str, Any],
    *,
    expected_public: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose exact downloaded evidence only after job and artifact authentication."""
    _require(
        type(jobs.get("total_count")) is int
        and jobs["total_count"] == len(jobs.get("jobs", [])) <= 100,
        "Job metadata is incomplete or paginated.",
    )
    _require(
        type(artifacts.get("total_count")) is int
        and artifacts["total_count"] == len(artifacts.get("artifacts", [])) <= 100,
        "Artifact metadata is incomplete or paginated.",
    )
    public_input = expected_public is not None
    identities = verify_artifacts(
        context, expected_artifacts, artifacts["artifacts"], public_input=public_input
    )
    expected_names = {item["name"] for item in identities.values()}
    _require(
        downloads.is_dir()
        and not downloads.is_symlink()
        and {path.name for path in downloads.iterdir()} == expected_names,
        "Downloaded artifact inventory is incomplete or unexpected.",
    )
    paths = {key: downloads / item["name"] for key, item in identities.items()}
    _require(
        all(path.is_dir() and not path.is_symlink() for path in paths.values()),
        "Artifact directory is not regular.",
    )
    build_root = paths["admission" if public_input else "build"]
    _require(
        set(path.name for path in build_root.iterdir())
        == {"dist", "binding.json", "content-ledger.json", "canonical-build.json"}
        | ({"public-input.json", "public-provenance"} if public_input else set()),
        "Unexpected canonical build artifact files.",
    )
    _require(
        BundleBinding.from_json((build_root / "binding.json").read_text(), policy=POLICY)
        == context.binding,
        "Downloaded bundle binding differs from upstream output.",
    )
    bundle.verify_handoff(
        build_root / "dist", build_root / "dist/SHA256SUMS", context.binding, policy=POLICY
    )
    if expected_public is not None:
        from scripts.release_qualification.alpha1_public import verify_retained

        verify_retained(build_root, context, expected_public)
    build = read_document(build_root / "canonical-build.json")
    _require(
        build == expected_build,
        "Canonical build evidence differs from independent upstream output.",
    )
    verify_canonical_build(context, build)
    rows: list[dict[str, Any]] = []
    for key in ("linux312", "linux313", "macos312", "macos313"):
        path = paths[key]
        _require(
            {item.name for item in path.iterdir()}
            == {
                "wheel.json",
                "sdist.json",
                "wheel-operational.json",
                "sdist-operational.json",
                "build-environment.json",
                "provisioning-evidence.json",
            },
            "Missing or extra installed row files.",
        )
        for kind in ("wheel", "sdist"):
            row = read_document(path / f"{kind}.json")
            raw_report = read_document(path / f"{kind}-operational.json")
            _require(
                raw_report == row["operational"],
                "Retained full operational report differs from row evidence.",
            )
            if kind == "sdist":
                _require(
                    read_document(path / "build-environment.json")
                    == row["build"]["environment_descriptor"]
                    and read_document(path / "provisioning-evidence.json")
                    == row["build"]["provisioning_evidence"],
                    "Retained sdist provisioning differs from row evidence.",
                )
            rows.append(row)
    source = read_document(paths["source-controls"] / "source.json")
    _require(
        {path.name for path in paths["source-controls"].iterdir()} == {"source.json", "junit.xml"},
        "Unexpected source evidence files.",
    )
    junit = paths["source-controls"] / "junit.xml"
    _require(
        not junit.is_symlink() and junit.is_file() and junit.stat().st_size <= 262_144,
        "Invalid source JUnit evidence.",
    )
    _require(
        hashlib.sha256(junit.read_bytes()).hexdigest() == source.get("junit_sha256"),
        "Source JUnit digest mismatch.",
    )
    _require(
        {path.name for path in paths["windows-refusal"].iterdir()} == {"windows.json"},
        "Unexpected Windows refusal evidence files.",
    )
    windows = read_document(paths["windows-refusal"] / "windows.json")
    result = verify_matrix(context, rows, jobs["jobs"], source, windows, public_input=public_input)
    if expected_public is not None:
        result["public_input"] = expected_public
    result["artifact_bindings"] = expected_artifacts
    result["canonical_build"] = build
    return result
