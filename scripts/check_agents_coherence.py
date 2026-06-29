#!/usr/bin/env python3
"""Fail CI when AGENTS.md router, llms.txt mirrors, or doc paths drift."""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Paths that AGENTS.md must cite and that must exist on disk.
REQUIRED_DOC_PATHS: tuple[str, ...] = (
    "AGENTS.md",
    "SYSTEM_PROMPT.md",
    "llms.txt",
    ".well-known/llms.txt",
    "CONTRIBUTING.md",
    "docs/CLEAN_CODE_ARCHITECTURE.md",
    "docs/openspec/agent-onboarding.md",
    "docs/openspec/agent/_assembly_order.txt",
    "docs/openspec/agent/paradigm.md",
    "docs/openspec/llm-performance.md",
    "docs/openspec/logseq-paradigm.md",
)

CURSOR_RULES_DIR = ROOT / ".cursor" / "rules"

# Rules intentionally omitted from AGENTS.md index (with documented reason).
RULE_EXCLUSIONS: dict[str, str] = {}


def pyproject_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if match is None:
        msg = "Could not parse version from pyproject.toml"
        raise SystemExit(msg)
    return match.group(1)


def _fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def check_agents_file_exists() -> str:
    agents_path = ROOT / "AGENTS.md"
    if not agents_path.is_file():
        _fail("AGENTS.md is missing at repository root")
    return agents_path.read_text(encoding="utf-8")


def check_system_prompt_cited(agents_text: str) -> None:
    if "SYSTEM_PROMPT.md" not in agents_text:
        _fail("AGENTS.md must explicitly cite SYSTEM_PROMPT.md")


def check_required_paths_exist() -> None:
    for rel in REQUIRED_DOC_PATHS:
        path = ROOT / rel
        if not path.is_file():
            _fail(f"Required path missing: {rel}")


def check_llms_byte_identity() -> None:
    left = ROOT / "llms.txt"
    right = ROOT / ".well-known" / "llms.txt"
    if left.read_bytes() != right.read_bytes():
        left_hash = hashlib.sha256(left.read_bytes()).hexdigest()
        right_hash = hashlib.sha256(right.read_bytes()).hexdigest()
        _fail(
            "llms.txt and .well-known/llms.txt are not byte-identical "
            f"(sha256 {left_hash} vs {right_hash})"
        )


def check_agent_onboarding_version(version: str) -> None:
    path = ROOT / "docs" / "openspec" / "agent-onboarding.md"
    first_line = path.read_text(encoding="utf-8").splitlines()[0]
    expected = f"v{version}"
    if expected not in first_line:
        _fail(
            f"docs/openspec/agent-onboarding.md header must reference {expected!r}, "
            f"got: {first_line!r}"
        )


def check_cursor_rules_indexed(agents_text: str) -> None:
    if not CURSOR_RULES_DIR.is_dir():
        _fail(f"Missing Cursor rules directory: {CURSOR_RULES_DIR.relative_to(ROOT)}")
    for rule_path in sorted(CURSOR_RULES_DIR.glob("*.mdc")):
        name = rule_path.name
        if name in RULE_EXCLUSIONS:
            continue
        if name not in agents_text and name.replace(".mdc", "") not in agents_text:
            _fail(
                f"AGENTS.md must reference Cursor rule {name} "
                f"(or add to RULE_EXCLUSIONS in check_agents_coherence.py)"
            )


def main() -> None:
    agents_text = check_agents_file_exists()
    check_system_prompt_cited(agents_text)
    check_required_paths_exist()
    check_llms_byte_identity()
    version = pyproject_version()
    check_agent_onboarding_version(version)
    check_cursor_rules_indexed(agents_text)
    print("agents coherence OK")


if __name__ == "__main__":
    main()
