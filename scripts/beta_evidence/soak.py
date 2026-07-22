"""Resumable, privacy-bounded Shadow DB soak collection."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .core import (
    EvidenceError,
    GateRecord,
    _atomic_write,
    _atomic_write_json,
    _canonical_hash,
    _is_within,
    _record_gate,
    _repo_root_from_script,
    _require_matching_gate_input,
    validate_output_directory,
)
from .wheel import (
    _WHEEL_CANDIDATE,
    _copy_vault_without_cache,
    _markdown_fingerprint,
    _resolve_source_vault,
    _safe_environment,
)

_SOAK_SCHEMA_VERSION = 1
_DEFAULT_DURATION_SECONDS = 24 * 60 * 60
_DEFAULT_MAX_CYCLES = 145
_DEFAULT_INTERVAL_SECONDS = 10 * 60
_MAX_DURATION_SECONDS = 7 * 24 * 60 * 60
_MAX_CYCLES = 10_080
_MAX_INTERVAL_SECONDS = 60 * 60
_PROBE_TIMEOUT_SECONDS = 900
_STATE_FILE = "soak-state.json"
_HEARTBEAT_FILE = "soak-heartbeat.json"
_RESULT_FILE = "soak-result.json"
_SUMMARY_FILE = "soak-summary.md"

type ProbeRunner = Callable[[Path, Path, int, int, int], dict[str, object]]
type Clock = Callable[[], float]
type Sleeper = Callable[[float], None]
type Copier = Callable[[Path, Path], None]
type CandidateVerifier = Callable[[Path], str]

_CANDIDATE_PROBE = f"""
import hashlib
from importlib.metadata import distribution, version
from pathlib import Path
import sys

import src

origin = Path(src.__file__).resolve()
prefix = Path(sys.prefix).resolve()
assert origin.is_relative_to(prefix)
assert any(part in ("site-packages", "dist-packages") for part in origin.parts)
assert version("matryca-plumber") == {_WHEEL_CANDIDATE!r}
installed = distribution("matryca-plumber")
files = installed.files or ()
artifacts = sorted(
    file for file in files if str(file).endswith((".dist-info/METADATA", ".dist-info/RECORD"))
)
assert len(artifacts) == 2
digest = hashlib.sha256()
for artifact in artifacts:
    digest.update(installed.locate_file(artifact).read_bytes())
print(digest.hexdigest())
"""

_OFF_PROBE = r"""
import json
import os
import resource
import sqlite3
import sys
from pathlib import Path

from src.shadow.bootstrap import rebuild_shadow_from_graph
from src.shadow.config import shadow_db_enabled, shadow_db_path
from src.shadow.health import ShadowHealthState, resolve_shadow_health

graph = Path(os.environ["LOGSEQ_GRAPH_PATH"])
database = shadow_db_path(graph)
assert database.is_file()
before_bytes = database.read_bytes()
before_hash = __import__("hashlib").sha256(before_bytes).hexdigest()
conn = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
try:
    keys = ("generation", "source_page_count", "indexed_page_count")
    before = [
        conn.execute("SELECT value FROM shadow_meta WHERE key=?", (key,)).fetchone()
        for key in keys
    ]
finally:
    conn.close()
assert shadow_db_enabled() is False
assert resolve_shadow_health(graph) is ShadowHealthState.DISABLED
rebuild_shadow_from_graph(graph)
assert database.read_bytes() == before_bytes
assert __import__("hashlib").sha256(database.read_bytes()).hexdigest() == before_hash
conn = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
try:
    after = [
        conn.execute("SELECT value FROM shadow_meta WHERE key=?", (key,)).fetchone()
        for key in keys
    ]
finally:
    conn.close()
assert before == after
rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
if sys.platform == "darwin":
    rss //= 1024
print(json.dumps({"flag_off": True, "rss_kib": int(rss)}))
"""

_ON_PROBE = r"""
import json
import os
import resource
import sys
from pathlib import Path

