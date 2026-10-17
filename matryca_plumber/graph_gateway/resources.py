"""Finite authentication of the installed OG profile's static resources."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from contextlib import suppress
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Any

from .profile import PROFILE_ID, SCHEMA_DIGESTS, _admit_descriptor

_RESOURCE_ROOT = "resources/og-v1"
_MAX_DOCUMENT_BYTES = 131_072
_MAX_RESOURCE_BYTES = 1_048_576
_MAX_RESOURCE_TOTAL = 8_388_608
_MAX_RESOURCE_FILES = 256
_MAX_MODULE_BYTES = 262_144
_SHA256 = re.compile(r"[0-9a-f]{64}")
_SCHEMA_PATHS = {
    "read": "schemas/plumber.graph.read.v1.json",
    "topology": "schemas/plumber.graph.topology.v1.json",
}
_PINNED_PATHS = {
    "dependency_profile": "dependency-profile.json",
    "requirements": "requirements-og-v1-parser-1.9.0.txt",
    "fixture_manifest": "fixture-manifest.json",
    "golden": "golden/topology.result.json",
    "tck_cases": "tck-cases.json",
}
_CODE_MODULE_PATHS = frozenset({"consumer.py", "tck.py"})


class PackageResourceError(ValueError):
    """A sanitized failure to authenticate the installed package resource tree."""

    def __init__(self) -> None:
        super().__init__("package_resource_rejected")


@dataclass(frozen=True, slots=True)
class PackageResources:
    """Authenticated immutable view of the bounded operational resource package."""

    descriptor: dict[str, Any]
    descriptor_bytes: bytes
    descriptor_sha256: str
    manifest: dict[str, Any]
    manifest_bytes: bytes
    manifest_sha256: str
    assets: dict[str, bytes]
    schema_digests: dict[str, str]
    schema_bytes: dict[str, bytes]
    module_bytes: dict[str, bytes]
    package_paths: frozenset[str]


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise PackageResourceError()
        value[key] = item
    return value


def _document(data: bytes, maximum: int) -> dict[str, Any]:
    if type(data) is not bytes or len(data) > maximum:
        raise PackageResourceError()
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise PackageResourceError() from None
    if type(value) is not dict:
        raise PackageResourceError()
    return value


def _canonical_name(name: str) -> bool:
    if (
        not name
        or "\\" in name
        or "\x00" in name
        or name.startswith("/")
        or name != str(PurePosixPath(name))
    ):
        return False
    return all(part not in {"", ".", ".."} for part in name.split("/"))


def _read_tree(root: Any) -> tuple[dict[str, bytes], frozenset[str]]:
    assets: dict[str, bytes] = {}
    package_paths: set[str] = set()
    total = 0

    def visit(directory: Any, prefix: str, depth: int) -> None:
        nonlocal total
        if depth > 5:
            raise PackageResourceError()
        try:
            children: list[Any] = []
            for child in directory.iterdir():
                if len(children) >= _MAX_RESOURCE_FILES + 16:
                    raise PackageResourceError()
                children.append(child)
            children.sort(key=lambda item: item.name)
        except (OSError, TypeError, ValueError):
            raise PackageResourceError() from None
        for child in children:
            name = f"{prefix}/{child.name}" if prefix else child.name
            if not _canonical_name(name) or getattr(child, "is_symlink", lambda: False)():
                raise PackageResourceError()
            full_name = f"{_RESOURCE_ROOT}/{name}"
            package_paths.add(full_name)
            if len(package_paths) > _MAX_RESOURCE_FILES + 16:
                raise PackageResourceError()
            try:
                is_directory = child.is_dir()
                is_regular_file = child.is_file()
                if is_directory:
                    visit(child, name, depth + 1)
                elif is_regular_file:
                    with child.open("rb") as handle:
                        content = handle.read(_MAX_RESOURCE_BYTES + 1)
                else:
                    raise PackageResourceError()
            except (OSError, TypeError, ValueError):
                raise PackageResourceError() from None
            if is_regular_file:
                if len(content) > _MAX_RESOURCE_BYTES:
                    raise PackageResourceError()
                total += len(content)
                if total > _MAX_RESOURCE_TOTAL:
                    raise PackageResourceError()
                assets[name] = content

    visit(root, "", 0)
    if len(assets) > _MAX_RESOURCE_FILES:
        raise PackageResourceError()
    return assets, frozenset(package_paths)


def _read_installed_module(package_root: Path, name: object) -> bytes:
    """Read one fixed, regular installed module without following links or blocking."""
    if (
        type(name) is not str
        or name not in _CODE_MODULE_PATHS
        or not _canonical_name(name)
        or PurePosixPath(name).is_absolute()
    ):
        raise PackageResourceError()
    path = package_root.joinpath(name)
    descriptor: int | None = None
    try:
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode):
            raise PackageResourceError()
        no_follow = getattr(os, "O_NOFOLLOW", None)
        if os.name != "posix" or no_follow is None:
            raise PackageResourceError()
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | no_follow)
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or (before.st_dev, before.st_ino) != (
            opened.st_dev,
            opened.st_ino,
        ):
            raise PackageResourceError()
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            content = handle.read(_MAX_MODULE_BYTES + 1)
        if len(content) > _MAX_MODULE_BYTES:
            raise PackageResourceError()
        return content
    except PackageResourceError:
        raise
    except (OSError, TypeError, ValueError):
        raise PackageResourceError() from None
    finally:
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)


def _verify_package_resources(
    descriptor_bytes: bytes,
    manifest_bytes: bytes,
    assets: dict[str, bytes],
    available: set[str] | frozenset[str],
    schema_bytes: dict[str, bytes],
    module_bytes: dict[str, bytes],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Verify exact namespace, duplicate-free manifests, descriptor pins and all bytes."""
    try:
        profile = _admit_descriptor(descriptor_bytes, None)
        descriptor = profile.document
        manifest = _document(manifest_bytes, _MAX_DOCUMENT_BYTES)
        if (
            set(manifest) != {"schema_version", "files"}
            or type(manifest["schema_version"]) is not int
            or manifest["schema_version"] != 1
        ):
            raise PackageResourceError()
        declared = manifest["files"]
        if type(declared) is not dict or not declared or set(declared) != set(assets):
            raise PackageResourceError()
        if any(
            not _canonical_name(name)
            or not isinstance(digest, str)
            or _SHA256.fullmatch(digest) is None
            for name, digest in declared.items()
        ):
            raise PackageResourceError()
        expected_paths = {
            f"{_RESOURCE_ROOT}/descriptor.json",
            f"{_RESOURCE_ROOT}/manifest.json",
        }
        for name in declared:
            expected_paths.add(f"{_RESOURCE_ROOT}/{name}")
            parent = PurePosixPath(name).parent
            while str(parent) != ".":
                expected_paths.add(f"{_RESOURCE_ROOT}/{parent}")
                parent = parent.parent
        if set(available) != expected_paths:
            raise PackageResourceError()
        if any(_digest(assets[name]) != digest for name, digest in declared.items()):
            raise PackageResourceError()
        resource_digests = descriptor["resource_digests"]
        if resource_digests["manifest"] != _digest(manifest_bytes):
            raise PackageResourceError()
        for key, path in _PINNED_PATHS.items():
            if path not in assets or _digest(assets[path]) != resource_digests[key]:
                raise PackageResourceError()
            if declared.get(path) != resource_digests[key]:
                raise PackageResourceError()
        dependency_profile = _document(assets[_PINNED_PATHS["dependency_profile"]], 131_072)
        if (
            set(dependency_profile)
            != {
                "export",
                "lock_sha256",
                "lock_source",
                "matrix",
                "parser",
                "profile_id",
                "project",
                "qualification",
                "requirements",
                "resolution",
            }
            or type(dependency_profile["export"]) is not dict
            or type(dependency_profile["matrix"]) is not list
            or type(dependency_profile["parser"]) is not dict
            or type(dependency_profile["project"]) is not dict
            or type(dependency_profile["requirements"]) is not dict
            or dependency_profile["profile_id"] != descriptor["dependencies"]["profile_id"]
            or dependency_profile["parser"]
            != {"name": "logseq-matryca-parser", "version": descriptor["dependencies"]["parser"]}
            or dependency_profile["matrix"] != descriptor["matrix"]
            or dependency_profile["qualification"] != "unqualified"
            or dependency_profile["lock_source"] != "uv.lock"
            or not isinstance(dependency_profile["lock_sha256"], str)
            or _SHA256.fullmatch(dependency_profile["lock_sha256"]) is None
            or dependency_profile["project"].get("name") != "matryca-plumber"
            or not isinstance(dependency_profile["project"].get("version"), str)
            or dependency_profile["export"].get("kind") != "uv-export-runtime-closure"
            or type(dependency_profile["export"].get("entry_count")) is not int
            or dependency_profile["export"]["entry_count"] <= 0
            or dependency_profile["requirements"]
            != {
                "path": _PINNED_PATHS["requirements"],
                "sha256": resource_digests["requirements"],
            }
            or not assets[_PINNED_PATHS["requirements"]].startswith(b"--require-hashes\n")
        ):
            raise PackageResourceError()
        if set(schema_bytes) != set(_SCHEMA_PATHS):
            raise PackageResourceError()
        for role, path in _SCHEMA_PATHS.items():
            digest = _digest(schema_bytes[role])
            if (
                assets.get(path) != schema_bytes[role]
                or declared.get(path) != digest
                or descriptor["schemas"][role] != digest
                or digest != SCHEMA_DIGESTS[role]
            ):
                raise PackageResourceError()
        code_modules = descriptor["code_modules"]
        expected_modules = {module["path"]: module["sha256"] for module in code_modules}
        if set(module_bytes) != set(expected_modules) or any(
            type(payload) is not bytes
            or len(payload) > _MAX_MODULE_BYTES
            or _digest(payload) != expected_modules[path]
            for path, payload in module_bytes.items()
        ):
            raise PackageResourceError()
        if descriptor["profile"] != PROFILE_ID:
            raise PackageResourceError()
        return descriptor, manifest
    except (KeyError, TypeError, ValueError):
        raise PackageResourceError() from None


