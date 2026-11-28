"""Qualify only the missing ordinary public RC1 installations on hosted POSIX."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Literal, cast

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from scripts.release_qualification import bundle, sdist_build
from scripts.release_qualification.alpha1_matrix import canonical, digest
from scripts.release_qualification.build_environment import BuildEnvironmentDescriptor
from scripts.release_qualification.first_stable_host import HOSTS, PINS
from scripts.release_qualification.first_stable_installed import verify_and_write_installed_row
from scripts.release_qualification.first_stable_job import (
    _build_from_sdist,
    install_commands,
    read_export,
)
from scripts.release_qualification.first_stable_profiles import resolve_profile
from scripts.release_qualification.first_stable_s3_inputs import (
    _RC_BINDING,
    BASELINES,
    RC_COMMIT,
    RC_PUBLISHER_RUN,
    RC_TAG_OBJECT,
    RC_TREE,
    TAG,
    AcquisitionCheckpoint,
    acquire_public,
    require_source,
    valid_acquisition_diagnostic,
)
from scripts.release_qualification.first_stable_s3_probe import FIXTURE
from scripts.release_qualification.installed import InstalledReceipt

_PYTHON = "3.12.16"
_RC = "2.1.0rc1"
_EXPORT = "1547eb0a8e3eae63b3063b6e7e91e5928d0e26a79b80f0f6b7a2fdf7b84ada5e"
_BUILDER_LOCK = "742a4abf69cdd39bada5b1ce8cd6169ce418c8f20b3527885826e7175b2c66b5"
_BUILDER_RECIPE = "7cf9b4f74bf76b7f59e46d2b29570613c28f8ad95949039db189ea1104521b1d"
_BUILDER_PACKAGES = [
    {"name": "packaging", "version": "26.3"},
    {"name": "setuptools", "version": "84.1.0"},
    {"name": "wheel", "version": "0.48.0"},
]
_CASES = {"clean-wheel": None, "clean-sdist": None, "from-stable": "2.0.0", "from-alpha": "2.1.0a4"}
_SHA = re.compile(r"[0-9a-f]{64}")
_FIXTURE_SHA = hashlib.sha256(FIXTURE).hexdigest()


def select_case(
    target: str, case: str, builder: Path | None, baseline_source: Path | None
) -> tuple[Literal["wheel", "sdist"], str | None]:
    """Reject any platform, case or auxiliary input outside the S3 follow-up."""
    if (
        case not in _CASES
        or target not in HOSTS
        or (target == "macos-arm64" and case != "clean-sdist")
    ):
        raise ValueError("Unselected S3 case or platform.")
    baseline = _CASES[case]
    kind: Literal["wheel", "sdist"] = "sdist" if case == "clean-sdist" else "wheel"
    if (builder is not None) != (kind == "sdist") or (baseline_source is not None) != (
        baseline is not None
    ):
        raise ValueError("S3 case has missing or extraneous inputs.")
    return kind, baseline


def historical_dependencies(export: str, target: str) -> dict[str, str]:
    """Project an exact historical export onto the admitted native runtime."""
    if not export or len(export) > 1024 * 1024 or not export.isascii() or target not in HOSTS:
        raise ValueError("Historical export or target is invalid.")
    system, machine = HOSTS[target]
    env = cast(dict[str, str], default_environment())
    env.update(
        implementation_name="cpython",
        implementation_version=_PYTHON,
        os_name="posix",
        platform_machine=machine,
        platform_python_implementation="CPython",
        platform_system=system,
        python_full_version=_PYTHON,
        python_version="3.12",
        sys_platform="linux" if system == "Linux" else "darwin",
    )
    result: dict[str, str] = {}
    for line in export.replace("\\\n", " ").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        raw, *hashes = re.split(r"[ \t]+--hash=", line.strip())
        req = Requirement(raw)
        sdist_build._reject_unbound_marker(raw)
        pins = list(req.specifier)
        name = canonicalize_name(req.name)
        if (
            req.url is not None
            or req.extras
            or len(pins) != 1
            or pins[0].operator != "=="
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.!+_-]{0,127}", pins[0].version) is None
            or name in {"matryca-plumber", "pip"}
            or not hashes
            or any(not re.fullmatch(r"sha256:[0-9a-f]{64}", h.strip()) for h in hashes)
        ):
            raise ValueError("Historical export has an unpinned or unexpected requirement.")
        if req.marker and not req.marker.evaluate(env):
            continue
        if name in result:
            raise ValueError("Duplicate historical requirement for this runtime.")
        result[name] = pins[0].version
    if not result:
        raise ValueError("Historical export is empty on this runtime.")
    return result


def require_restored_records(before: tuple[str, str], after: tuple[str, str]) -> None:
    """Require both baseline installed RECORD digests to be restored."""
    if before != after or any(_SHA.fullmatch(value) is None for value in before):
        raise ValueError("Rollback did not restore the Plumber and Parser RECORD digests.")


def _hash(path: Path) -> str:
    return sdist_build._sha256_file(path)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, sort_keys=True, separators=(",", ":"))
        stream.write("\n")


def _disk(root: Path) -> None:
    if shutil.disk_usage(root).free < 3 * 2**30:
        raise OSError("Disposable hosted S3 disk reserve unmet.")


def _admit_host(target: str, runtime: Path) -> dict[str, Any]:
    if (
        os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted"
        or os.environ.get("GITHUB_REPOSITORY") != "MarcoPorcellato/matryca-plumber"
        or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or os.environ.get("GITHUB_REF") != "refs/heads/main"
        or os.environ.get("GITHUB_REF_PROTECTED") != "true"
        or os.environ.get("GITHUB_WORKFLOW_SHA") != os.environ.get("GITHUB_SHA")
        or os.environ.get("GITHUB_RUN_ATTEMPT") != "1"
        or re.fullmatch(r"[1-9][0-9]*", os.environ.get("GITHUB_RUN_ID", "")) is None
        or re.fullmatch(r"[0-9a-f]{40}", os.environ.get("GITHUB_SHA", "")) is None
        or (platform.system(), platform.machine()) != HOSTS[target]
        or runtime.resolve(strict=True) != runtime
    ):
        raise ValueError("S3 requires the selected native hosted first attempt.")
    startup = runtime.parents[3] / "startup.json"
    expected = {
        "archive_sha256": PINS[target, _PYTHON].sha256,
        "implementation": "CPython",
        "platform": target,
        "version": _PYTHON,
        "executable_sha256": _hash(runtime),
        "cleanup": "verified",
    }
    if startup.is_symlink() or not startup.is_file() or startup.stat().st_size > 4096:
        raise ValueError("Native runtime startup receipt is missing or invalid.")
    if json.loads(startup.read_bytes()) != expected:
        raise ValueError("Native runtime startup receipt differs from the pinned runtime.")
    return expected


class Case:
    """Run bounded, sequential operations and keep only path-free observations."""

    def __init__(self, work: Path, uv: Path, runtime: Path, result: dict[str, Any]) -> None:
        self.work, self.uv, self.runtime, self.result = work, uv, runtime, result
        self.prefix = work / "installed"
        self.python = self.prefix / "bin/python"
        self.fixture = work / "graph/pages/S3.md"
        self.inode: tuple[int, int] | None = None

    def run(
        self, step: str, args: list[str], *, cwd: Path | None = None, capture: bool = False
    ) -> bytes:
        self.result["stage"] = step
        _disk(self.work)
        done = sdist_build._run_bounded(args, cwd=cwd or self.work, timeout=180, capture=capture)
        self.result["operations"].append(
            {
                "name": step,
                "exit": done.returncode,
                "cleanup": "verified",
                "stdout_sha256": hashlib.sha256(done.stdout).hexdigest() if capture else None,
            }
        )
        if done.returncode != 0:
            raise ValueError("Bounded S3 subcommand did not succeed.")
        return done.stdout

    def export(self, source: Path, destination: Path, *, rc: bool) -> str:
        args = [
            str(self.uv),
            "export",
            "--project",
            str(source),
            "--frozen",
            "--offline",
            "--no-config",
            "--no-dev",
            "--no-emit-project",
            "--no-header",
            "--no-annotate",
            "--format",
            "requirements.txt",
            "--output-file",
            str(destination),
            "--quiet",
            "--python",
            str(self.runtime),
        ]
        if rc:
            args.extend(["--no-emit-package", "logseq-matryca-parser"])
        self.run("rc-export" if rc else "historical-export", args, cwd=source)
        return read_export(destination, _EXPORT if rc else None)

    def create(self) -> None:
        self.fixture.parent.mkdir(parents=True, mode=0o700)
        with self.fixture.open("xb") as stream:
            stream.write(FIXTURE)
        self.run(
            "new-venv",
            [
                str(self.uv),
                "venv",
                "--no-config",
                "--no-python-downloads",
                "--python",
                str(self.runtime),
                str(self.prefix),
            ],
        )
        stat = self.prefix.stat()
        self.inode = (stat.st_dev, stat.st_ino)
        self.require_prefix()

    def require_prefix(self) -> None:
        if self.prefix.is_symlink() or self.python.resolve(strict=True) != self.runtime:
            raise ValueError("Unexpected venv or native Python.")
        stat = self.prefix.stat()
        if self.inode != (stat.st_dev, stat.st_ino):
            raise ValueError("S3 operation replaced the selected environment.")

    def sync(self, stage: str, closure: str, wheel: Path, digest: str) -> None:
        if wheel.is_symlink() or _hash(wheel) != digest:
            raise ValueError("Transition wheel bytes differ from the selected wheel.")
        path = self.work / f"{stage}.txt"
        with path.open("x", encoding="ascii") as stream:
            stream.write(
                closure.rstrip()
                + "\nmatryca-plumber @ "
                + wheel.as_uri()
                + " --hash=sha256:"
                + digest
                + "\n"
            )
        self.run(
            stage + "-sync",
            [
                str(self.uv),
                "pip",
                "sync",
                "--no-config",
                "--no-python-downloads",
                "--default-index",
                "https://pypi.org/simple",
                "--only-binary",
                ":all:",
                "--require-hashes",
                "--python",
                str(self.python),
                str(path),
            ],
        )

    def observe(self, stage: str, expected: dict[str, str], version: str) -> tuple[str, str]:
        self.require_prefix()
        self.run(
            stage + "-dependency-check",
            [
                str(self.uv),
                "pip",
                "check",
                "--no-config",
                "--no-python-downloads",
                "--python",
                str(self.python),
            ],
        )
        raw = self.run(
            stage + "-inventory",
            [
                str(self.python),
                "-I",
                "-B",
                "-c",
                "import sys,json,importlib.metadata as m; "
                "packages = [[d.metadata['Name'],d.version] for d in m.distributions()]; "
                "print(json.dumps([sys.prefix, packages]))",
            ],
            capture=True,
        )
        prefix, inventory = json.loads(raw)
        actual = {canonicalize_name(n): v for n, v in inventory}
        if (
            len(actual) != len(inventory)
            or actual != {**expected, "matryca-plumber": version}
            or Path(prefix) != self.prefix
        ):
            raise ValueError("Installed inventory or prefix differs from the exact closure.")
        probe = Path(__file__).with_name("first_stable_s3_probe.py").resolve(strict=True)
        read = json.loads(
            self.run(
                stage + "-nested-read",
                [
                    str(self.python),
                    "-I",
                    "-B",
                    str(probe),
                    "--expected-version",
                    version,
                    "--prefix",
                    str(self.prefix),
                    "--fixture",
                    str(self.fixture),
                ],
                capture=True,
            )
        )
        if (
            read["status"] != "PASS"
            or read["nested_read"] is not True
            or read["plumber_version"] != version
            or read["parser_version"] != expected["logseq-matryca-parser"]
            or read["fixture_sha256"] != _FIXTURE_SHA
            or _hash(self.fixture) != _FIXTURE_SHA
        ):
            raise ValueError("Synthetic nested read did not bind the selected installation.")
        records = (read["plumber_record_sha256"], read["parser_record_sha256"])
        require_restored_records(records, records)
        self.result["stages"][stage] = {
            "version": version,
            "inventory": actual,
            "fixture_sha256": _FIXTURE_SHA,
            "plumber_record_sha256": records[0],
            "parser_record_sha256": records[1],
        }
        return records


def qualify(args: argparse.Namespace) -> None:
    """Run one case; no package installation happens before admission."""
    target, name = args.target, args.case
    kind, version = select_case(target, name, args.builder, args.baseline_source)
    work: Path = args.work
    output: Path = args.output
    runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    for path in (work, output):
        if (
            not path.is_absolute()
            or not path.is_relative_to(runner_temp)
            or path.parent.resolve(strict=True) != path.parent
            or os.path.lexists(path)
        ):
            raise ValueError("S3 work or report is not fresh and task-owned.")
    if work in output.parents or output in work.parents or output == work:
        raise ValueError("S3 work and report must be disjoint.")
    _disk(runner_temp)
    runtime = _admit_host(target, args.runtime)
    source: Path = args.source
    require_source(source, RC_COMMIT, RC_TREE)
    if version is not None:
        pin = BASELINES[version]
        require_source(args.baseline_source, pin.commit, pin.tree)
    uv_hash = _hash(args.uv)
    if (
        not args.uv.is_absolute()
        or args.uv.resolve(strict=True) != args.uv
        or uv_hash != os.environ.get("S3_UV_SHA256")
    ):
        raise ValueError("Installer differs from the verified archive member.")
    result: dict[str, Any] = {
        "schema_version": 1,
        "result": "FAIL",
        "stage": "admission",
        "target": target,
        "case": name,
        "kind": kind,
        "producer_commit": RC_COMMIT,
        "producer_tree": RC_TREE,
        "producer_tag": TAG,
        "producer_tag_object": RC_TAG_OBJECT,
        "producer_publication_run": RC_PUBLISHER_RUN,
        "verifier_commit": os.environ["GITHUB_SHA"],
        "run_id": int(os.environ["GITHUB_RUN_ID"]),
        "run_attempt": 1,
        "runtime": runtime,
        "uv_sha256": uv_hash,
        "operations": [],
        "stages": {},
    }
    os.umask(0o077)
    work.mkdir(mode=0o700)
    case = Case(work, args.uv, args.runtime, result)
    # Control subprocess inputs without retaining the caller's tokens, caches or config.
    inherited = {key: os.environ[key] for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT")}
    for subdir in ("home", "tmp", "config", "cache", "data"):
        (work / subdir).mkdir(mode=0o700)
    os.environ.clear()
    os.environ.update(
        inherited,
        PATH="/usr/bin:/bin",
        LANG="C",
        LC_ALL="C",
        HOME=str(work / "home"),
        TMPDIR=str(work / "tmp"),
        XDG_CONFIG_HOME=str(work / "config"),
        XDG_CACHE_HOME=str(work / "cache"),
        XDG_DATA_HOME=str(work / "data"),
        MATRYCA_READ_ONLY="true",
        MATRYCA_CACHE_PATH=str(work / "data/shadow"),
        LOGSEQ_GRAPH_PATH=str(case.fixture.parents[1]),
        PYTHONDONTWRITEBYTECODE="1",
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL="/dev/null",
        GIT_OPTIONAL_LOCKS="0",
        UV_CACHE_DIR=str(work / "cache/uv"),
        UV_NO_CONFIG="true",
        UV_HTTP_RETRIES="0",
        UV_PYTHON_DOWNLOADS="never",
        UV_NO_PROGRESS="1",
        UV_SYSTEM_CERTS="true",
    )
    acquisition = AcquisitionCheckpoint()
    try:
        if case.run("installer-version", [str(args.uv), "--version"], capture=True).split()[:2] != [
            b"uv",
            b"0.12.19",
        ]:
            raise ValueError("Unexpected installer version.")
        result["stage"] = "public-acquisition"
        originals = work / "public"
        binding = acquire_public(originals, version, checkpoint=acquisition)
        result["binding"] = json.loads(binding.to_json())
        rc_export = case.export(source, work / "runtime-lock.txt", rc=True)
        profile = resolve_profile(rc_export, "current", target, _PYTHON)
        result["locked_export_sha256"] = hashlib.sha256(rc_export.encode("ascii")).hexdigest()
        result["profile_sha256"] = hashlib.sha256(profile.requirements.encode("ascii")).hexdigest()
        expected = dict(profile.packages)
        case.create()
        wheel = originals / "dist" / binding.wheel_name
        row_key = f"current-{target}-cpython-{_PYTHON}-{kind}"
        prior = None
        historical = ""
        baseline = None
        if version is not None:
            pin = BASELINES[version]
            historical = case.export(args.baseline_source, work / "historical-lock.txt", rc=False)
            historical_expected = historical_dependencies(historical, target)
            result["baseline"] = {
                "source_commit": pin.commit,
                "source_tree": pin.tree,
                "wheel_name": pin.wheel_name,
                "wheel_sha256": pin.wheel_sha256,
                "export_sha256": hashlib.sha256(historical.encode("ascii")).hexdigest(),
            }
            if (
                historical_expected.get("logseq-matryca-parser")
                != {"2.0.0": "1.7.1", "2.1.0a4": "1.9.0"}[version]
            ):
                raise ValueError("Historical closure does not bind the selected Parser.")
            baseline = originals / pin.wheel_name
            case.sync("baseline", historical, baseline, pin.wheel_sha256)
            prior = case.observe("baseline", historical_expected, version)
            case.sync("upgrade", profile.requirements, wheel, binding.wheel_sha256)
        else:
            if kind == "sdist":
                result["stage"] = "locked-sdist-build"
                wheel, result["sdist_build"] = _build_from_sdist(
                    source,
                    args.uv,
                    args.builder,
                    originals / "dist",
                    binding,
                    work,
                    row_key,
                )
            requirements = work / "current.txt"
            with requirements.open("x", encoding="ascii") as stream:
                stream.write(profile.requirements)
            for step, command in zip(
                ("install-locked-closure", "install-exact-wheel"),
                install_commands(args.uv, case.python, requirements, wheel),
                strict=True,
            ):
                case.run(step, command)
        case.observe("rc1", expected, _RC)
        result["stage"] = "installed-contract-verification"
        row = work / "installed-row.json"
        verify_and_write_installed_row(
            output=row,
            row_key=row_key,
            candidate_tag=TAG,
            binding=binding,
            expected_dependencies=expected,
            installed_python=case.python,
            source_root=source,
            originals=originals / "dist",
        )
        result["installed_rc1"] = json.loads(row.read_bytes())
        if version is not None and baseline is not None and prior is not None:
            case.sync("rollback", historical, baseline, BASELINES[version].wheel_sha256)
            restored = case.observe("rollback", historical_expected, version)
            require_restored_records(prior, restored)
            result["baseline_restored"] = True
        result["stage"] = "final-integrity"
        case.require_prefix()
        bundle.verify_handoff(
            originals / "dist", originals / "dist/SHA256SUMS", binding, policy="og-alpha3"
        )
        require_source(source, RC_COMMIT, RC_TREE)
        if version is not None:
            require_source(args.baseline_source, BASELINES[version].commit, BASELINES[version].tree)
        if (
            _hash(args.runtime) != runtime["executable_sha256"]
            or _hash(args.uv) != uv_hash
            or _hash(case.fixture) != _FIXTURE_SHA
        ):
            raise ValueError("S3 runtime, installer or fixture changed during the case.")
        result["result"] = "PASS"
    except BaseException as error:
        result["failure_class"] = type(error).__name__
        if result["stage"] == "public-acquisition" and isinstance(error, (OSError, ValueError)):
            result["acquisition_diagnostic"] = acquisition.diagnostic(error)
        raise
    finally:
        _write_json(output, result)


def _need(condition: bool, label: str) -> None:
    if not condition:
        raise ValueError(f"Invalid S3 report: {label}.")


def _hash_field(value: object) -> bool:
    return isinstance(value, str) and _SHA.fullmatch(value) is not None


def _safe_report_value(value: Any, depth: int = 0) -> bool:
    """Permit only bounded JSON scalars and containers, with no paths or raw logs."""
    if depth > 12:
        return False
    if isinstance(value, str):
        return (
            len(value) <= 512
            and value.isascii()
            and all(32 <= ord(char) < 127 and char not in "/\\" for char in value)
        )
    if isinstance(value, list):
        return len(value) <= 512 and all(_safe_report_value(item, depth + 1) for item in value)
    if isinstance(value, dict):
        return len(value) <= 512 and all(
            key not in {"stderr", "stdout", "log", "logs", "path", "environment_values", "token"}
            and _safe_report_value(key, depth + 1)
            and _safe_report_value(item, depth + 1)
            for key, item in value.items()
        )
    return value is None or type(value) in (int, bool)


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = dict(pairs)
    _need(len(result) == len(pairs), "unique JSON fields")
    return result


def _case_operations(baseline: str | None) -> list[str]:
    install = (
        ["install-locked-closure", "install-exact-wheel"]
        if baseline is None
        else [
            "historical-export",
            "baseline-sync",
            "baseline-dependency-check",
            "baseline-inventory",
            "baseline-nested-read",
            "upgrade-sync",
        ]
    )
    rollback = (
        []
        if baseline is None
        else [
            "rollback-sync",
            "rollback-dependency-check",
            "rollback-inventory",
            "rollback-nested-read",
        ]
    )
    return [
        "installer-version",
        "rc-export",
        "new-venv",
        *install,
        "rc1-dependency-check",
        "rc1-inventory",
        "rc1-nested-read",
        *rollback,
    ]


def _check_sdist(row: dict[str, Any], row_key: str, target: str, run: int) -> None:
    selected = row["sdist_build"]
    _need(set(selected) == {"receipt", "descriptor", "provisioning"}, "sdist evidence")
    receipt, descriptor, provisioning = (
        selected["receipt"],
        selected["descriptor"],
        selected["provisioning"],
    )
    BuildEnvironmentDescriptor.from_bytes(canonical(descriptor))
    _need(
        set(receipt) == set(sdist_build.SdistBuildReceipt.__dataclass_fields__)
        and type(receipt["schema_version"]) is int
        and receipt["schema_version"] == 2,
        "complete sdist receipt fields",
    )
    expected = {
        "source_commit": RC_COMMIT,
        "source_tree": RC_TREE,
        "binding_sha256": digest(row["binding"]),
        "sdist_name": _RC_BINDING.sdist_name,
        "sdist_size": _RC_BINDING.sdist_size,
        "sdist_sha256": _RC_BINDING.sdist_sha256,
        "provisioning_recipe_sha256": _BUILDER_RECIPE,
        "provisioning_evidence_sha256": digest(provisioning),
    }
    _need(
        all(
            receipt.get(key) == val and descriptor.get(key) == val for key, val in expected.items()
        ),
        "original sdist and builder binding",
    )
    environment = provisioning["environment"]
    system, arch = ("macos", "arm64") if target == "macos-arm64" else ("linux", "x64")
    native_builder = {
        "python_implementation": "CPython",
        "python_version": _PYTHON,
        "python_executable_sha256": row["runtime"]["executable_sha256"],
        "target_os": system,
        "target_architecture": arch,
        "uv_version": "0.12.19",
        "uv_sha256": row["uv_sha256"],
        "build_lock_sha256": _BUILDER_LOCK,
    }
    _need(
        environment == {**native_builder, "packages": _BUILDER_PACKAGES}
        and all(receipt[key] == descriptor[key] == val for key, val in native_builder.items())
        and descriptor["packages"] == _BUILDER_PACKAGES
        and receipt["backend"] == "setuptools.build_meta"
        and receipt["backend_version"] == "84.1.0"
        and all(
            receipt[key] == _BUILDER_PACKAGES
            for key in (
                "provisioned_packages",
                "before_hooks_packages",
                "after_hooks_packages",
                "after_build_packages",
            )
        ),
        "locked sdist builder closure",
    )
    _need(
        set(provisioning) == {"instance", "run_id", "run_attempt", "operation", "environment"}
        and provisioning["instance"] == row_key
        and provisioning["run_id"] == str(run)
        and type(provisioning["run_attempt"]) is int
        and provisioning["run_attempt"] == 1
        and provisioning["operation"] == "uv-sync-locked-no-install-project"
        and receipt["environment_descriptor_sha256"] == digest(descriptor)
        and receipt["wheel_name"] == _RC_BINDING.wheel_name
        and type(receipt["wheel_size"]) is int
        and receipt["wheel_size"] > 0
        and _hash_field(receipt["wheel_sha256"]),
        "native locked build receipt",
    )
    packages = {item["name"]: item["version"] for item in _BUILDER_PACKAGES}
    for key in ("static_requirement_records", "dynamic_requirement_records"):
        records = receipt[key]
        _need(isinstance(records, list), "build requirement observations")
        for item in records:
            _need(
                set(item) == {"expression", "marker_applicable", "satisfier"},
                "build requirement fields",
            )
            dependency = item["satisfier"]
            _need(
                dependency is None or set(dependency) == {"name", "version"},
                "build requirement satisfier",
            )
            satisfier = None if dependency is None else (dependency["name"], dependency["version"])
            observed = sdist_build.BuildRequirementRecord(
                item["expression"], item["marker_applicable"], satisfier
            )
            observed.validate(
                packages,
                target_os=system,
                target_architecture=arch,
                python_implementation="CPython",
                python_version=_PYTHON,
            )
    _need(
        [item["expression"] for item in receipt["static_requirement_records"]]
        == ["setuptools>=61", "wheel"],
        "required static build inputs",
    )


def _check_pass(row: dict[str, Any], target: str, case: str, run: int) -> None:
    baseline = _CASES[case]
    sdist = case == "clean-sdist"
    kind = "sdist" if sdist else "wheel"
    row_key = f"current-{target}-cpython-{_PYTHON}-{kind}"
    _need(
        row["stage"] == "final-integrity"
        and row["binding"] == json.loads(_RC_BINDING.to_json())
        and row["locked_export_sha256"] == _EXPORT
        and _hash_field(row["profile_sha256"]),
        "final binding and locked profile",
    )
    installed_row = row["installed_rc1"]
    installed = installed_row["installed"]
    original = (
        (_RC_BINDING.sdist_name, _RC_BINDING.sdist_size, _RC_BINDING.sdist_sha256)
        if sdist
        else (_RC_BINDING.wheel_name, _RC_BINDING.wheel_size, _RC_BINDING.wheel_sha256)
    )
    observed_os, machine = HOSTS[target]
    _need(
        set(installed_row)
        == {
            "schema_version",
            "row_key",
            "source_commit",
            "source_tree",
            "candidate_tag",
            "original_artifact",
            "installed",
        }
        and installed_row["schema_version"] == 1
        and (installed_row["source_commit"], installed_row["source_tree"]) == (RC_COMMIT, RC_TREE)
        and installed_row["row_key"] == row_key
        and installed_row["candidate_tag"] == TAG
        and installed_row["original_artifact"]
        == dict(zip(("name", "size", "sha256"), original, strict=True))
        and installed["kind"] == kind
        and set(installed).issubset(InstalledReceipt.__dataclass_fields__)
        and (installed["operating_system"], installed["architecture"])
        == (observed_os.lower(), machine)
        and installed["version"] == _RC
        and installed["python_version"] == _PYTHON
        and installed["location_class"] == "isolated-venv-site-packages"
        and installed.get("windows_launcher") is None
        and installed["tck_outcomes"] == ["PASS"] * 3
        and all(
            _hash_field(installed[name])
            for name in ("record_sha256", "resource_sha256", "dependency_sha256")
        ),
        "installed contract receipt",
    )
    stages = row["stages"]
    expected_stages = {"rc1": (_RC, "1.11.4")}
    if baseline is not None:
        parser = "1.7.1" if baseline == "2.0.0" else "1.9.0"
        expected_stages.update(baseline=(baseline, parser), rollback=(baseline, parser))
    _need(set(stages) == set(expected_stages), "required installation stages")
    for name, (version, parser) in expected_stages.items():
        stage = stages[name]
        _need(
            set(stage)
            == {
                "version",
                "inventory",
                "fixture_sha256",
                "plumber_record_sha256",
                "parser_record_sha256",
            }
            and stage["version"] == version
            and stage["fixture_sha256"] == _FIXTURE_SHA
            and stage["inventory"]["matryca-plumber"] == version
            and stage["inventory"]["logseq-matryca-parser"] == parser
            and _hash_field(stage["plumber_record_sha256"])
            and _hash_field(stage["parser_record_sha256"]),
            "synthetic read and installed inventory",
        )
    dependencies = installed["dependencies"]
    normalized = [(item["name"], item["version"]) for item in dependencies]
    _need(
        all(set(item) == {"name", "version"} for item in dependencies)
        and len(dict(normalized)) == len(normalized)
        and stages["rc1"]["inventory"] == {"matryca-plumber": _RC, **dict(normalized)}
        and installed["dependency_sha256"]
        == hashlib.sha256(json.dumps(normalized, separators=(",", ":")).encode()).hexdigest(),
        "bound dependency inventory",
    )
    if sdist:
        _check_sdist(row, row_key, target, run)
    if baseline is not None:
        pin = BASELINES[baseline]
        selected = row["baseline"]
        _need(
            set(selected)
            == {"source_commit", "source_tree", "wheel_name", "wheel_sha256", "export_sha256"}
            and (
                selected["source_commit"],
                selected["source_tree"],
                selected["wheel_name"],
                selected["wheel_sha256"],
            )
            == (pin.commit, pin.tree, pin.wheel_name, pin.wheel_sha256)
            and _hash_field(selected["export_sha256"])
            and row["baseline_restored"] is True
            and stages["baseline"] == stages["rollback"],
            "restored baseline and RECORDs",
        )


def _check_report(
    row: dict[str, Any], case: str, target: str, verifier: str, run: int, *, fail_allowed: bool
) -> None:
    common = {
        "schema_version": 1,
        "producer_commit": RC_COMMIT,
        "producer_tree": RC_TREE,
        "producer_tag": TAG,
        "producer_tag_object": RC_TAG_OBJECT,
        "producer_publication_run": RC_PUBLISHER_RUN,
        "target": target,
        "case": case,
        "kind": "sdist" if case == "clean-sdist" else "wheel",
        "verifier_commit": verifier,
        "run_id": run,
        "run_attempt": 1,
    }
    required = {*common, "runtime", "uv_sha256", "result", "stage", "operations", "stages"}
    evidence = {"binding", "locked_export_sha256", "profile_sha256", "installed_rc1"}
    if case == "clean-sdist":
        evidence.add("sdist_build")
    baseline = _CASES[case]
    if baseline is not None:
        evidence.update({"baseline", "baseline_restored"})
    _need(
        isinstance(row, dict)
        and _safe_report_value(row)
        and all(type(row.get(key)) is type(val) and row[key] == val for key, val in common.items())
        and required.issubset(row)
        and set(row).issubset(required | evidence | {"failure_class", "acquisition_diagnostic"})
        and _hash_field(row["uv_sha256"]),
        "closed identity and path-free schema",
    )
    runtime = row["runtime"]
    _need(
        set(runtime)
        == {
            "archive_sha256",
            "implementation",
            "platform",
            "version",
            "executable_sha256",
            "cleanup",
        }
        and runtime["archive_sha256"] == PINS[target, _PYTHON].sha256
        and runtime["implementation"] == "CPython"
        and runtime["platform"] == target
        and runtime["version"] == _PYTHON
        and runtime["cleanup"] == "verified"
        and _hash_field(runtime["executable_sha256"]),
        "runtime identity and verified cleanup",
    )
    statuses = row["operations"]
    passing = row["result"] == "PASS"
    _need(
        passing or (fail_allowed and row["result"] == "FAIL" and "failure_class" in row),
        "terminal outcome",
    )
    if "acquisition_diagnostic" in row:
        _need(
            not passing
            and row["stage"] == "public-acquisition"
            and valid_acquisition_diagnostic(row["acquisition_diagnostic"], baseline),
            "closed public acquisition diagnostic",
        )
    names = _case_operations(baseline)
    _need(
        [event["name"] for event in statuses] == names[: len(statuses)]
        and all(
            set(event) == {"name", "exit", "cleanup", "stdout_sha256"}
            and event["cleanup"] == "verified"
            and type(event["exit"]) is int
            and (event["stdout_sha256"] is None or _hash_field(event["stdout_sha256"]))
            and (event["exit"] == 0 or (not passing and index == len(statuses) - 1))
            for index, event in enumerate(statuses)
        ),
        "bounded operation evidence",
    )
    if passing:
        _need(
            set(row) == required | evidence and len(statuses) == len(names), "complete PASS fields"
        )
        _check_pass(row, target, case, run)


def verify_reports(reports: Path, target: str, outcome: str, verifier: str, run: int) -> None:
    """Check original producer, run and stage proof before any report upload."""
    _need(target in HOSTS and outcome in {"success", "failure"}, "native platform and job outcome")
    _need(
        re.fullmatch(r"[0-9a-f]{40}", verifier) is not None
        and run > 0
        and reports.resolve(strict=True) == reports
        and reports.is_dir(),
        "hosted workflow context or report directory",
    )
    cases = ["clean-sdist"] if target == "macos-arm64" else list(_CASES)
    observed = {entry.name for entry in reports.iterdir()}
    selected = cases[: len(observed)]
    _need(
        bool(observed)
        and observed == {f"{case}.json" for case in selected}
        and (outcome == "failure" or len(observed) == len(cases)),
        "report set or partial run order",
    )
    for index, case in enumerate(selected):
        path = reports / f"{case}.json"
        _need(
            not path.is_symlink() and path.is_file() and 0 < path.stat().st_size <= 262_144,
            "bounded regular report file",
        )
        with path.open("rb") as stream:
            data = stream.read(262_145)
        _need(len(data) <= 262_144, "bounded report bytes")
        _check_report(
            json.loads(data, object_pairs_hook=_unique_json_object),
            case,
            target,
            verifier,
            run,
            fail_allowed=outcome == "failure" and index == len(selected) - 1,
        )


def _reports_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Verify sanitized S3 case evidence.")
    parser.add_argument("--target", required=True)
    parser.add_argument("--reports", type=Path, required=True)
    parser.add_argument("--outcome", required=True)
    args = parser.parse_args(argv)
    try:
        verify_reports(
            args.reports,
            args.target,
            args.outcome,
            os.environ["GITHUB_SHA"],
            int(os.environ["GITHUB_RUN_ID"]),
        )
    except (OSError, ValueError, TypeError, KeyError):
        print("S3 report rejected; no report from this job is uploadable.", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    if sys.argv[1:2] == ["verify-reports"]:
        return _reports_main(sys.argv[2:])
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("target", "case"):
        parser.add_argument(f"--{option}", required=True)
    for option in ("source", "uv", "runtime", "work", "output"):
        parser.add_argument(f"--{option}", required=True, type=Path)
    for option in ("builder", "baseline-source"):
        parser.add_argument(f"--{option}", type=Path)
    args = parser.parse_args()
    try:
        qualify(args)
    except (OSError, ValueError, RuntimeError) as error:
        print(
            f"S3 qualification stopped: {type(error).__name__}; inspect the case receipt.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
