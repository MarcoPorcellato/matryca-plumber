#!/usr/bin/env python3
"""Write the A-CLI-01 pathological synthetic page (deterministic).

Usage::

    uv run python scripts/gen_a_cli_01_pathological_page.py /tmp/pathological.md

The page is privacy-clean (synthetic tokens only). Intended for upstream
``logseq-matryca-parser`` reproduction and local ``pytest -m slow`` probes.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.a_cli_01_generator import (  # noqa: E402
    PATHOLOGICAL_PAGE_SHA256,
    generate_pathological_page,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output",
        type=Path,
        help="Destination .md path (parent dirs created as needed)",
    )
    args = parser.parse_args()
    text = generate_pathological_page()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    print(
        f"Wrote {args.output} ({len(text.encode('utf-8'))} bytes, "
        f"{text.count(chr(10))} lines, sha256={digest})"
    )
    if digest != PATHOLOGICAL_PAGE_SHA256:
        raise SystemExit("hash contract broken")


if __name__ == "__main__":
    main()