def _load_package_resources() -> PackageResources:
    """Read, bound and authenticate the exact installed resources/og-v1 inventory."""
    try:
        package_root = files("matryca_plumber.graph_gateway")
        if not isinstance(package_root, Path) or not stat.S_ISDIR(package_root.lstat().st_mode):
            raise PackageResourceError()
        resources_root = package_root.joinpath("resources")
        if not stat.S_ISDIR(resources_root.lstat().st_mode):
            raise PackageResourceError()
        root = resources_root.joinpath("og-v1")
        if not stat.S_ISDIR(root.lstat().st_mode):
            raise PackageResourceError()
        tree, package_paths = _read_tree(root)
        descriptor_bytes = tree["descriptor.json"]
        manifest_bytes = tree["manifest.json"]
        descriptor_profile = _admit_descriptor(descriptor_bytes, None)
        descriptor = descriptor_profile.document
        manifest = _document(manifest_bytes, _MAX_DOCUMENT_BYTES)
        if type(manifest.get("files")) is not dict:
            raise PackageResourceError()
        asset_names = set(tree) - {"descriptor.json", "manifest.json"}
        if asset_names != set(manifest["files"]):
            raise PackageResourceError()
        assets = {name: tree[name] for name in asset_names}
        schema_bytes = {
            role: assets[path] for role, path in _SCHEMA_PATHS.items() if path in assets
        }
        module_bytes: dict[str, bytes] = {}
        for module in descriptor["code_modules"]:
            name = module["path"]
            module_bytes[name] = _read_installed_module(package_root, name)
        _verify_package_resources(
            descriptor_bytes,
            manifest_bytes,
            assets,
            package_paths,
            schema_bytes,
            module_bytes,
        )
        return PackageResources(
            descriptor=descriptor,
            descriptor_bytes=descriptor_bytes,
            descriptor_sha256=_digest(descriptor_bytes),
            manifest=manifest,
            manifest_bytes=manifest_bytes,
            manifest_sha256=_digest(manifest_bytes),
            assets=assets,
            schema_digests=dict(descriptor["schemas"]),
            schema_bytes=schema_bytes,
            module_bytes=module_bytes,
            package_paths=package_paths,
        )
    except PackageResourceError:
        raise
    except (OSError, KeyError, TypeError, ValueError, RecursionError):
        raise PackageResourceError() from None
