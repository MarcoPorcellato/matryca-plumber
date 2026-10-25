"""Closed verifier identity for recovery of the immutable published alpha.3."""

from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from scripts.release_qualification import bundle, installed
from scripts.release_qualification.release_target import ALPHA3_TARGET, ReleaseTarget

SOURCE = "8c30f70e217722e719c5aedc322219ebccb87e68"
TREE = "de80d0473aa281c52d0fed10b4561024dd12d76f"
TAG_OBJECT = "c093e9e8aa735b7c37a0c1a56a601a9c31cbdf24"
PUBLISHER = "39887297548"
FAILED_QUALIFICATION = "39888823938"
WORKFLOW = ".github/workflows/og-public-artifact-qualification.yml"
POLICY = "alpha3-verifier-recovery/v1"
REQUIRED_TOOLS = frozenset(
    (
        WORKFLOW,
        "scripts/qualify_release_package.py",
        "scripts/release_qualification/alpha3_recovery.py",
    )
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


@dataclass(frozen=True, slots=True)
class RecoveryBinding:
    """Separately authenticated verifier; never an arbitrary producer override."""

    verifier_commit: str
    verifier_tree: str
    tool_files: tuple[tuple[str, str], ...]
    target: ReleaseTarget = ALPHA3_TARGET

    def __post_init__(self) -> None:
        _require(
            all(
                isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value)
                for value in (self.verifier_commit, self.verifier_tree)
            )
            and isinstance(self.target, ReleaseTarget)
            and self.verifier_commit != self.target.source_commit
            and self.verifier_tree != self.target.source_tree,
            "Invalid or conflated recovery verifier identity.",
        )
        _require(
            type(self.tool_files) is tuple and 3 <= len(self.tool_files) <= 256,
            "Invalid recovery tooling inventory.",
        )
        names = []
        for item in self.tool_files:
            _require(type(item) is tuple and len(item) == 2, "Invalid recovery tool entry.")
            name, digest = item
            _require(
                isinstance(name, str)
                and str(PurePosixPath(name)) == name
                and ".." not in PurePosixPath(name).parts
                and (name == WORKFLOW or (name.startswith("scripts/") and name.endswith(".py")))
                and isinstance(digest, str)
                and re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
                "Invalid recovery tool path or digest.",
            )
            names.append(name)
        _require(
            names == sorted(set(names)) and set(names) >= REQUIRED_TOOLS,
            "Missing, duplicate or unordered recovery tools.",
        )

    def require_producer(self, commit: str, tree: str, publisher: str | None = None) -> None:
        """Admit only the separately selected producer and its first publisher."""
        _require(
            (commit, tree, self.target.publisher_run if publisher is None else publisher)
            == (self.target.source_commit, self.target.source_tree, self.target.publisher_run),
            "Recovery must preserve the exact selected producer and publisher.",
        )

    def to_dict(self) -> dict[str, Any]:
        """Canonical JSON-compatible verifier evidence, separate from the producer."""
        result: dict[str, Any] = {
            "policy": POLICY,
            "verifier_commit": self.verifier_commit,
            "verifier_tree": self.verifier_tree,
            "tool_files": [{"path": name, "sha256": digest} for name, digest in self.tool_files],
        }
        if self.target != ALPHA3_TARGET:
            result["producer_target"] = self.target.to_dict()
        return result


def verify_tool_origins(verifier: Path, modules: dict[str, Any], committed: dict[str, str]) -> None:
    """Reject qualification imports from the producer or an ambient installation."""
    root = verifier.resolve()
    for name, module in tuple(modules.items()):
        if (name != "scripts" and not name.startswith("scripts.")) or module is None:
            continue
        module_path = name.replace(".", "/")
        filename = getattr(module, "__file__", None)
        if filename is None:
            locations = getattr(getattr(module, "__spec__", None), "submodule_search_locations", ())
            _require(
                bool(locations)
                and len(locations) == 1
                and all(Path(location).resolve() == root / module_path for location in locations)
                and module_path + "/__init__.py" not in committed
                and any(path.startswith(module_path + "/") for path in committed),
                "Recovery tooling namespace origin mismatch.",
            )
            continue
        origin = getattr(getattr(module, "__spec__", None), "origin", None)
        if not isinstance(filename, str) or not isinstance(origin, str):
            raise ValueError("Recovery tool origin is missing.")
        _require(
            Path(filename).resolve().is_relative_to(root)
            and Path(origin).resolve() == Path(filename).resolve(),
            "Recovery tool import origin mismatch.",
        )
        path = Path(filename)
        relative = path.resolve().relative_to(root).as_posix()
        _require(
            relative in (module_path + ".py", module_path + "/__init__.py")
            and relative in committed
            and not path.is_symlink()
            and path.is_file()
            and 0 < path.stat().st_size <= 1_048_576,
            "Recovery loaded tool is not committed source.",
        )
        _require(
            hashlib.sha256(path.read_bytes()).hexdigest() == committed[relative],
            "Recovery loaded tool differs from the selected verifier tree.",
        )


def checkout_binding(
    source: Path, verifier: Path, commit: str, tree: str, *, target: ReleaseTarget = ALPHA3_TARGET
) -> RecoveryBinding:
    """Bind disjoint clean producer/verifier checkouts and committed tool bytes."""
    for path in (source, verifier):
        _require(
            not path.is_symlink() and path.is_dir(),
            "Recovery checkout must be a regular directory.",
        )
    source, verifier = source.resolve(), verifier.resolve()
    _require(
        not source.is_relative_to(verifier) and not verifier.is_relative_to(source),
        "Recovery checkouts must not overlap.",
    )
    for root, expected_commit, expected_tree in (
        (source, target.source_commit, target.source_tree),
        (verifier, commit, tree),
    ):
        _require(
            bundle._git_value(root, "HEAD") == expected_commit
            and bundle._git_value(root, "HEAD^{tree}") == expected_tree
            and not installed._git_value(root, "status", "--porcelain", "--untracked-files=all"),
            "Recovery checkout commit, tree or cleanliness mismatch.",
        )
    _require(
        Path(__file__).resolve().is_relative_to(verifier),
        "Recovery module is not from the verifier.",
    )
    committed = bundle._git_tree_file_digests(verifier)
    names = sorted(
        name
        for name in committed
        if name == WORKFLOW or (name.startswith("scripts/") and name.endswith(".py"))
    )
    _require(
        set(names) >= REQUIRED_TOOLS and len(names) <= 256,
        "Recovery committed tool inventory is incomplete or exceeds its bound.",
    )
    observed = []
    for name in names:
        path = verifier / name
        _require(
            not path.is_symlink()
            and path.is_file()
            and path.resolve().is_relative_to(verifier)
            and 0 < path.stat().st_size <= 1_048_576,
            "Recovery tool is missing, unsafe or exceeds its bound.",
        )
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        _require(
            digest == committed[name], "Recovery tool differs from the selected verifier tree."
        )
        observed.append((name, digest))
    verify_tool_origins(verifier, sys.modules, committed)
    for root, expected in ((source, target.source_commit), (verifier, commit)):
        _require(
            bundle._git_value(root, "HEAD") == expected
            and not installed._git_value(root, "status", "--porcelain", "--untracked-files=all"),
            "Recovery checkout changed during admission.",
        )
    return RecoveryBinding(commit, tree, tuple(observed), target=target)
