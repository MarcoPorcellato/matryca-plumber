"""Resumable, privacy-bounded Shadow DB soak collection."""

from __future__ import annotations

import hashlib
import json
import os
import re
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
    _require_bound_wheel,
    _require_matching_gate_input,
    validate_output_directory,
)
from .wheel import (
    _copy_vault_without_cache,
    _markdown_fingerprint,
    _resolve_source_vault,
    _safe_environment,
    _verify_candidate_python,
)

_SOAK_SCHEMA_VERSION = 2
_DEFAULT_DURATION_SECONDS = 24 * 60 * 60
_DEFAULT_MAX_CYCLES = 145
_DEFAULT_INTERVAL_SECONDS = 10 * 60
_MAX_DURATION_SECONDS = 7 * 24 * 60 * 60
_MAX_CYCLES = 10_080
_MAX_INTERVAL_SECONDS = 60 * 60
_PROBE_TIMEOUT_SECONDS = 900
_ATTEMPT_HISTORY_LIMIT = 2 * _MAX_CYCLES + 2
_STATE_FILE = "soak-state.json"
_HEARTBEAT_FILE = "soak-heartbeat.json"
_RESULT_FILE = "soak-result.json"
_SUMMARY_FILE = "soak-summary.md"

type ProbeRunner = Callable[[Path, Path, int, int, int], dict[str, object]]
type Clock = Callable[[], float]
type Sleeper = Callable[[float], None]
type Copier = Callable[[Path, Path], None]
type CandidateVerifier = Callable[[Path], str]

_PHASES = ("ON", "OFF")
_RECOVERABLE_FAILURE_CATEGORIES = frozenset(
    {
        "probe_timeout",
        "probe_launch_failed",
        "probe_flag_on_failed",
        "probe_flag_off_failed",
        "probe_payload_invalid",
        "probe_invalid",
    }
)
_SAFE_CATEGORY = re.compile(r"[a-z0-9_]{1,80}")
_LEGACY_TREND_FIELDS = (
    "source_count",
    "indexed_count",
    "rss_kib",
    "elapsed_ms",
    "subtree",
    "synthetic_crud",
)

