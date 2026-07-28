#!/usr/bin/env python3
"""Block publication of local code-audit graph and impact counts."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METRIC_RE = re.compile(
    r"(?:gitnexus|code[\s-]+audit)[^\n]{0,240}(?:"
    r"\b\d[\d,._]*\s+(?:symbols?|relationships?|execution\s+flows?|"
    r"process(?:es)?|modules?|callers?|nodes?|edges?|flows?|files?|"
    r"dependents?|cycles?|simboli|relazioni|processi|moduli|chiamanti|"
    r"nodi|archi|flussi?|file|dipendenti|cicli|cluster)\b"
    r"|\bd\s*=\s*\d+(?:\s*[→-]\s*\d+)?"
    r")",
    re.IGNORECASE,
)


def tracked_files() -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / raw.decode("utf-8") for raw in completed.stdout.split(b"\0") if raw]


def main() -> int:
    findings: list[str] = []
    for path in tracked_files():
        if not path.is_file() or path == Path(__file__).resolve():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if METRIC_RE.search(line):
                findings.append(f"{path.relative_to(ROOT)}:{line_number}")

    if findings:
        print("Public code-audit metrics are forbidden:", file=sys.stderr)
        for finding in findings:
            print(f"  {finding}", file=sys.stderr)
        return 1
    print("No public code-audit metrics found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
