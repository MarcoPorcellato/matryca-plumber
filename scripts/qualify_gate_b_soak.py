#!/usr/bin/env python3
"""Run a resumable Gate B soak against an installed public RC wheel."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Literal, cast

from beta_evidence.core import EvidenceError, _atomic_write_json, _is_within
from beta_evidence.soak import collect_soak
from beta_evidence.wheel import _copy_vault_without_cache

Profile = Literal["default-on", "read-only-external"]

_PROFILE_FILE = "gate-b-profile.json"
_PROFILE_SCHEMA_VERSION = 1
_PROFILES: tuple[Profile, ...] = ("default-on", "read-only-external")

_DEFAULT_ON_PROBE = r"""
import hashlib
import json
import os
import re
import resource
import sqlite3
import sys
from pathlib import Path

from src.shadow.bootstrap import (
    ensure_shadow_runtime_at_startup,
    handle_shadow_watchdog_change,
    rebuild_shadow_from_graph,
    reset_shadow_bootstrap_checked_for_tests,
)
from src.shadow.cache_location import resolve_shadow_cache_location
from src.shadow.config import shadow_db_enabled
from src.shadow.connection import open_shadow_db
from src.shadow.health import ShadowHealthState, resolve_shadow_health
from src.shadow.meta import (
    META_INDEXED_PAGE_COUNT,
    META_LAST_SYNC_ERROR,
    META_QUARANTINED_PAGE_COUNT,
    META_SOURCE_PAGE_COUNT,
    get_meta,
    set_meta,
)
from src.shadow.query import search_blocks_fts
from src.shadow.subtree import SubtreeStatus, query_subtree_by_block_uuid

graph = Path(os.environ["LOGSEQ_GRAPH_PATH"])
cache_root = Path(os.environ["MATRYCA_CACHE_PATH"])
cycle = int(os.environ["MATRYCA_SOAK_CYCLE"])
assert "MATRYCA_SHADOW_DB_ENABLED" not in os.environ
assert "MATRYCA_READ_ONLY" not in os.environ
assert shadow_db_enabled() is True
reset_shadow_bootstrap_checked_for_tests()
ensure_shadow_runtime_at_startup(graph)
assert resolve_shadow_health(graph) is ShadowHealthState.READY
location = resolve_shadow_cache_location(graph)
assert location.database_path.is_relative_to(cache_root)
assert not location.database_path.is_relative_to(graph)

fixture = graph / "pages" / ".matryca_gate_b_fixture.md"
renamed = fixture.with_name(".matryca_gate_b_fixture_renamed.md")
fixture.write_text(
    "- matrycagatebuniquetoken parent\n"
    "  id:: 3a333333-3333-4333-8333-333333333333\n"
    "  - matrycagatebuniquetoken child\n"
    "    id:: 4a444444-4444-4444-8444-444444444444\n",
    encoding="utf-8",
)
try:
    handle_shadow_watchdog_change(graph, fixture, "created")
    with open_shadow_db(graph) as connection:
        assert search_blocks_fts(connection, "matrycagatebuniquetoken", limit=2)
        subtree = query_subtree_by_block_uuid(
            connection, "3a333333-3333-4333-8333-333333333333", max_depth=1
        )
        assert subtree.status is SubtreeStatus.TRUNCATED
        assert len(subtree.nodes) == 1
    fixture.rename(renamed)
    handle_shadow_watchdog_change(graph, renamed, "created")
    with open_shadow_db(graph) as connection:
        assert connection.execute(
            "SELECT 1 FROM pages WHERE file_path=?",
            ("pages/.matryca_gate_b_fixture.md",),
        ).fetchone() is None
        assert connection.execute(
            "SELECT 1 FROM pages WHERE file_path=?",
            ("pages/.matryca_gate_b_fixture_renamed.md",),
        ).fetchone() is not None
finally:
    fixture.unlink(missing_ok=True)
    renamed.unlink(missing_ok=True)
    handle_shadow_watchdog_change(graph, renamed, "deleted")

if cycle % 12 == 0:
    with open_shadow_db(graph) as connection:
        set_meta(connection, META_LAST_SYNC_ERROR, "controlled recovery")
        connection.commit()
    assert resolve_shadow_health(graph) is ShadowHealthState.ERROR
    rebuild_shadow_from_graph(graph)
    assert resolve_shadow_health(graph) is ShadowHealthState.READY

with open_shadow_db(graph) as connection:
    source_count = int(get_meta(connection, META_SOURCE_PAGE_COUNT) or "0")
    indexed_count = int(get_meta(connection, META_INDEXED_PAGE_COUNT) or "0")
    quarantined_count = int(get_meta(connection, META_QUARANTINED_PAGE_COUNT) or "0")
    assert source_count == indexed_count + quarantined_count

