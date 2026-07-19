#!/usr/bin/env python3
"""Measure bounded page-parse worker overhead on a local vault (privacy-safe).

Writes aggregated timing only (no paths, titles, or content). Default corpus:
Caches soak/diag vault (~1009 pages). In-process LogosParser is used solely as
a measurement baseline — not as a production API path.

Usage::

    uv run python scripts/measure_bounded_page_parse_overhead.py
    uv run python scripts/measure_bounded_page_parse_overhead.py --limit 200
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from logseq_matryca_parser import LogosParser
from src.graph.bounded_page_parse import (
    BoundedPageParseWorker,
    reset_bounded_page_parse_worker_for_tests,
)


def _discover_vault() -> Path | None:
    bases = [
        Path.home() / "Library/Caches/mp-beta-soak-a5",
        Path.home() / "Library/Caches/mp-cli-diag-a5",
    ]
    best: tuple[int, Path] | None = None
    for base in bases:
        if not base.is_dir():
            continue
        for pages in base.rglob("pages"):
            if not pages.is_dir():
                continue
            n = len(list(pages.glob("*.md")))
            if n < 10:
                continue
            if best is None or n > best[0]:
                best = (n, pages.parent)
    return best[1] if best else None


def _pct(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    i = min(len(s) - 1, max(0, int(round((p / 100) * (len(s) - 1)))))
    return round(s[i], 6)


def _summarize(xs: list[float]) -> dict[str, float | int]:
    if not xs:
        return {"n": 0}
    return {
        "n": len(xs),
        "min": round(min(xs), 6),
        "p50": _pct(xs, 50),
        "p90": _pct(xs, 90),
        "p95": _pct(xs, 95),
        "p99": _pct(xs, 99),
        "max": round(max(xs), 6),
        "mean": round(statistics.mean(xs), 6),
        "sum": round(sum(xs), 6),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0, help="Max pages (0=all)")
    parser.add_argument(
        "--baseline-max-bytes",
        type=int,
        default=20_000,
        help="Only pages under this size get in-process baseline compare",
    )
    parser.add_argument(
        "--timeout-s",
        type=float,
        default=30.0,
        help="Per-page worker deadline for this measurement run",
    )
    args = parser.parse_args()

    vault = _discover_vault()
    if vault is None:
        raise SystemExit("no soak/diag vault found under Library/Caches")

    files: list[Path] = sorted((vault / "pages").glob("*.md"))
    journals = vault / "journals"
    if journals.is_dir():
        files.extend(sorted(journals.glob("*.md")))
    if args.limit > 0:
        files = files[: args.limit]

    worker = BoundedPageParseWorker()
    worker_times: list[float] = []
    baseline_times: list[float] = []
    paired_delta: list[float] = []
    timeouts = 0
    errors = 0
    cold_s: float | None = None

    try:
        for index, path in enumerate(files):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                errors += 1
                continue
            t0 = time.perf_counter()
            result = worker.parse_text(text, mode="logos", timeout_s=args.timeout_s)
            wall = time.perf_counter() - t0
            if index == 0:
                cold_s = round(wall, 6)
            if result.timed_out:
                timeouts += 1
                continue
            if not result.ok:
                errors += 1
                continue
            worker_times.append(wall)

            if len(text.encode("utf-8")) <= args.baseline_max_bytes:
                b0 = time.perf_counter()
                LogosParser().parse(text)
                bwall = time.perf_counter() - b0
                baseline_times.append(bwall)
                paired_delta.append(wall - bwall)
    finally:
        worker.shutdown()
        reset_bounded_page_parse_worker_for_tests()

    report = {
        "privacy": "aggregated_only_no_paths_titles_content",
        "page_files_considered": len(files),
        "timeout_s": args.timeout_s,
        "cold_first_parse_s": cold_s,
        "worker_wall_s": _summarize(worker_times),
        "inprocess_baseline_wall_s": _summarize(baseline_times),
        "worker_minus_baseline_s": _summarize(paired_delta),
        "timeouts": timeouts,
        "errors": errors,
        "note": (
            "In-process baseline is measurement-only. Production PR2B API always "
            "uses the spawn worker (no unbounded LogosParser path)."
        ),
    }
    print(json.dumps(report, indent=2))

    out_dirs = [
        Path.home() / "Library/Caches/mp-beta-soak-a5/report",
        Path.home() / "Library/Application Support/mp-beta-soak-a5/latest/report",
    ]
    for d in out_dirs:
        try:
            d.mkdir(parents=True, exist_ok=True)
            (d / "A_CLI_01_BOUNDED_PARSE_OVERHEAD.json").write_text(
                json.dumps(report, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass


if __name__ == "__main__":
    main()
