#!/usr/bin/env python3
"""Assemble SYSTEM_PROMPT.md from docs/openspec/agent/ fragments."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "docs" / "openspec" / "agent"
ORDER_FILE = AGENT_DIR / "_assembly_order.txt"
OUTPUT = ROOT / "SYSTEM_PROMPT.md"
GENERATED_BANNER = "<!-- GENERATED — do not edit -->"
BUILD_HASH_RE = re.compile(r"<!-- build-hash: ([a-f0-9]{64}) -->")


def listed_fragment_names(order_file: Path = ORDER_FILE) -> set[str]:
    if not order_file.is_file():
        return set()
    names: set[str] = set()
    for raw in order_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            names.add(line)
    return names


def unlisted_fragment_paths(
    *,
    agent_dir: Path = AGENT_DIR,
    order_file: Path = ORDER_FILE,
) -> list[Path]:
    """Return ``*.md`` files in agent_dir that are not listed in order_file."""
    listed = listed_fragment_names(order_file)
    on_disk = {path.name for path in agent_dir.glob("*.md")}
    return sorted(agent_dir / name for name in on_disk - listed)


def assert_no_unlisted_fragments(
    *,
    agent_dir: Path = AGENT_DIR,
    order_file: Path = ORDER_FILE,
) -> None:
    unlisted = unlisted_fragment_paths(agent_dir=agent_dir, order_file=order_file)
    if not unlisted:
        return
    names = "\n".join(f"  {path.name}" for path in unlisted)
    try:
        rel_order = order_file.relative_to(ROOT)
    except ValueError:
        rel_order = order_file
    msg = f"Fragments not listed in {rel_order}:\n{names}"
    raise SystemExit(msg)


def fragment_paths() -> list[Path]:
    assert_no_unlisted_fragments()
    if not ORDER_FILE.is_file():
        msg = f"Missing assembly order file: {ORDER_FILE}"
        raise SystemExit(msg)
    paths: list[Path] = []
    for raw in ORDER_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        path = AGENT_DIR / line
        if not path.is_file():
            msg = f"Fragment not found: {path.relative_to(ROOT)}"
            raise SystemExit(msg)
        paths.append(path)
    if not paths:
        msg = f"No fragments listed in {ORDER_FILE.relative_to(ROOT)}"
        raise SystemExit(msg)
    return paths


def compute_source_hash(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.read_bytes())
    return digest.hexdigest()


def strip_frontmatter(text: str) -> str:
    """Remove an OKF YAML frontmatter block from a prompt fragment."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    try:
        end = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration:
        return text
    return "\n".join(lines[end + 1 :])


def assemble_document(*, version: str | None = None) -> str:
    paths = fragment_paths()
    source_hash = compute_source_hash(paths)
    parts = [GENERATED_BANNER, f"<!-- build-hash: {source_hash} -->"]
    if version:
        parts.append(f"<!-- package-version: v{version} -->")
    parts.append("")
    parts.extend(
        strip_frontmatter(fragment.read_text(encoding="utf-8")).strip()
        for fragment in paths
    )
    return "\n\n".join(parts).rstrip() + "\n"


def pyproject_version() -> str:
    import re as re_mod

    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re_mod.search(r'^version\s*=\s*"([^"]+)"', text, re_mod.MULTILINE)
    if match is None:
        msg = "Could not parse version from pyproject.toml"
        raise SystemExit(msg)
    return match.group(1)


def write_output(content: str) -> None:
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")


def check_output() -> None:
    paths = fragment_paths()
    expected_hash = compute_source_hash(paths)
    if not OUTPUT.is_file():
        msg = f"{OUTPUT.relative_to(ROOT)} is missing — run: make build-system-prompt"
        raise SystemExit(msg)
    content = OUTPUT.read_text(encoding="utf-8")
    if GENERATED_BANNER not in content:
        msg = f"{OUTPUT.relative_to(ROOT)} missing banner {GENERATED_BANNER!r}"
        raise SystemExit(msg)
    match = BUILD_HASH_RE.search(content)
    if match is None:
        msg = f"{OUTPUT.relative_to(ROOT)} missing <!-- build-hash: ... --> comment"
        raise SystemExit(msg)
    if match.group(1) != expected_hash:
        msg = (
            f"{OUTPUT.relative_to(ROOT)} build-hash drift: expected {expected_hash}, "
            f"found {match.group(1)} — run: make build-system-prompt"
        )
        raise SystemExit(msg)
    print(f"system prompt OK (build-hash {expected_hash[:12]}…)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify SYSTEM_PROMPT.md matches fragment source hash (no write)",
    )
    args = parser.parse_args()
    if args.check:
        check_output()
        return
    version = pyproject_version()
    write_output(assemble_document(version=version))


if __name__ == "__main__":
    main()