from src.shadow.bootstrap import (
    ensure_shadow_runtime_at_startup,
    handle_shadow_watchdog_change,
    rebuild_shadow_from_graph,
)
from src.shadow.config import shadow_db_enabled
from src.shadow.connection import open_shadow_db
from src.shadow.health import ShadowHealthState, resolve_shadow_health
from src.shadow.meta import (
    META_INDEXED_PAGE_COUNT,
    META_LAST_SYNC_ERROR,
    META_SOURCE_PAGE_COUNT,
    get_meta,
    set_meta,
)
from src.shadow.query import search_blocks_fts
from src.shadow.subtree import SubtreeStatus, query_subtree_by_block_uuid

graph = Path(os.environ["LOGSEQ_GRAPH_PATH"])
cycle = int(os.environ["MATRYCA_SOAK_CYCLE"])
assert shadow_db_enabled() is True
if cycle == 0:
    rebuild_shadow_from_graph(graph)
ensure_shadow_runtime_at_startup(graph)
assert resolve_shadow_health(graph) is ShadowHealthState.READY

fixture = graph / "pages" / ".matryca_soak_fixture.md"
renamed = fixture.with_name(".matryca_soak_fixture_renamed.md")
fixture.write_text(
    "- matrycasoakuniquetoken parent\n"
    "  id:: 1a111111-1111-4111-8111-111111111111\n"
    "  - matrycasoakuniquetoken child\n"
    "    id:: 2a222222-2222-4222-8222-222222222222\n",
    encoding="utf-8",
)
handle_shadow_watchdog_change(graph, fixture, "created")
conn = open_shadow_db(graph)
try:
    source_count = int(get_meta(conn, META_SOURCE_PAGE_COUNT) or "0")
    indexed_count = int(get_meta(conn, META_INDEXED_PAGE_COUNT) or "0")
    assert source_count == indexed_count
    assert search_blocks_fts(conn, "matrycasoakuniquetoken", limit=2)
    result = query_subtree_by_block_uuid(conn, "1a111111-1111-4111-8111-111111111111", max_depth=1)
    assert result.status is SubtreeStatus.TRUNCATED
    assert len(result.nodes) == 1
finally:
    conn.close()

fixture.rename(renamed)
handle_shadow_watchdog_change(graph, renamed, "created")
conn = open_shadow_db(graph)
try:
    old = conn.execute(
        "SELECT 1 FROM pages WHERE file_path=?", ("pages/.matryca_soak_fixture.md",)
    ).fetchone()
    new = conn.execute(
        "SELECT 1 FROM pages WHERE file_path=?", ("pages/.matryca_soak_fixture_renamed.md",)
    ).fetchone()
    assert old is None
    assert new is not None
finally:
    conn.close()
renamed.unlink()
handle_shadow_watchdog_change(graph, renamed, "deleted")
conn = open_shadow_db(graph)
try:
    deleted = conn.execute(
        "SELECT 1 FROM pages WHERE file_path=?", ("pages/.matryca_soak_fixture_renamed.md",)
    ).fetchone()
    assert deleted is None
finally:
    conn.close()

if cycle % 12 == 0:
    conn = open_shadow_db(graph)
    try:
        set_meta(conn, META_LAST_SYNC_ERROR, "controlled recovery")
        conn.commit()
    finally:
        conn.close()
    assert resolve_shadow_health(graph) is ShadowHealthState.ERROR
    rebuild_shadow_from_graph(graph)
    assert resolve_shadow_health(graph) is ShadowHealthState.READY
conn = open_shadow_db(graph)
try:
    stable_source_count = int(get_meta(conn, META_SOURCE_PAGE_COUNT) or "0")
    stable_indexed_count = int(get_meta(conn, META_INDEXED_PAGE_COUNT) or "0")
    stable_page_count = int(conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0])
    assert stable_source_count == stable_indexed_count == stable_page_count
finally:
    conn.close()
rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
if sys.platform == "darwin":
    rss //= 1024
