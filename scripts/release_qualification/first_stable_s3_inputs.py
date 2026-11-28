"""Admit only the retained public RC1 and exact historical baseline wheels.

The RC1 public bytes were already attested and independently admitted. This
module rechecks their fixed byte identities; it does not claim a new
attestation ceremony or execute downloaded package content.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from scripts.release_qualification.alpha1_matrix import canonical, document
from scripts.release_qualification.alpha1_public import (
    _acquire as _acquire_public,
)
from scripts.release_qualification.alpha1_public import (
    _read_fetch_failure,
    fetch_failure_diagnostic,
)
from scripts.release_qualification.alpha1_public import (
    installed_status as _installed_status,
)
from scripts.release_qualification.bundle import BundleBinding, _git_value, verify_handoff

TAG = "v2.1.0-rc.1"
RC_TAG_OBJECT = "959ad1ce70d956aa6085bc5d1e0acc9853621e8b"
RC_PUBLISHER_RUN = 45996481639
RC_COMMIT = "4080f69ffc7d69edda27886530ce2932a6ee3fed"
RC_TREE = "d9d2ed439e8be446ff4ec1604807f788935060c4"
_RC_VERSION = "2.1.0rc1"
_REPO_URL = "https://github.com/MarcoPorcellato/matryca-plumber"
_GH_RELEASE_URL = f"{_REPO_URL}/releases/download/{TAG}"
_POLICY = "og-alpha3"
_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class Baseline:
    """Fixed source and public wheel identity for one admitted baseline."""

    commit: str
    tree: str
    wheel_name: str
    wheel_sha256: str
    wheel_size: int
    pypi_url: str


BASELINES: Mapping[str, Baseline] = MappingProxyType(
    {
        "2.0.0": Baseline(
            commit="987446b8337f7abd308a9efe4abb834ce1acdc1b",
            tree="d164f054f84e7d6eb33a60efbaa6181403edf312",
            wheel_name="matryca_plumber-2.0.0-py3-none-any.whl",
            wheel_sha256="d3247aa1f4c2ea802c0bd94b180df61fef8d3f1faf62e0f3b920e483f74c4653",
            wheel_size=593_914,
            pypi_url=(
                "https://files.pythonhosted.org/packages/e7/84/"
                "0a399141c2965c5c6961a0f83b94297c26620188d18d948de62608a6a4ff/"
                "matryca_plumber-2.0.0-py3-none-any.whl"
            ),
        ),
        "2.1.0a4": Baseline(
            commit="1d884ddcbdb37ecdd0d4ad3ccb3e9a6d406e1bdd",
            tree="22bced0e8eef57595acdfed12933e53905f22a95",
            wheel_name="matryca_plumber-2.1.0a4-py3-none-any.whl",
            wheel_sha256="6d611de748d267bf377dd8f3266259ede71268fd39f30ac7136238cc99cdad56",
            wheel_size=768_418,
            pypi_url=(
                "https://files.pythonhosted.org/packages/fd/11/"
                "9d2b2511981ebcc9fc6c2eecfd1a81377803efcefb26bcf93846c80012b8/"
                "matryca_plumber-2.1.0a4-py3-none-any.whl"
            ),
        ),
    }
)
_BASELINE_TAGS: Mapping[str, str] = MappingProxyType(
    {"2.0.0": "v2.0.0", "2.1.0a4": "v2.1.0-alpha.4"}
)

_RC_BINDING = BundleBinding(
    source_commit=RC_COMMIT,
    source_tree=RC_TREE,
    version=_RC_VERSION,
    wheel_name="matryca_plumber-2.1.0rc1-py3-none-any.whl",
    wheel_size=768_440,
    wheel_sha256="e7fc25eca467bdc67da5b35540d2779618c8c022b2b56578934cde399d1b8a88",
    sdist_name="matryca_plumber-2.1.0rc1.tar.gz",
    sdist_size=1_115_739,
    sdist_sha256="2b728f46f1eb9ebaff6716053aa92675c6fa47dc90e4d6de22a6a5ace0de7867",
    wheel_inventory_sha256="f246107868f554855429eccf0a47a9faec2001db20a81ce2e7ec0c49e41a7944",
    sdist_inventory_sha256="a1e629fa7e4ad63de5d2e165303369f5ff24fe62b4b7c552c8cf4d8dac90b22e",
)
_RC_BINDING_SHA256 = "65473d955944d94128aa812fef3ad2ed7264b35762fbc4749da9fba5af35e031"
_RC_BINDING_SIZE = 631
_RC_MANIFEST_SIZE = 206
_RC_MANIFEST_SHA256 = "dfffbb87b4696a47130b48b65a83f4bd1c05d1ef327d21b47144576f81e979a1"

_RC_URLS: Mapping[str, str] = MappingProxyType(
    {
        _RC_BINDING.wheel_name: f"{_GH_RELEASE_URL}/{_RC_BINDING.wheel_name}",
        _RC_BINDING.sdist_name: f"{_GH_RELEASE_URL}/{_RC_BINDING.sdist_name}",
        "binding.json": f"{_GH_RELEASE_URL}/binding.json",
        "SHA256SUMS": f"{_GH_RELEASE_URL}/SHA256SUMS",
    }
)
_PYPI_URLS: Mapping[str, str] = MappingProxyType(
    {
        _RC_BINDING.wheel_name: (
            "https://files.pythonhosted.org/packages/cc/1c/"
            "277ce07fe32c5b53273428f76db00c6d07cd6b3533a59bf930e29c891675/"
            "matryca_plumber-2.1.0rc1-py3-none-any.whl"
        ),
        _RC_BINDING.sdist_name: (
            "https://files.pythonhosted.org/packages/42/88/"
            "7a6dc59989da5b9dada66c2c09dc9b450a0c94a078bed8019211d2c0f65e/"
            "matryca_plumber-2.1.0rc1.tar.gz"
        ),
    }
)

_FETCH_STEPS = frozenset({"github-fetch", "pypi-fetch", "baseline-fetch"})
_FETCH_ERROR_PREFIX = "One-shot public acquisition failed: "


@dataclass(slots=True)
class AcquisitionCheckpoint:
    """Remember the last acquisition boundary without retaining paths or URLs."""

    step: str = "prepare"
    asset: str | None = None

    def mark(self, step: str, asset: str | None = None) -> None:
        self.step, self.asset = step, asset

    def diagnostic(self, error: ValueError | OSError) -> dict[str, Any]:
        """Keep the downloader's bounded failure details, not its exception text."""
        failure = fetch_failure_diagnostic(error)
        code = None
        # The shared downloader attaches structured child evidence to a fixed
        # error envelope. Parse only a bounded matching envelope; never relay it.
        message = error.args[0] if type(error) is ValueError and len(error.args) == 1 else None
        if (
            self.step in _FETCH_STEPS
            and isinstance(message, str)
            and len(message) <= 4096
            and message.isascii()
            and message.startswith(_FETCH_ERROR_PREFIX)
        ):
            try:
                child = document(message.removeprefix(_FETCH_ERROR_PREFIX).encode("ascii"))
            except (ValueError, RecursionError):
                child = {}
            origin = "github" if self.step == "github-fetch" else "pypi"
            if child.get("kind") == origin and child.get("asset") == self.asset:
                result = child.get("returncode")
                if type(result) is int and -255 <= result <= 255 and result != 0:
                    code = result
                    failure = _read_fetch_failure(canonical(child.get("failure"))) or failure
        return {"step": self.step, "asset": self.asset, "returncode": code, "failure": failure}


