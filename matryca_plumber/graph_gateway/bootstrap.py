"""Standard-library bootstrap for the experimental one-shot gateway."""

from __future__ import annotations

import contextlib
import importlib.metadata
import io
import platform
import re
import sys
from collections.abc import Sequence
from typing import Literal

ErrorCode = Literal[
    "usage",
    "expectation_mismatch",
    "source_rejected",
    "bounds_exceeded",
    "source_changed",
    "unsupported_platform",
    "unsupported_dependency",
    "audit_hook_unavailable",
    "internal",
]
ERROR_EXITS: dict[ErrorCode, int] = {
    "usage": 2,
    "expectation_mismatch": 3,
    "source_rejected": 4,
    "bounds_exceeded": 5,
    "source_changed": 6,
    "unsupported_platform": 7,
    "unsupported_dependency": 8,
    "audit_hook_unavailable": 9,
    "internal": 70,
}
DENIED_EVENTS = (
    "subprocess.Popen",
    "os.fork",
    "os.forkpty",
    "os.posix_spawn",
    "os.spawn",
    "os.exec",
    "os.system",
    "socket.__new__",
    "socket.connect",
    "socket.bind",
    "socket.sendto",
    "socket.sendmsg",
    "socket.getaddrinfo",
)


class GatewayError(ValueError):
    """Carry only a declared, sanitized rejection code."""

    def __init__(self, code: ErrorCode) -> None:
        super().__init__(code)
        self.code = code


class _RejectedOutput(io.TextIOBase):
    """Reject internal stream output before the complete response is admitted."""

    def __init__(self) -> None:
        super().__init__()
        self.emitted = False

    def write(self, data: str) -> int:
        if data:
            self.emitted = True
            raise GatewayError("internal")
        return 0


def _install_audit_hook() -> bool:
    """Establish tested event rejection, not an operating-system sandbox."""
    nonce = object()
    observed = False

    def reject(event: str, arguments: tuple[object, ...]) -> None:
        nonlocal observed
        if event in DENIED_EVENTS:
            raise PermissionError("Gateway audit event rejected.")
        if event == "matryca_plumber.graph_gateway.selfcheck":
            observed = len(arguments) == 1 and arguments[0] is nonce

    try:
        sys.addaudithook(reject)
        sys.audit("matryca_plumber.graph_gateway.selfcheck", nonce)
    except Exception:
        return False
    return observed


def _parse_arguments(arguments: Sequence[str]) -> tuple[str, str | None, str | None]:
    """Accept only an explicit snapshot or a graph-free descriptor request."""
    if list(arguments) == ["describe"]:
        return "describe", None, None
    if len(arguments) != 5 or arguments[0] != "snapshot":
        raise GatewayError("usage")
    values: dict[str, str] = {}
    for offset in (1, 3):
        flag, value = arguments[offset], arguments[offset + 1]
        if (
            flag not in {"--graph-root", "--expect-descriptor-sha256"}
            or flag in values
            or not isinstance(value, str)
            or not value
            or "\x00" in value
            or value.startswith("--")
        ):
            raise GatewayError("usage")
        values[flag] = value
    if set(values) != {"--graph-root", "--expect-descriptor-sha256"} or not re.fullmatch(
        r"[0-9a-f]{64}", values["--expect-descriptor-sha256"]
    ):
        raise GatewayError("usage")
    return "snapshot", values["--graph-root"], values["--expect-descriptor-sha256"]


def _admit_platform(system: str, machine: str, python: tuple[int, int]) -> None:
    """Refuse every runtime outside the planned, still-unqualified matrix."""
    if (system, machine) not in {("Linux", "x86_64"), ("Darwin", "arm64")} or python not in {
        (3, 12),
        (3, 13),
    }:
        raise GatewayError("unsupported_platform")


def _admit_dependencies(plumber: str, parser: str) -> None:
    """Admit exact metadata only; byte authentication belongs to installed verification."""
    if (
        not isinstance(plumber, str)
        or len(plumber) > 128
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.!+_-]*", plumber) is None
        or parser != "1.9.0"
    ):
        raise GatewayError("unsupported_dependency")


def main(arguments: Sequence[str] | None = None) -> int:
    """Emit one complete response only after bootstrap and source admission."""
    try:
        if not _install_audit_hook():
            raise GatewayError("audit_hook_unavailable")
        command, root, expected = _parse_arguments(sys.argv[1:] if arguments is None else arguments)
        _admit_platform(platform.system(), platform.machine(), sys.version_info[:2])
        rejected_output = _RejectedOutput()
        with (
            contextlib.redirect_stdout(rejected_output),
            contextlib.redirect_stderr(rejected_output),
        ):
            from .profile import _load_descriptor
            from .wire import _encode

            profile = _load_descriptor(expected)
            try:
                plumber = importlib.metadata.version("matryca-plumber")
                parser = importlib.metadata.version("logseq-matryca-parser")
            except importlib.metadata.PackageNotFoundError:
                raise GatewayError("unsupported_dependency") from None
            _admit_dependencies(plumber, parser)
            if command == "describe":
                document = {
                    "descriptor": profile.document,
                    "descriptor_sha256": profile.descriptor_sha256,
                }
            else:
                from pathlib import Path

                from .runtime import _snapshot

                if root is None:
                    raise GatewayError("usage")
                document = _snapshot(
                    Path(root),
                    profile,
                    {"plumber": plumber, "parser": parser, "python": platform.python_version()},
                )
            payload = _encode(document)
            if rejected_output.emitted:
                raise GatewayError("internal")
        if sys.stdout.buffer.write(payload) != len(payload):
            raise GatewayError("internal")
        return 0
    except GatewayError as error:
        code = error.code
    except Exception:
        code = "internal"
    try:
        sys.stderr.buffer.write(b'{"error":"' + code.encode("ascii") + b'"}\n')
    except OSError:
        return ERROR_EXITS["internal"]
    return ERROR_EXITS[code]