_OFF_PROBE = r"""
import json
import os
import resource
import sqlite3
import sys
from pathlib import Path

from src.shadow.bootstrap import rebuild_shadow_from_graph
from src.shadow.config import shadow_db_enabled
from src.shadow.connection import shadow_db_path
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
    META_QUARANTINED_PAGE_COUNT,
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
    stable_quarantined_count = int(get_meta(conn, META_QUARANTINED_PAGE_COUNT) or "0")
    # Post-quarantine invariant: a parked page is absent from `pages` on purpose, so the
    # cache is fully accounted for when indexed + quarantined covers every source page.
    assert stable_indexed_count == stable_page_count
    assert stable_source_count == stable_indexed_count + stable_quarantined_count
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
    "quarantined_count": stable_quarantined_count,
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
    if state.get("schema_version") == 1:
        return _migrate_v1_running_state(state)
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
        and isinstance(state.get("candidate_wheel_binding_digest"), str)
        and re.fullmatch(r"[0-9a-f]{64}", state["candidate_wheel_binding_digest"]) is not None
        and isinstance(state.get("elapsed_seconds"), (int, float))
        and not isinstance(state.get("elapsed_seconds"), bool)
        and isinstance(state.get("target_duration_seconds"), int)
        and isinstance(state.get("page_parse_timeout_seconds"), int)
        and state.get("next_phase") in _PHASES
        and isinstance(state.get("attempt_history"), list)
        and isinstance(state.get("attempt_cursor"), str)
    ):
        raise EvidenceError("soak_state_invalid")
    if state["completed_cycles"] < 0 or state["status"] not in {"RUNNING", "READY", "PASS", "FAIL"}:
        raise EvidenceError("soak_state_invalid")
    if not 2 <= state["page_parse_timeout_seconds"] <= 120:
        raise EvidenceError("soak_state_invalid")
    if not all(isinstance(item, dict) for item in state["trends"]):
        raise EvidenceError("soak_state_invalid")
    _validate_attempt_history(state)
    return state


def _attempt_digest(previous_digest: str, attempt: Mapping[str, object]) -> str:
    return _canonical_hash({"previous_digest": previous_digest, **attempt})


def _append_attempt(
    state: dict[str, Any],
    *,
    phase: str,
    outcome: str,
    category: str | None = None,
) -> None:
    if len(state["attempt_history"]) >= _ATTEMPT_HISTORY_LIMIT:
        raise EvidenceError("soak_attempt_limit")
    if phase not in (*_PHASES, "legacy_combined") or outcome not in {"PASS", "FAIL"}:
        raise EvidenceError("soak_state_invalid")
    if category is not None and _SAFE_CATEGORY.fullmatch(category) is None:
        raise EvidenceError("soak_state_invalid")
    previous_digest = str(state["attempt_cursor"])
    attempt: dict[str, object] = {
        "sequence": len(state["attempt_history"]),
        "cycle": state["completed_cycles"],
        "phase": phase,
        "outcome": outcome,
    }
    if category is not None:
        attempt["category"] = category
    attempt["previous_digest"] = previous_digest
    attempt["digest"] = _attempt_digest(previous_digest, attempt)
    state["attempt_history"].append(attempt)
    state["attempt_cursor"] = str(attempt["digest"])


def _validate_attempt_history(state: Mapping[str, Any]) -> None:
    if len(state["attempt_history"]) > _ATTEMPT_HISTORY_LIMIT:
        raise EvidenceError("soak_state_invalid")
    cursor = ""
    for sequence, attempt in enumerate(state["attempt_history"]):
        if not isinstance(attempt, dict):
            raise EvidenceError("soak_state_invalid")
        allowed = {"sequence", "cycle", "phase", "outcome", "previous_digest", "digest"}
        if "category" in attempt:
            allowed.add("category")
        if set(attempt) != allowed:
            raise EvidenceError("soak_state_invalid")
        if (
            attempt.get("sequence") != sequence
            or not isinstance(attempt.get("cycle"), int)
            or attempt["cycle"] < 0
            or attempt.get("phase") not in (*_PHASES, "legacy_combined")
            or attempt.get("outcome") not in {"PASS", "FAIL"}
            or attempt.get("previous_digest") != cursor
            or not isinstance(attempt.get("digest"), str)
            or (
                "category" in attempt
                and (
                    not isinstance(attempt["category"], str)
                    or _SAFE_CATEGORY.fullmatch(attempt["category"]) is None
                )
            )
        ):
            raise EvidenceError("soak_state_invalid")
        unsigned_attempt = {key: value for key, value in attempt.items() if key != "digest"}
        expected = _attempt_digest(cursor, unsigned_attempt)
        if attempt["digest"] != expected:
            raise EvidenceError("soak_state_invalid")
        cursor = attempt["digest"]
    if state["attempt_cursor"] != cursor:
        raise EvidenceError("soak_state_invalid")


def _migrate_v1_running_state(state: dict[str, Any]) -> dict[str, Any]:
    if (
        state.get("status") != "RUNNING"
        or not isinstance(state.get("completed_cycles"), int)
        or isinstance(state.get("completed_cycles"), bool)
        or not isinstance(state.get("trends"), list)
        or state["completed_cycles"] != len(state["trends"])
    ):
        raise EvidenceError("soak_state_invalid")
    migrated = dict(state)
    migrated["schema_version"] = _SOAK_SCHEMA_VERSION
    migrated["next_phase"] = "ON"
    migrated["attempt_history"] = []
    migrated["attempt_cursor"] = ""
    legacy_trends: list[dict[str, object]] = []
    for index, trend in enumerate(migrated["trends"]):
        if not isinstance(trend, dict) or set(trend) != set(_LEGACY_TREND_FIELDS):
            raise EvidenceError("soak_state_invalid")
        if trend["subtree"] not in {"PASS", "SKIPPED"} or trend["synthetic_crud"] not in {
            "PASS",
            "SKIPPED",
        }:
            raise EvidenceError("soak_state_invalid")
        legacy_trends.append(
            {
                "phase": "legacy_combined",
                "source_count": _nonnegative_int(trend, "source_count"),
                "indexed_count": _nonnegative_int(trend, "indexed_count"),
                "rss_kib": _nonnegative_int(trend, "rss_kib"),
                "elapsed_ms": _nonnegative_number(trend, "elapsed_ms"),
                "subtree": trend["subtree"],
                "synthetic_crud": trend["synthetic_crud"],
            }
        )
        migrated["completed_cycles"] = index
        _append_attempt(migrated, phase="legacy_combined", outcome="PASS")
    migrated["trends"] = legacy_trends
    migrated["completed_cycles"] = len(legacy_trends)
    _validate_attempt_history(migrated)
    return migrated


def _write_state(output: Path, state: dict[str, Any]) -> None:
    _atomic_write_json(_state_path(output), state)


def _write_heartbeat(output: Path, state: Mapping[str, Any]) -> None:
    _atomic_write_json(
        output / _HEARTBEAT_FILE,
        {
            "schema_version": _SOAK_SCHEMA_VERSION,
            "status": state["status"],
            "completed_cycles": state["completed_cycles"],
            "next_phase": state["next_phase"],
            "attempt_cursor": state["attempt_cursor"],
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
        candidate = candidate_python.expanduser().absolute()
    except OSError as exc:
        raise EvidenceError("candidate_python_invalid") from exc
    if not candidate.is_file() or not os.access(candidate, os.X_OK):
        raise EvidenceError("candidate_python_invalid")
    return candidate


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
        raise EvidenceError("probe_flag_on_failed" if enabled else "probe_flag_off_failed")
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
    # Optional: a probe recorded before quarantine existed reports no parked pages, which
    # is indistinguishable from a run where nothing was parked. Absent means zero rather
    # than invalid, so an older evidence state stays readable.
    quarantined = (
        0
        if payload.get("quarantined_count") is None
        else _nonnegative_int(payload, "quarantined_count")
    )
    validated = {
        name: payload[name]
        for name in (*bool_fields, "subtree", "synthetic_crud", *count_fields, "elapsed_ms")
    }
    validated["quarantined_count"] = quarantined
    return validated


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


def _run_soak_phase(
    candidate_python: Path,
    working_root: Path,
    timeout_seconds: int,
    page_parse_timeout_seconds: int,
    cycle: int,
    phase: str,
) -> dict[str, object]:
    if phase == "ON":
        return _run_process(
            candidate_python,
            working_root,
            _ON_PROBE,
            cycle=cycle,
            enabled=True,
            timeout_seconds=timeout_seconds,
            page_parse_timeout_seconds=page_parse_timeout_seconds,
        )
    if phase == "OFF":
        return _run_process(
            candidate_python,
            working_root,
            _OFF_PROBE,
            cycle=cycle,
            enabled=False,
            timeout_seconds=timeout_seconds,
            page_parse_timeout_seconds=page_parse_timeout_seconds,
        )
    raise EvidenceError("soak_state_invalid")


def _validate_phase_payload(phase: str, payload: Mapping[str, object]) -> dict[str, object]:
    if phase == "ON":
        validated = _validate_probe_payload({**payload, "flag_off": True, "elapsed_ms": 0.0})
        return {
            name: validated[name] for name in validated if name not in {"flag_off", "elapsed_ms"}
        }
    if phase == "OFF":
        if payload.get("flag_off") is not True:
            raise EvidenceError("probe_invalid")
        return {"flag_off": True, "rss_kib": _nonnegative_int(payload, "rss_kib")}
    raise EvidenceError("soak_state_invalid")


def _run_soak_probe(
    candidate_python: Path,
    working_root: Path,
    timeout_seconds: int,
    page_parse_timeout_seconds: int,
    cycle: int,
) -> dict[str, object]:
    started = time.monotonic()
    on = _validate_phase_payload(
        "ON",
        _run_soak_phase(
            candidate_python,
            working_root,
            timeout_seconds,
            page_parse_timeout_seconds,
            cycle,
            "ON",
        ),
    )
    off = _validate_phase_payload(
        "OFF",
        _run_soak_phase(
            candidate_python,
            working_root,
            timeout_seconds,
            page_parse_timeout_seconds,
            cycle,
            "OFF",
        ),
    )
    payload = {**off, **on, "elapsed_ms": round((time.monotonic() - started) * 1000, 3)}
    validated = _validate_probe_payload(payload)
    elapsed = payload["elapsed_ms"]
    if not isinstance(elapsed, float) or elapsed < 0:
        raise EvidenceError("probe_invalid")
    validated["elapsed_ms"] = elapsed
    validated["rss_kib"] = max(_nonnegative_int(off, "rss_kib"), _nonnegative_int(on, "rss_kib"))
    return validated


def _checkpoint_phase(
    output: Path,
    state: dict[str, Any],
    *,
    phase: str,
    outcome: str,
    next_phase: str,
    category: str | None = None,
) -> None:
    _append_attempt(state, phase=phase, outcome=outcome, category=category)
    state["next_phase"] = next_phase
    state["updated_at"] = _now()
    _write_state(output, state)
    _write_heartbeat(output, state)


def _working_copy_is_intact(work: Path, state: Mapping[str, Any]) -> bool:
    return work.is_dir() and _markdown_fingerprint(work) == state["working_markdown_fingerprint"]


def _trend(payload: Mapping[str, object]) -> dict[str, object]:
    return {
        "phase": "combined",
        **{
            name: payload[name]
            for name in (
                "source_count",
                "indexed_count",
                # Sampled every cycle so a page that is parked and released repeatedly
                # (flapping under varying machine load) is visible as a moving count
                # rather than having to be inferred after the run.
                "quarantined_count",
                "rss_kib",
                "elapsed_ms",
                "subtree",
                "synthetic_crud",
            )
        },
    }


def _summary_details(state: Mapping[str, Any]) -> dict[str, object]:
    trends = state["trends"]
    if not isinstance(trends, list):
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
        "candidate_provenance_digest": state["candidate_provenance_digest"],
        "candidate_wheel_binding_digest": state["candidate_wheel_binding_digest"],
        "subtree_checks": sum(item["subtree"] == "PASS" for item in trends),
        "subtree_skipped": sum(item["subtree"] == "SKIPPED" for item in trends),
        "synthetic_crud_checks": sum(item["synthetic_crud"] == "PASS" for item in trends),
        "attempts_recorded": len(state["attempt_history"]),
    }
    for name in numeric:
        values = [item[name] for item in trends]
        if not values:
            details[f"{name}_min"] = None
            details[f"{name}_max"] = None
            continue
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
        f"Attempts recorded: {result['attempts_recorded']}",
        "RSS KiB range: "
        f"{result['rss_kib_min'] if result['rss_kib_min'] is not None else 'not observed'}–"
        f"{result['rss_kib_max'] if result['rss_kib_max'] is not None else 'not observed'}",
        "Probe timing ms range: "
        f"{result['elapsed_ms_min'] if result['elapsed_ms_min'] is not None else 'not observed'}–"
        f"{result['elapsed_ms_max'] if result['elapsed_ms_max'] is not None else 'not observed'}",
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
    resolved_output = validate_output_directory(
        output, repo_root=_repo_root_from_script(), protected_roots=[source]
    )
    candidate_wheel_binding_digest = _require_bound_wheel(resolved_output, candidate_digest)
    work = _resolve_working_root(working_root, source=source, output=resolved_output)
    input_hash = _canonical_hash(
        {
            "source_realpath_sha256": hashlib.sha256(str(source).encode()).hexdigest(),
            "expected_source_sha256": hashlib.sha256(expected_source_file.read_bytes()).hexdigest(),
            "candidate_provenance_digest": candidate_digest,
            "candidate_wheel_binding_digest": candidate_wheel_binding_digest,
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
            "next_phase": "ON",
            "attempt_history": [],
            "attempt_cursor": "",
            "source_copy_snapshot_fingerprint": source_before,
            "source_unchanged_during_copy": True,
            "working_markdown_fingerprint": working_snapshot,
            "candidate_provenance_digest": candidate_digest,
            "candidate_wheel_binding_digest": candidate_wheel_binding_digest,
            "elapsed_seconds": 0.0,
            "target_duration_seconds": duration_seconds,
            "page_parse_timeout_seconds": page_parse_timeout_seconds,
            "started_at": _now(),
            "updated_at": _now(),
        }
        _write_state(resolved_output, state)
    elif (
        state["input_hash"] != input_hash
        or state["status"] not in {"RUNNING", "READY"}
        or state["target_duration_seconds"] != duration_seconds
        or state["candidate_provenance_digest"] != candidate_digest
        or state["candidate_wheel_binding_digest"] != candidate_wheel_binding_digest
        or state["page_parse_timeout_seconds"] != page_parse_timeout_seconds
    ):
        raise EvidenceError("soak_resume_mismatch")
    elif not _working_copy_is_intact(work, state):
        return _finish(
            resolved_output,
            state,
            status="FAIL",
            failure_category=(
                "working_copy_missing" if not work.is_dir() else "working_copy_changed"
            ),
        )
    if len(state["attempt_history"]) >= _ATTEMPT_HISTORY_LIMIT:
        return _finish(
            resolved_output,
            state,
            status="FAIL",
            failure_category="soak_attempt_limit",
        )

    started = clock()
    checkpoint_clock = started
    state["status"] = "RUNNING"
    if state["next_phase"] == "OFF":
        # A process may have stopped after the ON checkpoint. A resumed cycle is
        # deliberately restarted from ON so no partial pair can become a trend.
        _checkpoint_phase(
            resolved_output,
            state,
            phase="OFF",
            outcome="FAIL",
            category="probe_interrupted",
            next_phase="ON",
        )
    _write_heartbeat(resolved_output, state)
    legacy_pair: dict[str, object] | None = None

    def run_phase(phase: str) -> dict[str, object]:
        nonlocal legacy_pair
        cycle = int(state["completed_cycles"])
        if probe_runner is _run_soak_probe:
            return _validate_phase_payload(
                phase,
                _run_soak_phase(
                    candidate,
                    work,
                    probe_timeout_seconds,
                    page_parse_timeout_seconds,
                    cycle,
                    phase,
                ),
            )
        if legacy_pair is None:
            legacy_pair = _validate_probe_payload(
                probe_runner(
                    candidate,
                    work,
                    probe_timeout_seconds,
                    page_parse_timeout_seconds,
                    cycle,
                )
            )
        return _validate_phase_payload(phase, legacy_pair)

    try:
        while (
            state["completed_cycles"] < max_cycles and state["elapsed_seconds"] < duration_seconds
        ):
            legacy_pair = None
            pair_started = time.monotonic()
            on = run_phase("ON")
            if not _working_copy_is_intact(work, state):
                raise EvidenceError("working_copy_changed")
            _checkpoint_phase(
                resolved_output,
                state,
                phase="ON",
                outcome="PASS",
                next_phase="OFF",
            )
            off = run_phase("OFF")
            if not _working_copy_is_intact(work, state):
                raise EvidenceError("working_copy_changed")
            _checkpoint_phase(
                resolved_output,
                state,
                phase="OFF",
                outcome="PASS",
                next_phase="ON",
            )
            elapsed_ms = (
                legacy_pair["elapsed_ms"]
                if legacy_pair is not None
                else round((time.monotonic() - pair_started) * 1000, 3)
            )
            payload = _validate_probe_payload({**off, **on, "elapsed_ms": elapsed_ms})
            payload["rss_kib"] = max(
                _nonnegative_int(on, "rss_kib"), _nonnegative_int(off, "rss_kib")
            )
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
        if not _working_copy_is_intact(work, state):
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
        phase = str(state["next_phase"])
        if exc.category in _RECOVERABLE_FAILURE_CATEGORIES and _working_copy_is_intact(work, state):
            _checkpoint_phase(
                resolved_output,
                state,
                phase=phase,
                outcome="FAIL",
                category=exc.category,
                next_phase="ON",
            )
            state["status"] = "RUNNING"
            state["last_failure_category"] = exc.category
            state["updated_at"] = _now()
            _write_state(resolved_output, state)
            _write_heartbeat(resolved_output, state)
            raise
        return _finish(
            resolved_output,
            state,
            status="FAIL",
            failure_category=exc.category,
        )
