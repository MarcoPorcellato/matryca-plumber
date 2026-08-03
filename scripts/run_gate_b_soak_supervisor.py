#!/usr/bin/env python3
"""Restart a Gate B collector only while its durable result is non-terminal."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

_RESULT_FILE = "soak-result.json"
_TERMINAL = frozenset({"PASS", "FAIL"})
_RETRY_EXIT = 75


def _terminal_status(output: Path) -> str | None:
    result = output / _RESULT_FILE
    if not result.exists():
        return None
    try:
        payload: object = json.loads(result.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("terminal_result_invalid") from exc
    if not isinstance(payload, dict) or payload.get("status") not in _TERMINAL:
        raise ValueError("terminal_result_invalid")
    return str(payload["status"])


def run_supervisor(
    output: Path,
    command: Sequence[str],
    *,
    command_runner: Callable[..., subprocess.CompletedProcess[Any]] = subprocess.run,
) -> int:
    try:
        if _terminal_status(output) is not None:
            return 0
    except ValueError:
        print("gate b supervisor: terminal_result_invalid", file=sys.stderr)
        return 0
    if not command:
        print("gate b supervisor: command_missing", file=sys.stderr)
        return 0
    try:
        completed = command_runner(list(command), check=False)
    except OSError:
        return _RETRY_EXIT
    try:
        if _terminal_status(output) is not None:
            return 0
    except ValueError:
        print("gate b supervisor: terminal_result_invalid", file=sys.stderr)
        return 0
    return _RETRY_EXIT if completed.returncode != 0 else _RETRY_EXIT


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    return run_supervisor(args.output, command)


if __name__ == "__main__":
    raise SystemExit(main())