def cache_digest(root):
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }

before_opt_out = cache_digest(cache_root)
os.environ["MATRYCA_SHADOW_DB_ENABLED"] = "false"
reset_shadow_bootstrap_checked_for_tests()
assert shadow_db_enabled() is False
assert resolve_shadow_health(graph) is ShadowHealthState.DISABLED
ensure_shadow_runtime_at_startup(graph)
assert cache_digest(cache_root) == before_opt_out
os.environ.pop("MATRYCA_SHADOW_DB_ENABLED")
reset_shadow_bootstrap_checked_for_tests()
ensure_shadow_runtime_at_startup(graph)
assert resolve_shadow_health(graph) is ShadowHealthState.READY

rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
if sys.platform == "darwin":
    rss //= 1024
print(json.dumps({
    "flag_off": True,
    "flag_on": True,
    "restart_health": True,
    "fts": True,
    "recovery": True,
    "subtree": "PASS",
    "synthetic_crud": "PASS",
    "source_count": source_count,
    "indexed_count": indexed_count,
    "quarantined_count": quarantined_count,
    "rss_kib": int(rss),
}, sort_keys=True))
"""

_READ_ONLY_PROBE = r"""
import hashlib
import json
import os
import re
import resource
import sys
from pathlib import Path

from src.shadow.bootstrap import (
    ensure_shadow_runtime_at_startup,
    rebuild_shadow_from_graph,
    reset_shadow_bootstrap_checked_for_tests,
)
from src.shadow.cache_location import resolve_shadow_cache_location
from src.shadow.config import shadow_db_enabled
from src.shadow.connection import open_shadow_db
from src.shadow.health import ShadowHealthState, resolve_shadow_health
from src.shadow.meta import (
    META_INDEXED_PAGE_COUNT,
    META_LAST_SYNC_ERROR,
    META_QUARANTINED_PAGE_COUNT,
    META_SOURCE_PAGE_COUNT,
    get_meta,
    set_meta,
)
from src.shadow.query import search_blocks_fts
from src.shadow.subtree import SubtreeStatus, query_subtree_by_block_uuid

graph = Path(os.environ["LOGSEQ_GRAPH_PATH"])
cache_root = Path(os.environ["MATRYCA_CACHE_PATH"])
cycle = int(os.environ["MATRYCA_SOAK_CYCLE"])
assert "MATRYCA_SHADOW_DB_ENABLED" not in os.environ
assert os.environ["MATRYCA_READ_ONLY"] == "true"
assert shadow_db_enabled() is True
reset_shadow_bootstrap_checked_for_tests()
ensure_shadow_runtime_at_startup(graph)
assert resolve_shadow_health(graph) is ShadowHealthState.READY
location = resolve_shadow_cache_location(graph)
assert location.database_path.is_relative_to(cache_root)
assert not location.database_path.is_relative_to(graph)

with open_shadow_db(graph) as connection:
    row = connection.execute(
        "SELECT block_uuid, content FROM blocks "
        "WHERE block_uuid IS NOT NULL AND content != '' LIMIT 100"
    ).fetchall()
    matched = False
    subtree_pass = False
    for block_uuid, content in row:
        for token in re.findall(r"[A-Za-z0-9]{4,}", content):
            if search_blocks_fts(connection, token, limit=5):
                matched = True
                break
        subtree = query_subtree_by_block_uuid(connection, block_uuid, max_depth=1)
        if subtree.status in {SubtreeStatus.COMPLETE, SubtreeStatus.TRUNCATED} and subtree.nodes:
            subtree_pass = True
        if matched and subtree_pass:
            break
    assert matched
    assert subtree_pass

if cycle % 12 == 0:
    with open_shadow_db(graph) as connection:
        set_meta(connection, META_LAST_SYNC_ERROR, "controlled recovery")
        connection.commit()
    assert resolve_shadow_health(graph) is ShadowHealthState.ERROR
    rebuild_shadow_from_graph(graph)
    assert resolve_shadow_health(graph) is ShadowHealthState.READY

with open_shadow_db(graph) as connection:
    source_count = int(get_meta(connection, META_SOURCE_PAGE_COUNT) or "0")
    indexed_count = int(get_meta(connection, META_INDEXED_PAGE_COUNT) or "0")
    quarantined_count = int(get_meta(connection, META_QUARANTINED_PAGE_COUNT) or "0")
    assert source_count == indexed_count + quarantined_count

def cache_digest(root):
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }

