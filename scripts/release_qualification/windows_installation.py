"""Independent, bounded Windows installation authority; never provisions or executes."""

from __future__ import annotations

import hashlib
import json
import ntpath
import os
import re
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, BinaryIO

from scripts.release_qualification.bundle import BundleBinding

PROFILE = "windows-x64-console-nonrelocatable/v1"
JSON_LIMIT = 262_144
RECIPE_LIMIT = 1_048_576
EXECUTABLE_LIMIT = 67_108_864
LAUNCHER_LIMIT = 16_777_216
INSTALLER_SIZE = 42_417_456
SCRIPT_PAIRS = (
    ("matryca", "src.cli:main"),
    ("matryca-logseq-llm-wiki", "src.main:main"),
    ("matryca-plumber", "src.plumber_entry:main"),
)
_INSTALLER = {
    "name": "uv",
    "version": "0.12.19",
    "source_commit": "bea138450f0e620a4ce5765b0e38cff7b9f0799f",
    "archive_sha256": "6dbb02d79e419522f1c500f0adb1cddcff0cda7d59b0d66ea7f5e3b4a1b2f5f0",
    "executable_sha256": "f94eddb81f3addca6ef8f2361a70c3edde31adcbd1000a55fc6674306ae0b1e7",
    "admission_sha256": "67adfa8e8687d206eec738e7e4e455e59249bb0a42ef477d02d2e852f0aa5ce0",
}
_TEMPLATE = {
    "profile": PROFILE,
    "size": 45_056,
    "git_blob": "c6d3881fc6b7d3ef0c6d3c08d505ab2b4c0ad9c4",
    "sha256": "0447a4febf43fdd958e4236129d6050b1dad64c124c43355d557542b3229cae8",
}


def _object(value: object, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"Windows {label} fields are invalid.")
    return value


def _hex(value: object, length: int = 64) -> str:
    if not isinstance(value, str) or re.fullmatch(f"[0-9a-f]{{{length}}}", value) is None:
        raise ValueError("Windows authority digest or source identity is invalid.")
    return value


def _positive(value: object, maximum: int) -> int:
    if type(value) is not int or not 0 < value <= maximum:
        raise ValueError("Windows authority size is invalid.")
    return value


def _version(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"3\.12\.[0-9]+", value) is None:
        raise ValueError("Windows installation supports exact CPython 3.12 only.")
    return value


def _schema(value: object) -> None:
    if type(value) is not int or value != 1:
        raise ValueError("Windows authority schema version must be integer 1.")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Windows authority JSON contains duplicate keys.")
        value[key] = item
    return value


def _constant(_value: str) -> None:
    raise ValueError("Windows authority JSON contains a nonstandard constant.")


def _json(raw: bytes) -> object:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= JSON_LIMIT:
        raise ValueError("Windows authority JSON exceeds its bound or is empty.")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeError, RecursionError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("Windows authority JSON is malformed.") from error


def canonical_windows_interpreter_path(value: str) -> str:
    """Normalize only the explicitly admitted local-drive display spelling."""
    if not isinstance(value, str):
        raise ValueError("Windows interpreter path must be text.")
    if value.startswith("\\\\?\\"):
        value = value[4:]
    value = value.replace("/", "\\")
    if re.match(r"^[A-Za-z]:\\", value) is None:
        raise ValueError("Windows interpreter requires a local absolute drive path.")
    value = value[0].upper() + value[1:]
    try:
        encoded = value.encode("utf-8")
    except UnicodeError as error:
        raise ValueError("Windows interpreter path has invalid Unicode.") from error
    if not 1 <= len(encoded) <= 4096 or any(c in value for c in "\x00\r\n"):
        raise ValueError("Windows interpreter path exceeds its bound or contains controls.")
    components = value[3:].split("\\")
    for component in components:
        device = component.partition(".")[0].upper()
        if (
            not component
            or component in {".", ".."}
            or component.endswith((".", " "))
            or any(ord(c) < 32 or c in '<>:"|?*' for c in component)
            or device in {"CON", "PRN", "AUX", "NUL"}
            or re.fullmatch(r"(?:COM|LPT)[1-9¹²³]", device)
        ):
            raise ValueError("Windows interpreter path has an unsupported component.")
    if ntpath.normpath(value) != value:
        raise ValueError("Windows interpreter path is not canonical.")
    return value


