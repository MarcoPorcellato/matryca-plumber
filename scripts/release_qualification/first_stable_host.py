"""Provision and probe one pinned, native first-stable CPython runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path

from scripts.release_qualification.first_stable_runtime import extract_runtime
from scripts.release_qualification.process import start_process

_RELEASE = "20261110"


@dataclass(frozen=True, slots=True)
class RuntimePin:
    triple: str
    size: int
    sha256: str

    def filename(self, version: str) -> str:
        return f"cpython-{version}+{_RELEASE}-{self.triple}-install_only.tar.gz"


_LINUX = "x86_64-unknown-linux-gnu"
_MACOS = "aarch64-apple-darwin"
PINS = {
    ("linux-x86_64", "3.12.16"): RuntimePin(
        _LINUX, 68163679, "c2f87d4b4e8db3abddb0f116c6ccfc503d0cbdbb9ee8faacddad1b679ec12e99"
    ),
    ("linux-x86_64", "3.13.18"): RuntimePin(
        _LINUX, 77155083, "50c774f6674740739f791c05a9177ed03e2fe02abebda9bca3512eb7309b37cc"
    ),
    ("macos-arm64", "3.12.16"): RuntimePin(
        _MACOS, 25371130, "e956e60bc9465d577ef8062059aa05cd3a2665b4b8678a2ed24e432368330b8f"
    ),
    ("macos-arm64", "3.13.18"): RuntimePin(
        _MACOS, 25598083, "1afd3983237c2a10277345f235be730e9cb49a123e0574ed252dbf3a841a24e4"
    ),
}
HOSTS = {"linux-x86_64": ("Linux", "x86_64"), "macos-arm64": ("Darwin", "arm64")}
_ENV = {"PATH": "/usr/bin:/bin", "LC_ALL": "C"}
_PROBE = """
import bz2, ctypes, json, lzma, os, platform, sqlite3, ssl, sys, zlib
print(json.dumps(dict(implementation=platform.python_implementation(),
    version=platform.python_version(), system=platform.system(), machine=platform.machine(),
    executable=os.path.realpath(sys.executable), prefix=os.path.realpath(sys.base_prefix))))
"""


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _run_owned(argv: list[str], cwd: Path, stdout: Path, stderr: Path, timeout: int) -> None:
    with stdout.open("xb") as captured, stderr.open("xb") as errors:
        owner = start_process(
            argv,
            cwd=cwd,
            env=_ENV,
            stdin=subprocess.DEVNULL,
            stdout=captured,
            stderr=errors,
            windows=False,
        )
        try:
            code = owner.process.wait(timeout=timeout)
            if owner.group_exists():
                raise ValueError("Native input process group remains after child exit.")
        except BaseException as error:
            try:
                owner.terminate(grace_seconds=0)
            except BaseException as cleanup:
                error.add_note(f"Process-group cleanup failed: {type(cleanup).__name__}")
            try:
                owner.reap_and_dispose_handle(timeout=5)
            except BaseException as reap:
                error.add_note(f"Direct child reap failed: {type(reap).__name__}")
            raise
        if code != 0 or stderr.stat().st_size:
            raise ValueError("Native input operation was not clean; evidence retained.")


def probe(executable: Path, root: Path, version: str, target: str) -> dict[str, object]:
    """Verify native loader, interpreter identity and owned terminal exit."""
    import resource

    native = HOSTS[target]
    if (platform.system(), platform.machine()) != native:
        raise ValueError("Runner kernel and machine do not match the selected native target.")
    prefix = executable.parent.parent
    if executable.is_symlink() or not executable.is_file() or root not in executable.parents:
        raise ValueError("Native executable is outside the owned task root.")
    executable_sha256 = _digest(executable)
    old_soft, old_hard = resource.getrlimit(resource.RLIMIT_FSIZE)
    if old_hard != resource.RLIM_INFINITY and old_hard < 8192:
        raise ValueError("Native probe cannot enforce its output envelope.")
    resource.setrlimit(resource.RLIMIT_FSIZE, (8192, old_hard))
    stdout, stderr = root / "startup.stdout", root / "startup.stderr"
    try:
        _run_owned([str(executable), "-I", "-S", "-B", "-c", _PROBE], root, stdout, stderr, 15)
    finally:
        resource.setrlimit(resource.RLIMIT_FSIZE, (old_soft, old_hard))
    expected = {
        "implementation": "CPython",
        "version": version,
        "system": native[0],
        "machine": native[1],
        "executable": str(executable),
        "prefix": str(prefix),
    }
    if (
        not 0 < stdout.stat().st_size < 8192
        or json.loads(stdout.read_bytes()) != expected
        or _digest(executable) != executable_sha256
    ):
        raise ValueError("Native interpreter observation differs from expectation.")
    return {
        "implementation": "CPython",
        "version": version,
        "platform": target,
        "executable_sha256": executable_sha256,
        "cleanup": "verified",
    }


def provision(target: str, version: str, root: Path, archive: Path | None = None) -> Path:
    """Prepare the exact archive once; a smoke receipt is not a qualification row."""
    pin = PINS[target, version]
    if (platform.system(), platform.machine()) != HOSTS[target]:
        raise ValueError("Native runner platform mismatch.")
    if not root.is_absolute() or root.parent.resolve(strict=True) != root.parent:
        raise ValueError("Runtime work parent must be canonical and task-owned.")
    root.mkdir(mode=0o700)
    if target == "linux-x86_64":
        (root / "case-test").mkdir()
        (root / "CASE-TEST").mkdir()
    if archive is None:
        filename = pin.filename(version)
        archive = root / filename
        url = f"https://github.com/astral-sh/python-build-standalone/releases/download/{_RELEASE}/{filename}"
        _run_owned(
            [
                "/usr/bin/curl",
                "--disable",
                "--noproxy",
                "*",
                "--proto",
                "=https",
                "--proto-redir",
                "=https",
                "--location",
                "--max-redirs",
                "1",
                "--fail",
                "--silent",
                "--show-error",
                "--max-time",
                "90",
                "--max-filesize",
                str(pin.size),
                "--output",
                str(archive),
                url,
            ],
            root,
            root / "acquire.stdout",
            root / "acquire.stderr",
            95,
        )
    executable = extract_runtime(
        archive,
        root / "runtime",
        version,
        pin.size,
        pin.sha256,
        case_sensitive=target == "linux-x86_64",
    )
    receipt = probe(executable, root, version, target)
    receipt["archive_sha256"] = pin.sha256
    with (root / "startup.json").open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, sort_keys=True, separators=(",", ":"))
    return executable


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("platform", choices=tuple(HOSTS))
    parser.add_argument("version", choices=("3.12.16", "3.13.18"))
    parser.add_argument("root", type=Path)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    print(provision(args.platform, args.version, args.root, args.archive))


if __name__ == "__main__":
    main()
