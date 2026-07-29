"""One-shot parser child for daemon multiprocessing parents.

``multiprocessing`` forbids daemon processes from creating child processes.
This module runs through :class:`subprocess.Popen`, so parsing remains
process-isolated and terminable when called by a daemon pool worker.
"""

from __future__ import annotations

import json
import struct
import sys
from typing import Any

from .bounded_page_parse import _parse_request_message

_HEADER_BYTES = 4


def _write_response(response: dict[str, Any]) -> None:
    """Write header then AST blob; parent checks header before decoding the AST."""
    blob = response.pop("blob", b"")
    if not isinstance(blob, bytes):
        blob = b""
    header = {**response, "blob_length": len(blob)}
    encoded_header = json.dumps(
        header,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("!I", len(encoded_header)))
    sys.stdout.buffer.write(encoded_header)
    sys.stdout.buffer.write(blob)
    sys.stdout.buffer.flush()


def main() -> int:
    """Read one local request and write one binary response without diagnostics."""
    try:
        raw = sys.stdin.buffer.read()
        request = json.loads(raw.decode("utf-8"))
        if not isinstance(request, dict):
            return 2
        _write_response(_parse_request_message(request))
    except Exception:  # noqa: BLE001 - never disclose local request content
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
