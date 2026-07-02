#!/usr/bin/env python3
"""Fail CI when graph markdown reads bypass the path sandbox helper."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = (
    REPO_ROOT / "src" / "graph",
    REPO_ROOT / "src" / "agent",
    REPO_ROOT / "src" / "rag",
    REPO_ROOT / "src" / "semantic",
)

# Files allowed to call Path.read_text directly (sandbox primitives or non-markdown I/O).
# Subset requires inline ``# sandbox-read-ok`` on each read_text line (line-stable marker).
_MARKER_READ_TEXT_ALLOWLIST = frozenset(
    {
        "src/agent/maintenance_daemon.py",
        "src/agent/daemon_process_lock.py",
    },
)

ALLOWLIST = frozenset(
    {
        "src/graph/path_sandbox.py",
        "src/graph/markdown_io.py",
        "src/agent/plumber_modules/property_hygiene.py",  # repo-local YAML rules
        "src/agent/maintenance_daemon.py",  # daemon pid/lock sidecars only (marker-gated)
        "src/agent/daemon_process_lock.py",  # pid/lock sidecars (marker-gated)
        "src/utils/bounded_json.py",
        "src/utils/config_paths.py",
        "src/utils/provision_l1.py",
        "src/utils/runtime_bootstrap.py",
        "src/cli/ui_server.py",
        "src/config.py",
    },
)

# maintenance_daemon.py: only reads tagged with this inline marker are allowlisted.
# Using a marker (instead of hardcoded line numbers) keeps the check stable when
# the daemon module is edited and lines shift.
_DAEMON_ALLOW_MARKER = "sandbox-read-ok"

_READ_TEXT_RE = re.compile(r"\.read_text\s*\(")


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def main() -> int:
    violations: list[str] = []
    for root in SCAN_ROOTS:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            rel = _rel(path)
            if rel in ALLOWLIST:
                if rel in _MARKER_READ_TEXT_ALLOWLIST:
                    lines = path.read_text(encoding="utf-8").splitlines()
                    for lineno, line in enumerate(lines, start=1):
                        if _DAEMON_ALLOW_MARKER in line:
                            continue
                        if _READ_TEXT_RE.search(line):
                            violations.append(f"{rel}:{lineno}: {line.strip()}")
                continue
            text = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if _READ_TEXT_RE.search(line):
                    violations.append(f"{rel}:{lineno}: {line.strip()}")

    if violations:
        print("Direct Path.read_text() on graph paths is forbidden outside the sandbox allowlist:")
        for item in violations:
            print(f"  - {item}")
        print(
            "Use read_graph_file_text() / read_graph_page_text() from path_sandbox / markdown_io."
        )
        return 1

    print("sandbox-read-check: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