def console_script_payload(name: str, target: str, *, interpreter_display_path: str) -> bytes:
    """Return the pinned complete UTF-8/LF script, including its trusted shebang."""
    if (name, target) not in SCRIPT_PAIRS:
        raise ValueError("Windows console-script pair is unsupported.")
    if canonical_windows_interpreter_path(interpreter_display_path) != interpreter_display_path:
        raise ValueError("Windows descriptor interpreter path must already be canonical.")
    module, function = target.split(":")
    return (
        f"#!{interpreter_display_path}\n# -*- coding: utf-8 -*-\nimport sys\n"
        f"from {module} import {function}\n"
        'if __name__ == "__main__":\n'
        '    if sys.argv[0].endswith("-script.pyw"):\n'
        "        sys.argv[0] = sys.argv[0][:-11]\n"
        '    elif sys.argv[0].endswith(".exe"):\n'
        "        sys.argv[0] = sys.argv[0][:-4]\n"
        f"    sys.exit({function}())\n"
    ).encode()


def reject_path_redirection(path: Path) -> None:
    """Inspect existing components before following any symlink or reparse point."""
    if ".." in path.parts:
        raise ValueError("Windows authority file path contains parent traversal.")
    absolute = path.absolute()
    for component in (*reversed(absolute.parents), absolute):
        info = component.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError(
                "Windows authority file path redirects through a link or reparse point."
            )


