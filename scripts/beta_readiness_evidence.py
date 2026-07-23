#!/usr/bin/env python3
"""Executable wrapper for the private beta-evidence CLI."""

from beta_evidence.cli import main  # type: ignore[import-not-found]

if __name__ == "__main__":
    raise SystemExit(main())
