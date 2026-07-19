"""Deterministic A-CLI-01 pathological page generator (privacy-clean).

Expands a compact zlib seed captured from the structural synthetic twin of the
beta-soak culprit page (text tokenized; indent / properties / fences / wiki
punctuation preserved). The seed is not operator vault content.

See GitHub issue #297 (matryca-plumber) and the matching upstream parser report.
"""

from __future__ import annotations

import hashlib
import zlib
from pathlib import Path

# sha256 of the expanded UTF-8 page (stable contract for tests / upstream).
PATHOLOGICAL_PAGE_SHA256 = "4c2b1e87367d2b7b9c16ee62441f05c21c46c86c954703c5f7892789ca148a5d"
PATHOLOGICAL_PAGE_LINE_COUNT = 1148
PATHOLOGICAL_PAGE_BYTE_COUNT = 67321

_SEED = Path(__file__).resolve().parent / "fixtures" / "a_cli_01" / "pathological_page.md.zlib"


def generate_pathological_page() -> str:
    """Return the deterministic pathological Markdown page (UTF-8 text)."""
    raw = zlib.decompress(_SEED.read_bytes())
    text = raw.decode("utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if digest != PATHOLOGICAL_PAGE_SHA256:
        msg = f"A-CLI-01 seed hash mismatch: got {digest}, expected {PATHOLOGICAL_PAGE_SHA256}"
        raise RuntimeError(msg)
    return text


def generate_control_page(*, line_count: int = PATHOLOGICAL_PAGE_LINE_COUNT) -> str:
    """Return a same-scale outline that must parse well under a healthy budget.

    Nested bullets + properties + wiki links + a short fenced block — without
    the broken/nested fence shape that triggers LogosParser pathology.
    """
    if line_count < 20:
        msg = f"line_count must be >= 20, got {line_count}"
        raise ValueError(msg)
    parts: list[str] = [
        "- control-root\n",
        "  id:: aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa\n",
        "  status:: active\n",
        "\t- intro [[ControlHub]]\n",
        "\t\t```markdown\n",
        "\t\ttok fence body line\n",
        "\t\t```\n",
    ]
    # Fill remaining lines with a shallow, well-formed outline.
    remaining = line_count - sum(p.count("\n") for p in parts)
    for i in range(max(0, remaining)):
        depth = i % 6
        parts.append("\t" * depth + f"- tok-{i} [[Page{i % 17}]]\n")
        if i % 40 == 0:
            parts.append("\t" * depth + f"  propkey:: synth_val_{i}\n")
            remaining -= 1
    text = "".join(parts)
    # Trim or pad to exact line_count for stable comparisons.
    lines = text.splitlines()
    if len(lines) > line_count:
        lines = lines[:line_count]
    while len(lines) < line_count:
        lines.append(f"- pad-{len(lines)}")
    return "\n".join(lines) + "\n"