def valid_acquisition_diagnostic(value: object, baseline: str | None) -> bool:
    """Accept only the monitored step/asset pairs and closed downloader fields."""
    if not isinstance(value, dict) or set(value) != {"step", "asset", "returncode", "failure"}:
        return False
    step, asset, code = value["step"], value["asset"], value["returncode"]
    if step in ("github-fetch", "github-verify"):
        allowed: Collection[str | None] = _RC_URLS.keys()
    elif step in ("pypi-fetch", "pypi-verify"):
        allowed = _PYPI_URLS.keys()
    elif step in ("baseline-fetch", "baseline-verify", "baseline-copy"):
        allowed = (BASELINES[baseline].wheel_name,) if baseline is not None else ()
    elif step == "binding-verify":
        allowed = ("binding.json",)
    elif step in ("prepare", "bundle-verify"):
        allowed = (None,)
    else:
        return False
    return (
        (asset is None or isinstance(asset, str))
        and asset in allowed
        and (
            code is None
            or (step in _FETCH_STEPS and type(code) is int and -255 <= code <= 255 and code != 0)
        )
        and _read_fetch_failure(canonical(value["failure"])) is not None
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _file_identity(path: Path) -> tuple[int, str]:
    """Hash one existing regular file without following a final symlink."""
    try:
        metadata = path.lstat()
    except OSError as error:
        raise ValueError("Public input file is missing or unreadable.") from error
    _require(stat.S_ISREG(metadata.st_mode), "Public input must be a regular file.")
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(65_536):
                size += len(chunk)
                digest.update(chunk)
    except OSError as error:
        raise ValueError("Public input file is missing or unreadable.") from error
    _require(size == metadata.st_size, "Public input changed while being verified.")
    return size, digest.hexdigest()


def _require_identity(path: Path, size: int, sha256: str) -> None:
    _require(
        type(size) is int and size > 0 and _SHA256.fullmatch(sha256) is not None,
        "Invalid pinned public input identity.",
    )
    _require(_file_identity(path) == (size, sha256), "Public input differs from its fixed pin.")


def require_source(source: Path, commit: str, tree: str) -> None:
    """Require a real, clean checkout at the exact selected source identity."""
    _require(
        isinstance(source, Path)
        and not source.is_symlink()
        and source.is_dir()
        and re.fullmatch(r"[0-9a-f]{40}", commit) is not None
        and re.fullmatch(r"[0-9a-f]{40}", tree) is not None,
        "Selected source path or identity is invalid.",
    )
    resolved = source.resolve(strict=True)
    observed_commit = _git_value(resolved, "HEAD")
    observed_tree = _git_value(resolved, "HEAD^{tree}")
    clean = _installed_status(resolved)
    _require(
        (observed_commit, observed_tree) == (commit, tree) and not clean,
        "Selected source must be clean and match the exact commit and tree.",
    )


def _fresh_root(root: Path) -> Path:
    _require(isinstance(root, Path) and not root.is_symlink(), "Public input root is invalid.")
    parent = root.parent
    _require(
        parent.is_dir() and not parent.is_symlink(),
        "Public input parent must be a real directory.",
    )
    _require(not os.path.lexists(root), "Public input root must be fresh.")
    return root


def acquire_public(
    root: Path, baseline: str | None, *, checkpoint: AcquisitionCheckpoint | None = None
) -> BundleBinding:
    """Acquire admitted RC1 bytes and, optionally, one exact public baseline wheel.

    GitHub and PyPI originals are independently fetched through the bounded,
    host-pinned acquisition owner. Each copy is checked against its retained
    size and digest, then their identities are compared before handoff checks.
    """
    trace = checkpoint if checkpoint is not None else AcquisitionCheckpoint()
    trace.mark("prepare")
    _require(
        baseline is None or (isinstance(baseline, str) and baseline in BASELINES),
        "Unknown S3 baseline selection.",
    )
    _require(
        (_RC_BINDING.source_commit, _RC_BINDING.source_tree, _RC_BINDING.version)
        == (RC_COMMIT, RC_TREE, _RC_VERSION),
        "Retained RC1 binding constants are inconsistent.",
    )
    root = _fresh_root(root)
    root.mkdir(mode=0o700)
    dist = root / "dist"
    dist.mkdir(mode=0o700)

    binding_path = root / "binding.json"
    manifest_path = dist / "SHA256SUMS"
    trace.mark("github-fetch", binding_path.name)
    _acquire_public(
        _RC_URLS["binding.json"],
        binding_path,
        _RC_BINDING_SIZE,
        _RC_BINDING_SHA256,
        "github",
        release_tag=TAG,
    )
    trace.mark("github-fetch", manifest_path.name)
    _acquire_public(
        _RC_URLS["SHA256SUMS"],
        manifest_path,
        _RC_MANIFEST_SIZE,
        _RC_MANIFEST_SHA256,
        "github",
        release_tag=TAG,
    )
    for name, size, sha256 in (
        (_RC_BINDING.wheel_name, _RC_BINDING.wheel_size, _RC_BINDING.wheel_sha256),
        (_RC_BINDING.sdist_name, _RC_BINDING.sdist_size, _RC_BINDING.sdist_sha256),
    ):
        target = dist / name
        trace.mark("github-fetch", name)
        _acquire_public(_RC_URLS[name], target, size, sha256, "github", release_tag=TAG)
        trace.mark("github-verify", name)
        _require_identity(target, size, sha256)
    trace.mark("github-verify", binding_path.name)
    _require_identity(binding_path, _RC_BINDING_SIZE, _RC_BINDING_SHA256)
    trace.mark("github-verify", manifest_path.name)
    _require_identity(manifest_path, _RC_MANIFEST_SIZE, _RC_MANIFEST_SHA256)
    trace.mark("binding-verify", binding_path.name)
    try:
        observed = BundleBinding.from_json(binding_path.read_text(encoding="ascii"), policy=_POLICY)
    except (OSError, UnicodeError, ValueError) as error:
        raise ValueError("Retained RC1 binding is invalid.") from error
    _require(
        observed == _RC_BINDING,
        "Retained RC1 binding differs from admitted publication metadata.",
    )

    trace.mark("prepare")
    pypi_root = root / "pypi"
    pypi_root.mkdir(mode=0o700)
    for name, size, sha256 in (
        (_RC_BINDING.wheel_name, _RC_BINDING.wheel_size, _RC_BINDING.wheel_sha256),
        (_RC_BINDING.sdist_name, _RC_BINDING.sdist_size, _RC_BINDING.sdist_sha256),
    ):
        trace.mark("github-verify", name)
        github_identity = _file_identity(dist / name)
        pypi_path = pypi_root / name
        trace.mark("pypi-fetch", name)
        _acquire_public(
            _PYPI_URLS[name],
            pypi_path,
            size,
            sha256,
            "pypi",
            release_tag=TAG,
        )
        trace.mark("pypi-verify", name)
        _require_identity(pypi_path, size, sha256)
        _require(
            _file_identity(pypi_path) == github_identity,
            "PyPI and GitHub public input bytes differ.",
        )

    trace.mark("bundle-verify")
    verify_handoff(dist, manifest_path, observed, policy=_POLICY)
    if baseline is not None:
        selected = BASELINES[baseline]
        baseline_pypi = pypi_root / selected.wheel_name
        trace.mark("baseline-fetch", selected.wheel_name)
        _acquire_public(
            selected.pypi_url,
            baseline_pypi,
            selected.wheel_size,
            selected.wheel_sha256,
            "pypi",
            release_tag=_BASELINE_TAGS[baseline],
        )
        trace.mark("baseline-verify", selected.wheel_name)
        _require_identity(baseline_pypi, selected.wheel_size, selected.wheel_sha256)
        target = root / selected.wheel_name
        trace.mark("baseline-copy", selected.wheel_name)
        with baseline_pypi.open("rb") as source, target.open("xb") as output:
            shutil.copyfileobj(source, output, length=65_536)
        trace.mark("baseline-verify", selected.wheel_name)
        _require_identity(
            target,
            selected.wheel_size,
            selected.wheel_sha256,
        )
    return observed
