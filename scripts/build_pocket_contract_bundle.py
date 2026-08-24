#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from src.contracts.pocket.bundle import build_contract_bundle, verify_contract_bundle
from src.contracts.pocket.canonical import PocketContractError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or verify Pocket V1 contracts.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--source-dir", type=Path, required=True)
    build.add_argument("--output-dir", type=Path, required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--bundle-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        receipt = (
            build_contract_bundle(args.source_dir, args.output_dir)
            if args.command == "build"
            else verify_contract_bundle(args.bundle_dir)
        )
    except PocketContractError as error:
        print(error.code, file=sys.stderr)
        return 2
    print(json.dumps(asdict(receipt), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