def _identity(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns


def authority_file_identity(path: Path) -> tuple[int, int, int, int, int]:
    """Retain an owned regular-file identity across the complete observation phase."""
    try:
        reject_path_redirection(path)
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("Windows authority identity is not a regular file.")
        return _identity(info)
    except OSError as error:
        raise ValueError("Windows authority file identity could not be verified.") from error


@contextmanager
def _authority_stream(path: Path, limit: int, expected_size: int | None) -> Iterator[BinaryIO]:
    try:
        reject_path_redirection(path)
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or not 0 <= before.st_size <= limit:
            raise ValueError("Windows authority file is not regular or exceeds its size limit.")
        if expected_size is not None and before.st_size != expected_size:
            raise ValueError("Windows authority file has the wrong exact size.")
        with path.open("rb") as stream:
            if _identity(os.fstat(stream.fileno())) != _identity(before):
                raise ValueError("Windows authority file identity changed before reading.")
            yield stream
            reject_path_redirection(path)
            if _identity(os.fstat(stream.fileno())) != _identity(before) or _identity(
                path.lstat()
            ) != _identity(before):
                raise ValueError("Windows authority file changed while reading.")
    except OSError as error:
        raise ValueError("Windows authority file could not be read safely.") from error


def read_authority_file(path: Path, *, limit: int, expected_size: int | None = None) -> bytes:
    with _authority_stream(path, limit, expected_size) as stream:
        data = stream.read(limit + 1)
        if len(data) != os.fstat(stream.fileno()).st_size or len(data) > limit:
            raise ValueError("Windows authority file changed or exceeds its read bound.")
        return data


def hash_authority_file(path: Path, *, limit: int, expected_size: int | None = None) -> str:
    with _authority_stream(path, limit, expected_size) as stream:
        digest = hashlib.sha256()
        total = 0
        while chunk := stream.read(min(65_536, limit + 1 - total)):
            total += len(chunk)
            if total > limit:
                raise ValueError("Windows authority file exceeds its streaming bound.")
            digest.update(chunk)
        if total != os.fstat(stream.fileno()).st_size:
            raise ValueError("Windows authority file changed during hashing.")
        return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class InstallerIdentity:
    name: str
    version: str
    source_commit: str
    archive_sha256: str
    executable_sha256: str
    admission_sha256: str


@dataclass(frozen=True, slots=True)
class TemplateIdentity:
    profile: str
    size: int
    git_blob: str
    sha256: str


@dataclass(frozen=True, slots=True)
class InterpreterIdentity:
    path_sha256: str
    executable_sha256: str
    implementation: str
    version: str


@dataclass(frozen=True, slots=True)
class ScriptIdentity:
    name: str
    target: str
    payload_sha256: str


@dataclass(frozen=True, slots=True)
class LauncherIdentity:
    name: str
    target: str
    payload_sha256: str
    launcher_size: int
    launcher_sha256: str


def _installer(value: object) -> InstallerIdentity:
    obj = _object(value, set(_INSTALLER), "installer")
    if any(type(obj[k]) is not type(v) or obj[k] != v for k, v in _INSTALLER.items()):
        raise ValueError("Windows installer differs from the admitted upstream identity.")
    return InstallerIdentity(**obj)


def _template(value: object) -> TemplateIdentity:
    obj = _object(value, set(_TEMPLATE), "template")
    if any(type(obj[k]) is not type(v) or obj[k] != v for k, v in _TEMPLATE.items()):
        raise ValueError("Windows template differs from the pinned profile.")
    return TemplateIdentity(**obj)


def _interpreter(value: object, *, with_path: bool) -> tuple[InterpreterIdentity, str | None]:
    fields = {"path_sha256", "executable_sha256", "implementation", "version"}
    obj = _object(value, fields | ({"path"} if with_path else set()), "interpreter")
    if obj["implementation"] != "CPython":
        raise ValueError("Windows interpreter implementation is unsupported.")
    identity = InterpreterIdentity(
        _hex(obj["path_sha256"]),
        _hex(obj["executable_sha256"]),
        "CPython",
        _version(obj["version"]),
    )
    path = obj.get("path")
    if with_path:
        if not isinstance(path, str) or canonical_windows_interpreter_path(path) != path:
            raise ValueError("Windows descriptor interpreter path is noncanonical.")
        if hashlib.sha256(path.encode("utf-8")).hexdigest() != identity.path_sha256:
            raise ValueError("Windows interpreter path digest differs from its display path.")
    return identity, path


def _scripts(
    value: object, *, proof: bool, path: str | None = None
) -> tuple[ScriptIdentity | LauncherIdentity, ...]:
    if not isinstance(value, list) or len(value) != len(SCRIPT_PAIRS):
        raise ValueError("Windows script inventory must contain exactly three entries.")
    result: list[ScriptIdentity | LauncherIdentity] = []
    for raw, (name, target) in zip(value, SCRIPT_PAIRS, strict=True):
        fields = {"name", "target", "payload_sha256"} | (
            {"launcher_size", "launcher_sha256"} if proof else set()
        )
        obj = _object(raw, fields, "script")
        if obj["name"] != name or obj["target"] != target:
            raise ValueError("Windows script pairs or order differ from the fixed recipe.")
        payload_hash = _hex(obj["payload_sha256"])
        if (
            path is not None
            and hashlib.sha256(
                console_script_payload(name, target, interpreter_display_path=path)
            ).hexdigest()
            != payload_hash
        ):
            raise ValueError("Windows complete script payload differs from its independent recipe.")
        if proof:
            result.append(
                LauncherIdentity(
                    name,
                    target,
                    payload_hash,
                    _positive(obj["launcher_size"], LAUNCHER_LIMIT),
                    _hex(obj["launcher_sha256"]),
                )
            )
        else:
            result.append(ScriptIdentity(name, target, payload_hash))
    return tuple(result)


@dataclass(frozen=True, slots=True)
class WindowsLauncherProof:
    schema_version: int
    profile: str
    descriptor_sha256: str
    installation_evidence_sha256: str
    installer: InstallerIdentity
    template: TemplateIdentity
    recipe_sha256: str
    interpreter: InterpreterIdentity
    scripts: tuple[LauncherIdentity, ...]

    @classmethod
    def from_dict(cls, value: object) -> WindowsLauncherProof:
        obj = _object(
            value,
            {
                "schema_version",
                "profile",
                "descriptor_sha256",
                "installation_evidence_sha256",
                "installer",
                "template",
                "recipe_sha256",
                "interpreter",
                "scripts",
            },
            "launcher proof",
        )
        _schema(obj["schema_version"])
        if obj["profile"] != PROFILE:
            raise ValueError("Windows launcher proof profile is unsupported.")
        interpreter, _ = _interpreter(obj["interpreter"], with_path=False)
        scripts = _scripts(obj["scripts"], proof=True)
        return cls(
            1,
            PROFILE,
            _hex(obj["descriptor_sha256"]),
            _hex(obj["installation_evidence_sha256"]),
            _installer(obj["installer"]),
            _template(obj["template"]),
            _hex(obj["recipe_sha256"]),
            interpreter,
            tuple(s for s in scripts if isinstance(s, LauncherIdentity)),
        )

    def to_dict(self) -> dict[str, Any]:
        if not isinstance(self.scripts, tuple) or any(
            not isinstance(script, LauncherIdentity) for script in self.scripts
        ):
            raise ValueError("Windows launcher proof scripts must be immutable typed identities.")
        value = asdict(self)
        value["scripts"] = [asdict(s) for s in self.scripts]
        self.from_dict(value)
        return value


@dataclass(frozen=True, slots=True)
class WindowsInstallationDescriptor:
    schema_version: int
    source_commit: str
    source_tree: str
    binding_sha256: str
    kind: str
    artifact_name: str
    artifact_size: int
    artifact_sha256: str
    installation_evidence_sha256: str
    installer: InstallerIdentity
    template: TemplateIdentity
    recipe_sha256: str
    interpreter: InterpreterIdentity
    interpreter_path: str
    scripts: tuple[ScriptIdentity, ...]
    descriptor_sha256: str

    @classmethod
    def from_bytes(cls, raw: bytes) -> WindowsInstallationDescriptor:
        obj = _object(
            _json(raw),
            {
                "schema_version",
                "source_commit",
                "source_tree",
                "binding_sha256",
                "kind",
                "artifact_name",
                "artifact_size",
                "artifact_sha256",
                "installation_evidence_sha256",
                "installer",
                "template",
                "recipe_sha256",
                "interpreter",
                "scripts",
            },
            "installation descriptor",
        )
        _schema(obj["schema_version"])
        name = obj["artifact_name"]
        if (
            obj["kind"] not in ("wheel", "sdist")
            or not isinstance(name, str)
            or not name
            or len(name) > 255
            or any(c in name for c in "/\\:\x00\r\n")
            or name in {".", ".."}
        ):
            raise ValueError("Windows original archive identity is invalid.")
        interpreter, path = _interpreter(obj["interpreter"], with_path=True)
        assert isinstance(path, str)
        scripts = _scripts(obj["scripts"], proof=False, path=path)
        return cls(
            1,
            _hex(obj["source_commit"], 40),
            _hex(obj["source_tree"], 40),
            _hex(obj["binding_sha256"]),
            obj["kind"],
            name,
            _positive(obj["artifact_size"], 512 * 1024 * 1024),
            _hex(obj["artifact_sha256"]),
            _hex(obj["installation_evidence_sha256"]),
            _installer(obj["installer"]),
            _template(obj["template"]),
            _hex(obj["recipe_sha256"]),
            interpreter,
            path,
            tuple(s for s in scripts if isinstance(s, ScriptIdentity)),
            hashlib.sha256(raw).hexdigest(),
        )

    def verify_binding(self, binding: BundleBinding, kind: str) -> None:
        if kind not in ("wheel", "sdist") or (
            self.source_commit,
            self.source_tree,
            self.binding_sha256,
            self.kind,
            self.artifact_name,
            self.artifact_size,
            self.artifact_sha256,
        ) != (
            binding.source_commit,
            binding.source_tree,
            hashlib.sha256(binding.to_json().encode()).hexdigest(),
            kind,
            getattr(binding, f"{kind}_name"),
            getattr(binding, f"{kind}_size"),
            getattr(binding, f"{kind}_sha256"),
        ):
            raise ValueError(
                "Windows descriptor differs from the bound source or original archive."
            )


@dataclass(frozen=True, slots=True)
class ExpectedWindowsInstallationBindings:
    schema_version: int
    source_commit: str
    source_tree: str
    binding_sha256: str
    targets: tuple[tuple[str, WindowsLauncherProof], ...]

    @classmethod
    def from_bytes(cls, raw: bytes) -> ExpectedWindowsInstallationBindings:
        obj = _object(
            _json(raw),
            {"schema_version", "source_commit", "source_tree", "binding_sha256", "targets"},
            "independent bindings",
        )
        _schema(obj["schema_version"])
        targets = _object(
            obj["targets"], {"windows-x64/wheel", "windows-x64/sdist"}, "independent targets"
        )
        return cls(
            1,
            _hex(obj["source_commit"], 40),
            _hex(obj["source_tree"], 40),
            _hex(obj["binding_sha256"]),
            tuple((key, WindowsLauncherProof.from_dict(targets[key])) for key in sorted(targets)),
        )

    def verify_binding(self, binding: BundleBinding) -> None:
        if (
            type(self.schema_version) is not int
            or self.schema_version != 1
            or (self.source_commit, self.source_tree, self.binding_sha256)
            != (
                binding.source_commit,
                binding.source_tree,
                hashlib.sha256(binding.to_json().encode()).hexdigest(),
            )
        ):
            raise ValueError("Windows independent expectations differ from the bound source.")
        if not isinstance(self.targets, tuple) or any(
            not isinstance(target, tuple) or len(target) != 2 for target in self.targets
        ):
            raise ValueError("Windows independent targets must be immutable typed pairs.")
        if tuple(k for k, _ in self.targets) != ("windows-x64/sdist", "windows-x64/wheel"):
            raise ValueError(
                "Windows independent expectation targets are incomplete or duplicated."
            )
        for _, proof in self.targets:
            if not isinstance(proof, WindowsLauncherProof):
                raise ValueError("Windows independent launcher proof is invalid.")
            proof.to_dict()

    def for_kind(self, kind: str) -> WindowsLauncherProof:
        if kind not in ("wheel", "sdist"):
            raise ValueError("Windows expected archive kind is unsupported.")
        return dict(self.targets)[f"windows-x64/{kind}"]


def _authenticated_json(path: Path, expected_sha256: str) -> bytes:
    expected = _hex(expected_sha256)
    raw = read_authority_file(path, limit=JSON_LIMIT)
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Windows authority bytes differ from the external authenticated digest.")
    return raw


def load_windows_installation_descriptor(
    path: Path, *, expected_sha256: str
) -> WindowsInstallationDescriptor:
    return WindowsInstallationDescriptor.from_bytes(_authenticated_json(path, expected_sha256))


def load_expected_windows_installation_bindings(
    path: Path, *, expected_sha256: str
) -> ExpectedWindowsInstallationBindings:
    return ExpectedWindowsInstallationBindings.from_bytes(
        _authenticated_json(path, expected_sha256)
    )
