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

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_release_artifacts import build_release_artifacts
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


def _append_output(path: Path, binding_json: str) -> None:
    _regular_file(path, "GITHUB_OUTPUT")
    descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0))
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("GITHUB_OUTPUT must be a regular file.")
        original_size = os.fstat(descriptor).st_size
        payload = f"binding_json={binding_json}\n".encode()
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
    receipt = verify_receipts(
        args.receipt_dir,
        expected_commit=args.expected_commit,
        expected_tree=args.expected_tree,
        expected_binding=binding,
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
        "verify-receipts", help="verify exactly three bound platform qualification receipts"
    )
    receipts.add_argument("--receipt-dir", type=Path, required=True)
    receipts.add_argument("--expected-commit", required=True)
    receipts.add_argument("--expected-tree", required=True)
    receipts.add_argument("--expected-binding", required=True)
    receipts.add_argument("--artifact-id", required=True)
    receipts.add_argument("--artifact-digest", required=True)
    receipts.add_argument("--run-id", required=True)
    receipts.add_argument("--expected-platform-count", type=int, default=3)
    receipts.set_defaults(handler=_verify_receipts)

    sdist_build = commands.add_parser(
        "prepare-sdist-build",
        help="build a temporary wheel from the bound sdist in a private PEP 517 environment",
    )
    sdist_build.add_argument("--artifact", type=Path, required=True)
    sdist_build.add_argument("--source-root", type=Path, required=True)
    sdist_build.add_argument("--python", type=Path, required=True)
    sdist_build.add_argument("--uv", type=Path, required=True)
    sdist_build.add_argument("--uv-sha256", required=True)
    sdist_build.add_argument("--wheel-output", type=Path, required=True)
    sdist_build.set_defaults(handler=_prepare_sdist_build)

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