before_opt_out = cache_digest(cache_root)
os.environ["MATRYCA_SHADOW_DB_ENABLED"] = "false"
reset_shadow_bootstrap_checked_for_tests()
assert shadow_db_enabled() is False
assert resolve_shadow_health(graph) is ShadowHealthState.DISABLED
ensure_shadow_runtime_at_startup(graph)
assert cache_digest(cache_root) == before_opt_out
os.environ.pop("MATRYCA_SHADOW_DB_ENABLED")
reset_shadow_bootstrap_checked_for_tests()
ensure_shadow_runtime_at_startup(graph)
assert resolve_shadow_health(graph) is ShadowHealthState.READY

rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
if sys.platform == "darwin":
    rss //= 1024
print(json.dumps({
    "flag_off": True,
    "flag_on": True,
    "restart_health": True,
    "fts": True,
    "recovery": True,
    "subtree": "PASS",
    "synthetic_crud": "SKIPPED",
    "source_count": source_count,
    "indexed_count": indexed_count,
    "quarantined_count": quarantined_count,
    "rss_kib": int(rss),
}, sort_keys=True))
"""


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _graph_manifest_digest(root: Path) -> str:
    entries: dict[str, dict[str, str | int]] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        metadata = path.lstat()
        common: dict[str, str | int] = {"mode": stat.S_IMODE(metadata.st_mode)}
        if path.is_symlink():
            entries[relative] = {**common, "type": "symlink", "target": os.readlink(path)}
        elif path.is_dir():
            entries[relative] = {**common, "type": "directory"}
        elif path.is_file():
            payload = path.read_bytes()
            entries[relative] = {
                **common,
                "type": "file",
                "size": len(payload),
                "sha256": _sha256(payload),
            }
        else:
            entries[relative] = {**common, "type": "other"}
    encoded = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    return _sha256(encoded)


def _resolve_external_cache_root(
    cache_root: Path,
    *,
    source: Path,
    working: Path,
    output: Path,
    repo: Path,
) -> Path:
    resolved = cache_root.expanduser().resolve(strict=False)
    if resolved.exists() and resolved.is_symlink():
        raise EvidenceError("gate_b_cache_invalid")
    if any(
        _is_within(resolved, protected) or _is_within(protected, resolved)
        for protected in (source, working, output, repo)
    ):
        raise EvidenceError("gate_b_cache_unsafe")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _profile_path(output: Path) -> Path:
    return output / _PROFILE_FILE


def _profile_payload(profile: Profile, cache_root: Path) -> dict[str, object]:
    return {
        "schema_version": _PROFILE_SCHEMA_VERSION,
        "profile": profile,
        "cache_root_sha256": _sha256(str(cache_root).encode()),
        "graph_manifest_sha256": None,
    }


def _load_or_create_profile(output: Path, profile: Profile, cache_root: Path) -> dict[str, Any]:
    path = _profile_path(output)
    expected = _profile_payload(profile, cache_root)
    if not path.exists():
        output.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(path, expected)
        return expected
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceError("gate_b_profile_invalid") from exc
    if not isinstance(payload, dict):
        raise EvidenceError("gate_b_profile_invalid")
    if any(
        payload.get(key) != value
        for key, value in expected.items()
        if key != "graph_manifest_sha256"
    ):
        raise EvidenceError("gate_b_profile_mismatch")
    manifest = payload.get("graph_manifest_sha256")
    if manifest is not None and (not isinstance(manifest, str) or len(manifest) != 64):
        raise EvidenceError("gate_b_profile_invalid")
    return payload


def _bind_manifest(output: Path, profile: Profile, cache_root: Path, working: Path) -> None:
    payload = _load_or_create_profile(output, profile, cache_root)
    digest = _graph_manifest_digest(working)
    recorded = payload.get("graph_manifest_sha256")
    if recorded is not None and recorded != digest:
        raise EvidenceError("working_copy_changed")
    if recorded is None:
        payload["graph_manifest_sha256"] = digest
        _atomic_write_json(_profile_path(output), payload)


def _safe_environment(
    graph: Path, cache_root: Path, profile: Profile, cycle: int
) -> dict[str, str]:
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONNOUSERSITE": "1",
        "LOGSEQ_GRAPH_PATH": str(graph),
        "MATRYCA_CACHE_PATH": str(cache_root),
        "MATRYCA_PAGE_PARSE_TIMEOUT_S": "15",
        "MATRYCA_SOAK_CYCLE": str(cycle),
    }
    if profile == "read-only-external":
        environment["MATRYCA_READ_ONLY"] = "true"
    return environment


def _validate_payload(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise EvidenceError("probe_payload_invalid")
    required_true = ("flag_off", "flag_on", "restart_health", "fts", "recovery")
    if any(payload.get(name) is not True for name in required_true):
        raise EvidenceError("probe_invalid")
    if payload.get("subtree") != "PASS" or payload.get("synthetic_crud") not in {
        "PASS",
        "SKIPPED",
    }:
        raise EvidenceError("probe_invalid")
    for name in ("source_count", "indexed_count", "quarantined_count", "rss_kib"):
        value = payload.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise EvidenceError("probe_invalid")
    return cast(dict[str, object], payload)


def _run_profile_probe(
    candidate_python: Path,
    working: Path,
    cache_root: Path,
    profile: Profile,
    timeout_seconds: int,
    cycle: int,
    *,
    command_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, object]:
    working = working.resolve(strict=True)
    cache_root = cache_root.resolve(strict=False)
    before = _graph_manifest_digest(working)
    code = _DEFAULT_ON_PROBE if profile == "default-on" else _READ_ONLY_PROBE
    try:
        completed = command_runner(
            [str(candidate_python), "-c", code],
            cwd=candidate_python.parent,
            env=_safe_environment(working, cache_root, profile, cycle),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise EvidenceError("probe_timeout") from exc
    except OSError as exc:
        raise EvidenceError("probe_launch_failed") from exc
    if completed.returncode != 0:
        raise EvidenceError("probe_flag_on_failed")
    try:
        payload: object = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise EvidenceError("probe_payload_invalid") from exc
    validated = _validate_payload(payload)
    if _graph_manifest_digest(working) != before:
        raise EvidenceError("working_copy_changed")
    return validated


def run_gate_b_soak(
    *,
    profile: Profile,
    output: Path,
    candidate_python: Path,
    source_vault: Path,
    expected_source_file: Path,
    working_root: Path,
    cache_root: Path,
    duration_seconds: int,
    max_cycles: int,
    interval_seconds: int,
    page_parse_timeout_seconds: int,
) -> object:
    source = source_vault.expanduser().resolve(strict=True)
    work = working_root.expanduser().resolve(strict=False)
    resolved_output = output.expanduser().resolve(strict=False)
    repo = Path(__file__).resolve().parents[1]
    cache = _resolve_external_cache_root(
        cache_root,
        source=source,
        working=work,
        output=resolved_output,
        repo=repo,
    )
    _load_or_create_profile(resolved_output, profile, cache)

    def copier(copy_source: Path, destination: Path) -> None:
        _copy_vault_without_cache(copy_source, destination)
        _bind_manifest(resolved_output, profile, cache, destination)

    def probe_runner(
        python: Path,
        graph: Path,
        timeout: int,
        _page_parse_timeout: int,
        cycle: int,
    ) -> dict[str, object]:
        _bind_manifest(resolved_output, profile, cache, graph)
        result = _run_profile_probe(python, graph, cache, profile, timeout, cycle)
        _bind_manifest(resolved_output, profile, cache, graph)
        return result

    return collect_soak(
        resolved_output,
        candidate_python=candidate_python,
        source_vault=source,
        expected_source_file=expected_source_file,
        working_root=work,
        duration_seconds=duration_seconds,
        max_cycles=max_cycles,
        interval_seconds=interval_seconds,
        page_parse_timeout_seconds=page_parse_timeout_seconds,
        probe_runner=probe_runner,
        copier=copier,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=_PROFILES, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-python", type=Path, required=True)
    parser.add_argument("--source-vault", type=Path, required=True)
    parser.add_argument("--expected-source-realpath-file", type=Path, required=True)
    parser.add_argument("--working-root", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--duration-seconds", type=int, default=72 * 60 * 60)
    parser.add_argument("--max-cycles", type=int, default=1_000)
    parser.add_argument("--interval-seconds", type=int, default=10 * 60)
    parser.add_argument("--page-parse-timeout-seconds", type=int, default=15)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        run_gate_b_soak(
            profile=cast(Profile, args.profile),
            output=args.output,
            candidate_python=args.candidate_python,
            source_vault=args.source_vault,
            expected_source_file=args.expected_source_realpath_file,
            working_root=args.working_root,
            cache_root=args.cache_root,
            duration_seconds=args.duration_seconds,
            max_cycles=args.max_cycles,
            interval_seconds=args.interval_seconds,
            page_parse_timeout_seconds=args.page_parse_timeout_seconds,
        )
    except EvidenceError as exc:
        print(f"gate b soak: {exc.category}", file=sys.stderr)
        return 2
    except OSError:
        print("gate b soak: storage_error", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
