#!/usr/bin/env python3
"""Build and verify one release package pair across a job handoff."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scripts.release_qualification.alpha1_matrix import MatrixContext

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_release_artifacts import build_release_artifacts
from scripts.release_qualification.build_environment import (
    load_expected_build_environment_bindings,
)
from scripts.release_qualification.bundle import (
    BundleBinding,
    build_binding,
    canonical_manifest,
    verify_handoff,
)
from scripts.release_qualification.focused import run_focused
from scripts.release_qualification.installed import verify_installed
from scripts.release_qualification.receipts import verify_receipts
from scripts.release_qualification.sdist_build import prepare_sdist_build


def _alpha_context(args: argparse.Namespace) -> object:
    from scripts.release_qualification.alpha1_matrix import source_context

    value = os.environ.get("EXPECTED_BINDING_JSON")
    if not value:
        raise ValueError("EXPECTED_BINDING_JSON is required for explicit alpha commands.")
    binding = BundleBinding.from_json(value, policy="og-alpha2")
    return source_context(
        args.source_root.resolve(),
        binding,
        os.environ["GITHUB_RUN_ID"],
        int(os.environ["GITHUB_RUN_ATTEMPT"]),
    )


def _alpha_public_inputs(args: argparse.Namespace, context: MatrixContext, root: Path) -> bool:
    """Authenticate public originals before any installed or source-test execution."""
    from scripts.release_qualification.alpha1_matrix import document
    from scripts.release_qualification.alpha1_public import context_from_roots, verify_retained

    verifier_root = getattr(args, "verifier_root", None)
    if verifier_root is None:
        if os.environ.get("EXPECTED_PUBLIC_JSON"):
            raise ValueError("Public inputs require an explicit verifier checkout.")
        return False
    value = os.environ.get("EXPECTED_PUBLIC_JSON")
    if not value:
        raise ValueError("EXPECTED_PUBLIC_JSON is required for public execution.")
    verifier = context_from_roots(
        args.source_root, verifier_root, os.environ.get("PUBLICATION_RUN", "")
    )
    if (
        root.is_symlink()
        or root.resolve().is_relative_to(args.source_root.resolve())
        or root.resolve().is_relative_to(verifier_root.resolve())
    ):
        raise ValueError("Public bundle must be outside the two selected checkouts.")
    verify_retained(root, context, document(value.encode()), verifier=verifier)
    return True


def _alpha_build(args: argparse.Namespace) -> None:
    from scripts.release_qualification.alpha1_matrix import build_alpha, canonical

    output_path = Path(os.environ["GITHUB_OUTPUT"])
    _regular_file(output_path, "GITHUB_OUTPUT")
    root = args.dist_dir.parent
    source = args.source_root.resolve()
    if root.resolve().is_relative_to(source) or output_path.resolve().is_relative_to(
        root.resolve()
    ):
        raise ValueError(
            "Alpha build outputs must be outside source; GITHUB_OUTPUT must be outside the bundle."
        )
    root.mkdir(parents=True, exist_ok=True)
    binding, record = build_alpha(
        args.source_root.resolve(),
        args.dist_dir,
        root / "content-ledger.json",
        args.build_python,
        args.uv,
        args.expected_commit,
    )
    _write_new_file(
        args.dist_dir / "SHA256SUMS",
        canonical_manifest(binding, policy="og-alpha2"),
        "alpha manifest",
    )
    verify_handoff(args.dist_dir, args.dist_dir / "SHA256SUMS", binding, policy="og-alpha2")
    _write_new_file(root / "binding.json", binding.to_json().encode(), "alpha binding")
    _write_new_file(root / "canonical-build.json", canonical(record), "canonical build evidence")
    _append_output(output_path, binding.to_json())
    _append_output(output_path, canonical(record).decode(), field="build_json")


def _alpha_row(args: argparse.Namespace) -> None:
    from scripts.release_qualification.alpha1_matrix import MatrixContext, canonical, run_row

    context = _alpha_context(args)
    assert isinstance(context, MatrixContext)
    _alpha_public_inputs(args, context, args.dist_dir.parent)
    try:
        result = run_row(
            context,
            args.source_root.resolve(),
            args.dist_dir,
            args.python,
            args.build_python,
            args.uv,
            args.minor,
            args.kind,
            args.work,
            args.output.parent / f"{args.kind}-operational.json",
        )
    except BaseException as error:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            _write_new_file(
                args.output.parent / f"{args.kind}-failure.json",
                canonical(
                    {
                        "schema_version": 1,
                        "status": "fail",
                        "stage": "alpha-row",
                        "source_commit": context.binding.source_commit,
                        "source_tree": context.binding.source_tree,
                        "run_id": context.run_id,
                        "run_attempt": context.run_attempt,
                        "kind": args.kind,
                        "runtime_minor": args.minor,
                        "error_type": type(error).__name__,
                    }
                ),
                "alpha row failure",
            )
        except BaseException as retention_error:
            error.add_note("Alpha failure retention error: " + type(retention_error).__name__)
        raise
    _write_new_file(args.output, canonical(result), "alpha row")


def _alpha_source_controls(args: argparse.Namespace) -> None:
    from scripts.release_qualification.alpha1_matrix import (
        MatrixContext,
        canonical,
        run_source_controls,
    )

    context = _alpha_context(args)
    assert isinstance(context, MatrixContext)
    public_input = _alpha_public_inputs(args, context, args.dist_dir.parent)
    verify_handoff(args.dist_dir, args.dist_dir / "SHA256SUMS", context.binding, policy="og-alpha2")
    result = run_source_controls(
        context,
        args.source_root.resolve(),
        args.python,
        args.work,
        args.output.parent / "junit.xml",
        public_input=public_input,
    )
    _write_new_file(args.output, canonical(result), "source control evidence")


def _alpha_windows_refusal(args: argparse.Namespace) -> None:
    from scripts.release_qualification.alpha1_matrix import canonical, run_windows_refusal

    if getattr(args, "verifier_root", None) is not None:
        from scripts.release_qualification.alpha1_public import context_from_roots

        context_from_roots(
            args.source_root, args.verifier_root, os.environ.get("PUBLICATION_RUN", "")
        )

    if (
        subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=args.source_root, text=True
        ).strip()
        != args.expected_commit
    ):
        raise ValueError("Windows refusal source differs from selection.")
    result = run_windows_refusal(
        args.source_root.resolve(),
        args.python,
        os.environ["GITHUB_RUN_ID"],
        int(os.environ["GITHUB_RUN_ATTEMPT"]),
    )
    _write_new_file(args.output, canonical(result), "Windows refusal evidence")


def _alpha_aggregate(args: argparse.Namespace) -> None:
    from scripts.release_qualification.alpha1_matrix import (
        MatrixContext,
        aggregate_downloads,
        canonical,
        document,
        read_document,
    )

    context = _alpha_context(args)
    assert isinstance(context, MatrixContext)
    result = aggregate_downloads(
        context,
        args.receipt_dir,
        read_document(args.jobs),
        read_document(args.artifacts),
        document(os.environ["EXPECTED_ARTIFACTS_JSON"].encode()),
        document(os.environ["EXPECTED_BUILD_JSON"].encode()),
    )
    _write_new_file(args.output, canonical(result), "alpha aggregate")


def _alpha_public_fetch(args: argparse.Namespace) -> None:
    from scripts.release_qualification.alpha1_public import fetch_file

    fetch_file(args.url, args.output, args.size, args.sha256, args.kind)


def _alpha_public_admit(args: argparse.Namespace) -> None:
    from scripts.release_qualification.alpha1_matrix import canonical, read_document
    from scripts.release_qualification.alpha1_public import admit_public

    output = Path(os.environ["GITHUB_OUTPUT"])
    _regular_file(output, "GITHUB_OUTPUT")
    if output.resolve().is_relative_to(args.output.resolve()):
        raise ValueError("GITHUB_OUTPUT must be outside the public bundle.")
    record = admit_public(
        args.source_root, args.output, args.publication_run, verifier=args.verifier_root
    )
    binding = BundleBinding.from_json(
        (args.output / "binding.json").read_text(), policy="og-alpha2"
    )
    _append_output(output, binding.to_json())
    _append_output(
        output,
        canonical(read_document(args.output / "canonical-build.json")).decode(),
        field="build_json",
    )
    _append_output(output, canonical(record).decode(), field="public_json")


def _alpha_public_aggregate(args: argparse.Namespace) -> None:
    from scripts.release_qualification.alpha1_matrix import (
        MatrixContext,
        aggregate_downloads,
        canonical,
        document,
        read_document,
    )
    from scripts.release_qualification.alpha1_public import context_from_roots

    context = _alpha_context(args)
    assert isinstance(context, MatrixContext)
    verifier = context_from_roots(
        args.source_root, args.verifier_root, os.environ.get("PUBLICATION_RUN", "")
    )
    result = aggregate_downloads(
        context,
        args.receipt_dir,
        read_document(args.jobs),
        read_document(args.artifacts),
        document(os.environ["EXPECTED_ARTIFACTS_JSON"].encode()),
        document(os.environ["EXPECTED_BUILD_JSON"].encode()),
        expected_public=document(os.environ["EXPECTED_PUBLIC_JSON"].encode()),
        verifier=verifier,
    )
    _write_new_file(args.output, canonical(result), "public alpha aggregate")


def _regular_file(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} must be an existing regular file: {path}")


def _write_new_file(path: Path, payload: bytes, label: str) -> None:
    if path.exists() or path.is_symlink():
        raise ValueError(f"Refusing to overwrite existing {label}: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError(f"Could not write complete {label}.")
            view = view[written:]
    except BaseException:
        os.close(descriptor)
        path.unlink(missing_ok=True)
        raise
    os.close(descriptor)


def _append_output(path: Path, binding_json: str, *, field: str = "binding_json") -> None:
    if field not in ("binding_json", "build_json", "public_json"):
        raise ValueError("Unknown qualification output field.")
    _regular_file(path, "GITHUB_OUTPUT")
    descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0))
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("GITHUB_OUTPUT must be a regular file.")
        original_size = os.fstat(descriptor).st_size
        payload = f"{field}={binding_json}\n".encode()
        try:
            view = memoryview(payload)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise OSError("Could not write complete GITHUB_OUTPUT value.")
                view = view[written:]
        except BaseException:
            os.ftruncate(descriptor, original_size)
            raise
    finally:
        os.close(descriptor)


def _build_handoff(args: argparse.Namespace) -> None:
    output_value = os.environ.get("GITHUB_OUTPUT")
    if not output_value:
        raise ValueError("GITHUB_OUTPUT is required for build-handoff.")
    output_path = Path(output_value)
    _regular_file(output_path, "GITHUB_OUTPUT")
    output_resolved = output_path.resolve()
    dist_resolved = args.dist_dir.resolve()
    if output_resolved == dist_resolved or dist_resolved in output_resolved.parents:
        raise ValueError("GITHUB_OUTPUT must be outside the distribution directory.")
    if not re.fullmatch(r"[0-9a-f]{40}", args.expected_commit):
        raise ValueError("Expected source commit must be a lowercase full Git ID.")
    try:
        current_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=args.repo_root, text=True, stderr=subprocess.PIPE
        ).strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError("Could not resolve repository HEAD before package build.") from error
    if current_commit != args.expected_commit:
        raise ValueError("Repository HEAD does not match expected source commit.")

    build_release_artifacts(
        args.repo_root.resolve(),
        args.dist_dir,
        content_ledger_path=args.ledger,
    )
    binding = build_binding(
        args.repo_root.resolve(), args.dist_dir, args.ledger, args.expected_commit
    )
    manifest = args.dist_dir / "SHA256SUMS"
    _write_new_file(manifest, canonical_manifest(binding), "SHA256SUMS manifest")
    verify_handoff(args.dist_dir, manifest, binding)
    _append_output(output_path, binding.to_json())


def _verify_handoff(args: argparse.Namespace) -> None:
    value = os.environ.get("EXPECTED_BINDING_JSON")
    if not value:
        raise ValueError("EXPECTED_BINDING_JSON is required for verify-handoff.")
    expected = BundleBinding.from_json(value)
    verify_handoff(args.dist_dir, args.manifest, expected)


def _verify_installed(args: argparse.Namespace) -> None:
    value = os.environ.get("EXPECTED_BINDING_JSON")
    if not value:
        raise ValueError("EXPECTED_BINDING_JSON is required for verify-installed.")
    binding = BundleBinding.from_json(value)
    receipt = verify_installed(
        args.python, binding, args.source_root, args.kind, artifact=args.artifact
    )
    print(receipt.to_json())


def _run_focused(args: argparse.Namespace) -> None:
    receipt = run_focused(
        args.repo_root.resolve(),
        args.platform,
        args.source_commit,
    )
    print(json.dumps(receipt.to_dict(), sort_keys=True, separators=(",", ":")))


def _verify_receipts(args: argparse.Namespace) -> None:
    binding = BundleBinding.from_json(args.expected_binding)
    expected_build_environments = load_expected_build_environment_bindings(
        args.expected_build_environments
    )
    receipt = verify_receipts(
        args.receipt_dir,
        expected_commit=args.expected_commit,
        expected_tree=args.expected_tree,
        expected_binding=binding,
        expected_build_environments=expected_build_environments,
        artifact_id=args.artifact_id,
        artifact_digest=args.artifact_digest,
        run_id=args.run_id,
        expected_platform_count=args.expected_platform_count,
    )
    print(json.dumps(receipt.to_dict(), sort_keys=True, separators=(",", ":")))


def _prepare_sdist_build(args: argparse.Namespace) -> None:
    value = os.environ.get("EXPECTED_BINDING_JSON")
    if not value:
        raise ValueError("EXPECTED_BINDING_JSON is required for prepare-sdist-build.")
    binding = BundleBinding.from_json(value)
    receipt = prepare_sdist_build(
        args.artifact,
        binding,
        args.source_root,
        args.python,
        args.uv,
        args.uv_sha256,
        args.wheel_output,
        environment_descriptor=args.build_environment_descriptor,
        expected_build_environment_sha256=args.expected_build_environment_sha256,
    )
    print(receipt.to_json())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build-handoff", help="build, verify, and bind one archive pair")
    build.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    build.add_argument("--dist-dir", type=Path, required=True)
    build.add_argument("--ledger", type=Path, required=True)
    build.add_argument("--expected-commit", required=True)
    build.set_defaults(handler=_build_handoff)

    verify = commands.add_parser("verify-handoff", help="verify downloaded bytes before install")
    verify.add_argument("--dist-dir", type=Path, required=True)
    verify.add_argument("--manifest", type=Path, required=True)
    verify.set_defaults(handler=_verify_handoff)

    installed = commands.add_parser(
        "verify-installed", help="verify one exact release distribution after installation"
    )
    installed.add_argument("--python", type=Path, required=True)
    installed.add_argument("--source-root", type=Path, required=True)
    installed.add_argument("--artifact", type=Path, required=True)
    installed.add_argument("--kind", choices=("wheel", "sdist"), required=True)
    installed.set_defaults(handler=_verify_installed)

    focused = commands.add_parser(
        "run-focused", help="run the frozen source-bound platform test selection"
    )
    focused.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    focused.add_argument("--platform", choices=("linux", "macos", "windows"), required=True)
    focused.add_argument("--source-commit", required=True)
    focused.set_defaults(handler=_run_focused)

    receipts = commands.add_parser(
        "verify-receipts",
        help="verify three platform receipts against independent build-environment bindings",
    )
    receipts.add_argument("--receipt-dir", type=Path, required=True)
    receipts.add_argument("--expected-commit", required=True)
    receipts.add_argument("--expected-tree", required=True)
    receipts.add_argument("--expected-binding", required=True)
    receipts.add_argument(
        "--expected-build-environments",
        type=Path,
        required=True,
        help=(
            "separate caller-authenticated three-target expectations for build-lock, recipe, "
            "descriptor, and provisioning-evidence digests; never inferred from receipts"
        ),
    )
    receipts.add_argument("--artifact-id", required=True)
    receipts.add_argument("--artifact-digest", required=True)
    receipts.add_argument("--run-id", required=True)
    receipts.add_argument("--expected-platform-count", type=int, default=3)
    receipts.set_defaults(handler=_verify_receipts)

    sdist_build = commands.add_parser(
        "prepare-sdist-build",
        help=(
            "verify the original sdist and four equal package manifests, then build one temporary "
            "wheel in an already-provisioned, separately locked CPython 3.12 environment"
        ),
    )
    sdist_build.add_argument(
        "--artifact",
        type=Path,
        required=True,
        help="bound original sdist; temporary wheel must not replace this verifier input",
    )
    sdist_build.add_argument("--source-root", type=Path, required=True)
    sdist_build.add_argument(
        "--python",
        type=Path,
        required=True,
        help=(
            "CPython 3.12 interpreter in the caller-provisioned environment; no creation, "
            "resolution, install, sync, or repair"
        ),
    )
    sdist_build.add_argument("--uv", type=Path, required=True)
    sdist_build.add_argument("--uv-sha256", required=True)
    sdist_build.add_argument(
        "--wheel-output",
        type=Path,
        required=True,
        help="private temporary-wheel destination outside canonical dist",
    )
    sdist_build.add_argument(
        "--build-environment-descriptor",
        type=Path,
        required=True,
        help=("caller-provisioned descriptor; authenticate it and bind its digest separately"),
    )
    sdist_build.add_argument(
        "--expected-build-environment-sha256",
        required=True,
        help="independently caller-bound descriptor SHA-256; never derived from descriptor bytes",
    )
    sdist_build.set_defaults(handler=_prepare_sdist_build)

    alpha_build = commands.add_parser(
        "alpha-build", help="build only the exact experimental OG alpha"
    )
    alpha_build.add_argument("--source-root", type=Path, required=True)
    alpha_build.add_argument("--dist-dir", type=Path, required=True)
    alpha_build.add_argument("--expected-commit", required=True)
    alpha_build.add_argument("--build-python", type=Path, required=True)
    alpha_build.add_argument("--uv", type=Path, required=True)
    alpha_build.set_defaults(handler=_alpha_build)

    alpha_row = commands.add_parser(
        "alpha-row", help="verify an original wheel or sdist installed alpha row"
    )
    for name in ("source-root", "dist-dir", "python", "build-python", "uv", "work", "output"):
        alpha_row.add_argument("--" + name, type=Path, required=True)
    alpha_row.add_argument("--kind", choices=("wheel", "sdist"), required=True)
    alpha_row.add_argument("--minor", choices=("3.12", "3.13"), required=True)
    alpha_row.add_argument("--verifier-root", type=Path)
    alpha_row.set_defaults(handler=_alpha_row)

    alpha_source = commands.add_parser(
        "alpha-source-controls", help="run the separately mapped exact-source controls"
    )
    for name in ("source-root", "dist-dir", "python", "work", "output"):
        alpha_source.add_argument("--" + name, type=Path, required=True)
    alpha_source.add_argument("--verifier-root", type=Path)
    alpha_source.set_defaults(handler=_alpha_source_controls)

    alpha_windows = commands.add_parser(
        "alpha-windows-refusal", help="native Windows refusal only, not installed qualification"
    )
    for name in ("source-root", "python", "output"):
        alpha_windows.add_argument("--" + name, type=Path, required=True)
    alpha_windows.add_argument("--expected-commit", required=True)
    alpha_windows.add_argument("--verifier-root", type=Path)
    alpha_windows.set_defaults(handler=_alpha_windows_refusal)

    alpha_aggregate = commands.add_parser(
        "alpha-aggregate", help="authenticate all eight alpha rows and actual upstream jobs"
    )
    for name in ("source-root", "receipt-dir", "jobs", "artifacts", "output"):
        alpha_aggregate.add_argument("--" + name, type=Path, required=True)
    alpha_aggregate.set_defaults(handler=_alpha_aggregate)

    public_fetch = commands.add_parser(
        "alpha-public-fetch", help="one bounded public byte acquisition"
    )
    public_fetch.add_argument("--url", required=True)
    public_fetch.add_argument("--output", type=Path, required=True)
    public_fetch.add_argument("--size", type=int, required=True)
    public_fetch.add_argument("--sha256", required=True)
    public_fetch.add_argument("--kind", choices=("github", "pypi", "pypi-metadata"), required=True)
    public_fetch.set_defaults(handler=_alpha_public_fetch)

    public_admit = commands.add_parser(
        "alpha-public-admit", help="admit the exact public alpha from a distinct publication run"
    )
    public_admit.add_argument("--source-root", type=Path, required=True)
    public_admit.add_argument("--output", type=Path, required=True)
    public_admit.add_argument("--publication-run", required=True)
    public_admit.add_argument("--verifier-root", type=Path, required=True)
    public_admit.set_defaults(handler=_alpha_public_admit)

    public_aggregate = commands.add_parser(
        "alpha-public-aggregate",
        help="authenticate actual public-input jobs without rewriting diagnostic metadata",
    )
    for name in ("source-root", "receipt-dir", "jobs", "artifacts", "output"):
        public_aggregate.add_argument("--" + name, type=Path, required=True)
    public_aggregate.add_argument("--verifier-root", type=Path, required=True)
    public_aggregate.set_defaults(handler=_alpha_public_aggregate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        args.handler(args)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    sys.exit(main())
