"""Run the ordinary canonical build and exact installed qualification rows."""

from __future__ import annotations

import argparse
import hashlib
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from scripts.release_qualification import bundle, sdist_build
from scripts.release_qualification.alpha1_matrix import (
    build_alpha,
    canonical,
    digest,
    locked_build_selection,
    read_document,
)
from scripts.release_qualification.build_environment import BuildEnvironmentDescriptor
from scripts.release_qualification.first_stable_admission import (
    require_ordinary_admission as require_ordinary_admission,
)
from scripts.release_qualification.first_stable_host import PINS
from scripts.release_qualification.first_stable_installed import verify_and_write_installed_row
from scripts.release_qualification.first_stable_matrix import (
    FIRST_STABLE_ROWS,
    first_stable_release_route,
)
from scripts.release_qualification.first_stable_profiles import resolve_profile

_POLICY = "og-alpha3"  # Shared hardened archive format; not the experimental OG lane.
ROWS = {row.key: row for row in FIRST_STABLE_ROWS}


def _write(path: Path, data: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(data)


def _owned_command(command: list[str], work: Path, label: str, *, capture: bool = True) -> None:
    result = sdist_build._run_bounded(command, cwd=work, timeout=180, capture=capture)
    if result.returncode != 0:
        raise ValueError(f"{label} failed.")


def install_commands(
    uv: Path, python: Path, requirements: Path, wheel: Path
) -> tuple[list[str], list[str]]:
    """Separate hash-pinned dependencies from the offline authenticated candidate."""
    common = [
        str(uv),
        "pip",
        "install",
        "--no-config",
        "--no-python-downloads",
        "--no-deps",
        "--only-binary",
        ":all:",
        "--python",
        str(python),
    ]
    return (
        [
            *common,
            "--default-index",
            "https://pypi.org/simple",
            "--require-hashes",
            "--requirement",
            str(requirements),
        ],
        [*common, "--no-index", "--offline", str(wheel)],
    )


def read_export(path: Path, expected_sha256: str | None = None) -> str:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 1024 * 1024:
        raise ValueError("Locked export must be a bounded regular file.")
    with path.open("rb") as stream:
        data = stream.read(1024 * 1024 + 1)
    actual = hashlib.sha256(data).hexdigest()
    if len(data) > 1024 * 1024 or (expected_sha256 is not None and expected_sha256 != actual):
        raise ValueError("Locked export digest or size differs from expectations.")
    return data.decode("ascii")


def _selection() -> bundle.BundleBinding:
    binding = bundle.BundleBinding.from_json(os.environ["EXPECTED_BINDING_JSON"], policy=_POLICY)
    first_stable_release_route(os.environ["CANDIDATE_TAG"], binding.version)
    if (
        binding.source_commit != os.environ["SELECTED_SOURCE"]
        or binding.source_tree != os.environ["SELECTED_TREE"]
    ):
        raise ValueError("Build binding does not identify the independently selected checkout.")
    return binding


def build(source: Path, uv: Path, python: Path, output: Path) -> None:
    """Build one original artifact pair and export dependencies from clean source."""
    expected = os.environ["SELECTED_SOURCE"]
    tag = os.environ["CANDIDATE_TAG"]
    first_stable_release_route(tag, os.environ["SELECTED_VERSION"])
    output.mkdir(mode=0o700)
    exported = output / "runtime-lock.txt"
    _owned_command(
        [
            str(uv),
            "export",
            "--locked",
            "--no-config",
            "--no-dev",
            "--no-emit-project",
            "--no-emit-package",
            "logseq-matryca-parser",
            "--no-header",
            "--no-annotate",
            "--format",
            "requirements.txt",
            "--output-file",
            str(exported),
        ],
        source,
        "Locked runtime export",
        capture=False,
    )
    closure = read_export(exported)
    for row in FIRST_STABLE_ROWS:
        resolve_profile(closure, row.profile, row.platform, row.python)
    selected, record = build_alpha(
        source,
        output / "dist",
        output / "content-ledger.json",
        python,
        uv,
        expected,
        release_tag=tag,
    )
    if selected.source_tree != os.environ["SELECTED_TREE"] or record["python_version"] != "3.12.16":
        raise ValueError("Canonical build tree or builder Python differs from expectations.")
    _write(output / "dist" / "SHA256SUMS", bundle.canonical_manifest(selected, policy=_POLICY))
    _write(output / "binding.json", selected.to_json().encode())
    _write(output / "canonical-build.json", canonical(record))
    export_sha256 = hashlib.sha256(closure.encode("ascii")).hexdigest()
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as outputs:
        outputs.write(f"binding={selected.to_json()}\nexport-sha256={export_sha256}\n")


def _build_from_sdist(
    source: Path,
    uv: Path,
    builder: Path,
    originals: Path,
    binding: bundle.BundleBinding,
    work: Path,
    row_key: str,
) -> tuple[Path, dict[str, Any]]:
    selected, observed = locked_build_selection(source, builder, uv)
    if observed["python_version"] != "3.12.16":
        raise ValueError("Sdist must be built with the independently locked CPython 3.12.16.")
    provisioning = {
        "instance": row_key,
        "run_id": os.environ["GITHUB_RUN_ID"],
        "run_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]),
        "operation": "uv-sync-locked-no-install-project",
        "environment": observed,
    }
    descriptor_value = {
        **observed,
        "schema_version": 1,
        "source_commit": binding.source_commit,
        "source_tree": binding.source_tree,
        "binding_sha256": digest(asdict(binding)),
        "sdist_name": binding.sdist_name,
        "sdist_size": binding.sdist_size,
        "sdist_sha256": binding.sdist_sha256,
        "provisioning_recipe_sha256": sdist_build._locked_build_identity(source)[1],
        "provisioning_evidence_sha256": digest(provisioning),
        "packages_sha256": digest(observed["packages"]),
    }
    encoded = canonical(descriptor_value)
    BuildEnvironmentDescriptor.from_bytes(encoded)
    descriptor = work / "build-environment.json"
    _write(descriptor, encoded)
    wheel_output = work / "sdist-wheel"
    wheel_output.mkdir(mode=0o700)
    receipt = sdist_build.prepare_sdist_build(
        originals / binding.sdist_name,
        binding,
        source,
        builder,
        uv,
        selected.uv_sha256,
        wheel_output,
        environment_descriptor=descriptor,
        expected_build_environment_sha256=hashlib.sha256(encoded).hexdigest(),
        policy=_POLICY,
    )
    wheel = wheel_output / binding.wheel_name
    if bundle._archive_sha256(wheel) != (receipt.wheel_size, receipt.wheel_sha256):
        raise ValueError("Temporary wheel bytes differ from the sdist build receipt.")
    return wheel, {
        "receipt": receipt.to_dict(),
        "descriptor": descriptor_value,
        "provisioning": provisioning,
    }


def install_row(
    source: Path,
    uv: Path,
    runtime: Path,
    builder: Path | None,
    inputs: Path,
    work: Path,
    output: Path,
) -> None:
    """Install exact inputs and emit evidence only after terminal verification."""
    row = ROWS[os.environ["ROW_KEY"]]
    binding = _selection()
    originals = inputs / "dist"
    bundle.verify_handoff(originals, originals / "SHA256SUMS", binding, policy=_POLICY)
    export_sha256 = os.environ["EXPECTED_EXPORT_SHA256"]
    profile = resolve_profile(
        read_export(inputs / "runtime-lock.txt", export_sha256),
        row.profile,
        row.platform,
        row.python,
    )
    startup = read_document(runtime.parents[3] / "startup.json")
    runtime_sha = sdist_build._sha256_file(runtime)
    if startup != {
        "implementation": "CPython",
        "version": row.python,
        "platform": row.platform,
        "archive_sha256": PINS[row.platform, row.python].sha256,
        "executable_sha256": runtime_sha,
        "cleanup": "verified",
    }:
        raise ValueError("Runtime startup does not bind the selected interpreter and archive.")
    work.mkdir(mode=0o700)
    output.mkdir(mode=0o700)
    python = work / "installed/bin/python"
    _owned_command(
        [
            str(uv),
            "venv",
            "--no-config",
            "--no-python-downloads",
            "--python",
            str(runtime),
            str(python.parent.parent),
        ],
        work,
        "Isolated row environment",
    )
    if python.resolve(strict=True) != runtime:
        raise ValueError("Isolated environment did not use the exact admitted executable.")
    requirements = work / "requirements.txt"
    _write(requirements, profile.requirements.encode("ascii"))
    wheel = originals / binding.wheel_name
    build_record = None
    if row.distribution == "sdist":
        if builder is None:
            raise ValueError("Sdist row requires a separate locked builder environment.")
        build_record_wheel, build_record = _build_from_sdist(
            source,
            uv,
            builder,
            originals,
            binding,
            work,
            row.key,
        )
        wheel = build_record_wheel
    elif builder is not None:
        raise ValueError("Wheel row must not perform a build.")
    for command in install_commands(uv, python, requirements, wheel):
        _owned_command(command, work, "Bound installation")
    _owned_command(
        [str(uv), "pip", "check", "--no-config", "--no-python-downloads", "--python", str(python)],
        work,
        "Installed dependency consistency check",
    )
    verified = work / "installed.json"
    verify_and_write_installed_row(
        output=verified,
        row_key=row.key,
        candidate_tag=os.environ["CANDIDATE_TAG"],
        binding=binding,
        expected_dependencies=dict(profile.packages),
        installed_python=python,
        source_root=source,
        originals=originals,
    )
    bundle.verify_handoff(originals, originals / "SHA256SUMS", binding, policy=_POLICY)
    if sdist_build._sha256_file(runtime) != runtime_sha:
        raise ValueError("Native executable changed during qualification.")
    _write(
        output / "row.json",
        canonical(
            {
                "schema_version": 1,
                "run_id": int(os.environ["GITHUB_RUN_ID"]),
                "attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]),
                "binding_sha256": digest(asdict(binding)),
                "locked_export_sha256": export_sha256,
                "profile_sha256": hashlib.sha256(profile.requirements.encode("ascii")).hexdigest(),
                "runtime": startup,
                "build": build_record,
                "installed": read_document(verified),
            }
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("build", "row"))
    parser.add_argument("--uv", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--builder", type=Path)
    parser.add_argument("--runtime", type=Path)
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--work", type=Path)
    args = parser.parse_args()
    source = Path.cwd()
    if args.operation == "build" and args.builder is not None:
        build(source, args.uv, args.builder, args.output)
    elif (
        args.operation == "row"
        and args.runtime is not None
        and args.inputs is not None
        and args.work is not None
    ):
        install_row(
            source,
            args.uv,
            args.runtime,
            args.builder,
            args.inputs,
            args.work,
            args.output,
        )
    else:
        parser.error("Missing build or row inputs.")


if __name__ == "__main__":
    main()
