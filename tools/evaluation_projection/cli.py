"""Deterministic maintainer CLI for graph-outcome evaluation projections."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError
from src.memory.graph_outcome_harness import run_default_scenarios

from tools.evaluation_projection.atomic_output import AtomicOutputError, write_projection_bytes
from tools.evaluation_projection.privacy import ProjectionPrivacyError
from tools.evaluation_projection.projector import ProjectionEvidenceError, project_suite
from tools.evaluation_projection.provenance import SourceBindingError, resolve_source_binding
from tools.evaluation_projection.schema import canonical_suite_bytes

_SOURCE_BINDING_ERROR_CODES = {
    "source_repository_unavailable": "source_repository_unavailable",
    "source_head_detached": "source_head_detached",
    "source_tree_dirty": "source_tree_dirty",
    "source_revision_invalid": "source_revision_invalid",
    "source_revision_mismatch": "source_revision_mismatch",
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="project_graph_outcome_evidence")
    parser.add_argument("--source-revision")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def _write_error(code: str) -> None:
    print(f"evaluation_projection: {code}", file=sys.stderr)


def main(argv: Sequence[str] | None = None, *, repository_root: Path | None = None) -> int:
    """Project the fixed scenario suite to stdout or one atomically installed file."""
    args = _parser().parse_args(argv)
    root = repository_root or Path(__file__).resolve().parents[2]

    try:
        binding = resolve_source_binding(root, args.source_revision)
    except SourceBindingError as error:
        _write_error(_SOURCE_BINDING_ERROR_CODES.get(str(error), "source_repository_unavailable"))
        return 3

    try:
        default_run = run_default_scenarios()
        suite = project_suite(default_run.episodes, source_revision=binding.revision)
        payload = canonical_suite_bytes(suite)
    except (ProjectionEvidenceError, ProjectionPrivacyError, ValidationError, ValueError):
        _write_error("evidence_rejected")
        return 4

    if args.output is None:
        try:
            if sys.stdout.buffer.write(payload) != len(payload):
                raise OSError
            sys.stdout.buffer.flush()
        except OSError:
            _write_error("output_failed")
            return 6
        return 0

    try:
        write_projection_bytes(args.output, payload, overwrite=args.overwrite)
    except AtomicOutputError as error:
        _write_error(error.code)
        return 5 if error.code == "output_exists" else 6
    except OSError:
        _write_error("output_failed")
        return 6
    return 0


__all__ = ["main"]