print(json.dumps({
    "flag_on": True,
    "restart_health": True,
    "fts": True,
    "subtree": "PASS",
    "synthetic_crud": "PASS",
    "recovery": True,
    "source_count": stable_source_count,
    "indexed_count": stable_indexed_count,
    "rss_kib": int(rss),
}))
"""


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _load_json(path: Path, *, category: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(category) from exc
    if not isinstance(value, dict):
        raise EvidenceError(category)
    return value


def _state_path(output: Path) -> Path:
    return output / _STATE_FILE


def _load_state(output: Path) -> dict[str, Any] | None:
    path = _state_path(output)
    if not path.exists():
        return None
    state = _load_json(path, category="soak_state_invalid")
    if state.get("schema_version") != _SOAK_SCHEMA_VERSION:
        raise EvidenceError("soak_state_invalid")
    if not (
        isinstance(state.get("input_hash"), str)
        and isinstance(state.get("completed_cycles"), int)
        and isinstance(state.get("trends"), list)
        and isinstance(state.get("status"), str)
        and isinstance(state.get("source_copy_snapshot_fingerprint"), str)
        and state.get("source_unchanged_during_copy") is True
        and isinstance(state.get("working_markdown_fingerprint"), str)
        and isinstance(state.get("candidate_provenance_digest"), str)
        and isinstance(state.get("elapsed_seconds"), (int, float))
        and not isinstance(state.get("elapsed_seconds"), bool)
        and isinstance(state.get("target_duration_seconds"), int)
        and isinstance(state.get("page_parse_timeout_seconds"), int)
    ):
        raise EvidenceError("soak_state_invalid")
    if state["completed_cycles"] < 0 or state["status"] not in {"RUNNING", "PASS", "FAIL"}:
        raise EvidenceError("soak_state_invalid")
    if not 2 <= state["page_parse_timeout_seconds"] <= 120:
        raise EvidenceError("soak_state_invalid")
    if not all(isinstance(item, dict) for item in state["trends"]):
        raise EvidenceError("soak_state_invalid")
    return state


def _write_state(output: Path, state: dict[str, Any]) -> None:
    _atomic_write_json(_state_path(output), state)


def _write_heartbeat(output: Path, state: Mapping[str, Any]) -> None:
    _atomic_write_json(
        output / _HEARTBEAT_FILE,
        {
            "schema_version": _SOAK_SCHEMA_VERSION,
            "status": state["status"],
            "completed_cycles": state["completed_cycles"],
            "updated_at": state["updated_at"],
        },
    )


def _validate_limits(*, duration_seconds: int, max_cycles: int, interval_seconds: int) -> None:
    if not 1 <= duration_seconds <= _MAX_DURATION_SECONDS:
        raise EvidenceError("duration_invalid")
    if not 1 <= max_cycles <= _MAX_CYCLES:
        raise EvidenceError("cycles_invalid")
    if not 0 <= interval_seconds <= _MAX_INTERVAL_SECONDS:
        raise EvidenceError("interval_invalid")


def _resolve_candidate_python(candidate_python: Path) -> Path:
    try:
        resolved = candidate_python.expanduser().resolve(strict=True)
    except OSError as exc:
        raise EvidenceError("candidate_python_invalid") from exc
    if not resolved.is_file():
        raise EvidenceError("candidate_python_invalid")
    return resolved


def _verify_candidate_python(candidate_python: Path) -> str:
    try:
        completed = subprocess.run(
            [str(candidate_python), "-c", _CANDIDATE_PROBE],
            cwd=tempfile.gettempdir(),
            env={"PATH": os.environ.get("PATH", ""), "PYTHONNOUSERSITE": "1"},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EvidenceError("candidate_python_invalid") from exc
    if completed.returncode != 0:
        raise EvidenceError("candidate_version_mismatch")
    digest = completed.stdout.strip()
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise EvidenceError("candidate_provenance_invalid")
    return digest


def _resolve_working_root(working_root: Path, *, source: Path, output: Path) -> Path:
    resolved = working_root.expanduser().resolve(strict=False)
    repo = _repo_root_from_script().expanduser().resolve(strict=False)
    if any(_is_within(resolved, protected) for protected in (repo, source, output)):
        raise EvidenceError("working_copy_unsafe")
    if resolved.exists() and resolved.is_symlink():
        raise EvidenceError("working_copy_invalid")
    return resolved


def _run_process(
    python: Path,
    graph: Path,
    code: str,
    *,
    cycle: int,
    enabled: bool,
    timeout_seconds: int,
    page_parse_timeout_seconds: int,
) -> dict[str, object]:
    environment = _safe_environment(
        graph,
        enabled=enabled,
        page_parse_timeout_seconds=page_parse_timeout_seconds,
    )
    environment["MATRYCA_SOAK_CYCLE"] = str(cycle)
    try:
        completed = subprocess.run(
            [str(python), "-c", code],
            cwd=tempfile.gettempdir(),
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise EvidenceError("probe_timeout") from exc
    except OSError as exc:
        raise EvidenceError("probe_launch_failed") from exc
    if completed.returncode != 0:
        raise EvidenceError("probe_failed")
    try:
        payload = json.loads(completed.stdout.strip())
    except json.JSONDecodeError as exc:
        raise EvidenceError("probe_payload_invalid") from exc
    if not isinstance(payload, dict):
        raise EvidenceError("probe_payload_invalid")
    return payload


def _validate_probe_payload(payload: Mapping[str, object]) -> dict[str, object]:
    bool_fields = ("flag_off", "flag_on", "restart_health", "fts", "recovery")
    count_fields = ("source_count", "indexed_count", "rss_kib")
    if any(payload.get(name) is not True for name in bool_fields):
        raise EvidenceError("probe_invalid")
    if payload.get("subtree") not in {"PASS", "SKIPPED"}:
        raise EvidenceError("probe_invalid")
    if payload.get("synthetic_crud") not in {"PASS", "SKIPPED"}:
        raise EvidenceError("probe_invalid")
    for name in count_fields:
        _nonnegative_int(payload, name)
    _nonnegative_number(payload, "elapsed_ms")
    return {
        name: payload[name]
        for name in (*bool_fields, "subtree", "synthetic_crud", *count_fields, "elapsed_ms")
    }


def _nonnegative_int(payload: Mapping[str, object], name: str) -> int:
    value = payload.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise EvidenceError("probe_invalid")
    return value


def _nonnegative_number(payload: Mapping[str, object], name: str) -> float | int:
    value = payload.get(name)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        raise EvidenceError("probe_invalid")
    return value


def _run_soak_probe(
    candidate_python: Path,
    working_root: Path,
    timeout_seconds: int,
    page_parse_timeout_seconds: int,
    cycle: int,
) -> dict[str, object]:
    started = time.monotonic()
    on = _run_process(
        candidate_python,
        working_root,
        _ON_PROBE,
        cycle=cycle,
        enabled=True,
        timeout_seconds=timeout_seconds,
        page_parse_timeout_seconds=page_parse_timeout_seconds,
    )
    off = _run_process(
        candidate_python,
        working_root,
        _OFF_PROBE,
        cycle=cycle,
        enabled=False,
        timeout_seconds=timeout_seconds,
        page_parse_timeout_seconds=page_parse_timeout_seconds,
    )
    payload = {**off, **on, "elapsed_ms": round((time.monotonic() - started) * 1000, 3)}
    validated = _validate_probe_payload(payload)
    elapsed = payload["elapsed_ms"]
    if not isinstance(elapsed, float) or elapsed < 0:
        raise EvidenceError("probe_invalid")
    validated["elapsed_ms"] = elapsed
    validated["rss_kib"] = max(_nonnegative_int(off, "rss_kib"), _nonnegative_int(on, "rss_kib"))
    return validated


def _trend(payload: Mapping[str, object]) -> dict[str, object]:
    return {
        name: payload[name]
        for name in (
            "source_count",
            "indexed_count",
            "rss_kib",
            "elapsed_ms",
            "subtree",
            "synthetic_crud",
        )
    }


def _summary_details(state: Mapping[str, Any]) -> dict[str, object]:
    trends = state["trends"]
    if not isinstance(trends, list) or not trends:
        raise EvidenceError("soak_state_invalid")
    numeric = ("source_count", "indexed_count", "rss_kib", "elapsed_ms")
    details: dict[str, object] = {
        "cycles_completed": state["completed_cycles"],
        "source_unchanged_during_copy": state["source_unchanged_during_copy"],
        "observed_duration_seconds": round(float(state["elapsed_seconds"]), 3),
        "target_duration_seconds": state["target_duration_seconds"],
        "page_parse_timeout_seconds": state["page_parse_timeout_seconds"],
        "duration_target_reached": state["elapsed_seconds"] >= state["target_duration_seconds"],
        "beta_qualified": (
            state["elapsed_seconds"] >= _DEFAULT_DURATION_SECONDS
            and state["target_duration_seconds"] >= _DEFAULT_DURATION_SECONDS
        ),
        "subtree_checks": sum(item["subtree"] == "PASS" for item in trends),
        "subtree_skipped": sum(item["subtree"] == "SKIPPED" for item in trends),
        "synthetic_crud_checks": sum(item["synthetic_crud"] == "PASS" for item in trends),
    }
    for name in numeric:
        values = [item[name] for item in trends]
        if not all(
            isinstance(value, (int, float)) and not isinstance(value, bool) for value in values
        ):
            raise EvidenceError("soak_state_invalid")
        details[f"{name}_min"] = min(values)
        details[f"{name}_max"] = max(values)
    return details


def _render_summary(result: Mapping[str, object]) -> str:
    lines = [
        "# Sanitized beta soak result",
        "",
        f"Status: {result['status']}",
        f"Cycles completed: {result['cycles_completed']}",
        f"Observed duration seconds: {result['observed_duration_seconds']}",
        f"Page parse timeout seconds: {result['page_parse_timeout_seconds']}",
        f"Beta-qualified duration: {result['beta_qualified']}",
        f"Source unchanged during copy: {result['source_unchanged_during_copy']}",
        f"FTS/subtree checks: {result['subtree_checks']} pass, {result['subtree_skipped']} skipped",
        f"Synthetic CRUD checks: {result['synthetic_crud_checks']} pass",
        f"RSS KiB range: {result['rss_kib_min']}–{result['rss_kib_max']}",
        f"Probe timing ms range: {result['elapsed_ms_min']}–{result['elapsed_ms_max']}",
        "",
    ]
    return "\n".join(lines)


def _finish(
    output: Path,
    state: dict[str, Any],
    *,
    status: str,
    failure_category: str | None = None,
) -> GateRecord:
    details = _summary_details(state)
    details["status"] = status
    if failure_category is not None:
        details["failure_category"] = failure_category
    result = {"schema_version": _SOAK_SCHEMA_VERSION, **details}
    _atomic_write_json(output / _RESULT_FILE, result)
    _atomic_write(output / _SUMMARY_FILE, _render_summary(result))
    state["status"] = status
    state["updated_at"] = _now()
    _write_state(output, state)
    _write_heartbeat(output, state)
    return _record_gate(
        output,
        GateRecord("soak", str(state["input_hash"]), status, details),
    )


def collect_soak(
    output: Path,
    *,
    candidate_python: Path,
    source_vault: Path,
    expected_source_file: Path,
    working_root: Path,
    page_parse_timeout_seconds: int,
    duration_seconds: int = _DEFAULT_DURATION_SECONDS,
    max_cycles: int = _DEFAULT_MAX_CYCLES,
    interval_seconds: int = _DEFAULT_INTERVAL_SECONDS,
    probe_timeout_seconds: int = _PROBE_TIMEOUT_SECONDS,
    probe_runner: ProbeRunner = _run_soak_probe,
    copier: Copier = _copy_vault_without_cache,
    candidate_verifier: CandidateVerifier = _verify_candidate_python,
    clock: Clock = time.monotonic,
    sleeper: Sleeper = time.sleep,
) -> GateRecord:
    """Collect bounded, resumable, sanitized candidate-vault soak evidence."""
    _validate_limits(
        duration_seconds=duration_seconds, max_cycles=max_cycles, interval_seconds=interval_seconds
    )
    if not 1 <= probe_timeout_seconds <= _PROBE_TIMEOUT_SECONDS:
        raise EvidenceError("timeout_invalid")
    if not 2 <= page_parse_timeout_seconds <= 120:
        raise EvidenceError("page_parse_timeout_invalid")
    source = _resolve_source_vault(source_vault, expected_source_file)
    candidate = _resolve_candidate_python(candidate_python)
    candidate_digest = candidate_verifier(candidate)
    if not candidate_digest:
        raise EvidenceError("candidate_provenance_invalid")
    resolved_output = validate_output_directory(
        output, repo_root=_repo_root_from_script(), protected_roots=[source]
    )
    work = _resolve_working_root(working_root, source=source, output=resolved_output)
    input_hash = _canonical_hash(
        {
            "source_realpath_sha256": hashlib.sha256(str(source).encode()).hexdigest(),
            "expected_source_sha256": hashlib.sha256(expected_source_file.read_bytes()).hexdigest(),
            "candidate_provenance_digest": candidate_digest,
            "duration_seconds": duration_seconds,
            "max_cycles": max_cycles,
            "interval_seconds": interval_seconds,
            "page_parse_timeout_seconds": page_parse_timeout_seconds,
        }
    )
    _require_matching_gate_input(
        resolved_output,
        gate_id="soak",
        input_hash=input_hash,
    )
    resolved_output.mkdir(parents=True, exist_ok=True)
    state = _load_state(resolved_output)
    if state is None:
        if work.exists():
            raise EvidenceError("working_copy_exists")
        source_before = _markdown_fingerprint(source)
        copier(source, work)
        source_after = _markdown_fingerprint(source)
        if source_after != source_before:
            raise EvidenceError("source_changed_during_copy")
        if not work.is_dir() or work.resolve() == source:
            raise EvidenceError("working_copy_invalid")
        working_snapshot = _markdown_fingerprint(work)
        if working_snapshot != source_before:
            raise EvidenceError("working_copy_invalid")
        state = {
            "schema_version": _SOAK_SCHEMA_VERSION,
            "input_hash": input_hash,
            "status": "RUNNING",
            "completed_cycles": 0,
            "trends": [],
            "source_copy_snapshot_fingerprint": source_before,
            "source_unchanged_during_copy": True,
            "working_markdown_fingerprint": working_snapshot,
            "candidate_provenance_digest": candidate_digest,
            "elapsed_seconds": 0.0,
            "target_duration_seconds": duration_seconds,
            "page_parse_timeout_seconds": page_parse_timeout_seconds,
            "started_at": _now(),
            "updated_at": _now(),
        }
        _write_state(resolved_output, state)
    elif (
        state["input_hash"] != input_hash
        or state["status"] != "RUNNING"
        or state["target_duration_seconds"] != duration_seconds
        or state["candidate_provenance_digest"] != candidate_digest
        or state["page_parse_timeout_seconds"] != page_parse_timeout_seconds
    ):
        raise EvidenceError("soak_resume_mismatch")
    elif not work.is_dir():
        raise EvidenceError("working_copy_missing")
    elif _markdown_fingerprint(work) != state["working_markdown_fingerprint"]:
        raise EvidenceError("working_copy_changed")

    started = clock()
    checkpoint_clock = started
    _write_heartbeat(resolved_output, state)
    try:
        while (
            state["completed_cycles"] < max_cycles and state["elapsed_seconds"] < duration_seconds
        ):
            payload = _validate_probe_payload(
                probe_runner(
                    candidate,
                    work,
                    probe_timeout_seconds,
                    page_parse_timeout_seconds,
                    state["completed_cycles"],
                )
            )
            if _markdown_fingerprint(work) != state["working_markdown_fingerprint"]:
                raise EvidenceError("working_copy_changed")
            current_clock = clock()
            state["elapsed_seconds"] += max(0.0, current_clock - checkpoint_clock)
            checkpoint_clock = current_clock
            state["trends"].append(_trend(payload))
            state["completed_cycles"] += 1
            state["updated_at"] = _now()
            _write_state(resolved_output, state)
            _write_heartbeat(resolved_output, state)
            if (
                state["completed_cycles"] < max_cycles
                and state["elapsed_seconds"] < duration_seconds
            ):
                sleeper(float(interval_seconds))
        if _markdown_fingerprint(work) != state["working_markdown_fingerprint"]:
            raise EvidenceError("working_copy_changed")
        if state["elapsed_seconds"] < duration_seconds:
            state["last_failure_category"] = "duration_incomplete"
            state["updated_at"] = _now()
            _write_state(resolved_output, state)
            _write_heartbeat(resolved_output, state)
            raise EvidenceError("duration_incomplete")
        return _finish(
            resolved_output,
            state,
            status="PASS",
        )
    except EvidenceError as exc:
        if exc.category == "duration_incomplete":
            raise
        if state["trends"]:
            return _finish(
                resolved_output,
                state,
                status="FAIL",
                failure_category=exc.category,
            )
        state["status"] = "FAIL"
        state["updated_at"] = _now()
        _write_state(resolved_output, state)
        _write_heartbeat(resolved_output, state)
        raise
