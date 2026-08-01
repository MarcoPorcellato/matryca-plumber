"""Private isolated wheel-upgrade collector for beta evidence."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Sequence
from contextlib import suppress
from pathlib import Path
from typing import Any, Protocol, cast

from .core import (
    EvidenceError,
    GateRecord,
    _candidate_wheel_binding_digest,
    _canonical_hash,
    _is_within,
    _record_gate,
    _repo_root_from_script,
    _require_matching_gate_input,
    validate_output_directory,
)

_WHEEL_PROBE_SCHEMA_VERSION = 1
_WHEEL_BASELINE = "2.0.0a5"
_WHEEL_CANDIDATE = "2.0.0b1"
_WHEEL_TIMEOUT_SECONDS = 180
_WHEEL_PROBE_PAGE = "Beta Wheel Probe.md"
_WHEEL_PROBE_DUPLICATE_PAGE = "Beta Wheel Duplicate.md"
_PROCESS_ENV_ALLOWLIST = frozenset(
    {
        "PATH",
        "HOME",
        "TMPDIR",
        "TMP",
        "TEMP",
        "UV_CACHE_DIR",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "no_proxy",
    }
)

_CANDIDATE_PROBE = f"""
import base64
import csv
import hashlib
import hmac
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
record_candidates = sorted(
    str(file) for file in files if str(file).endswith(".dist-info/RECORD")
)
assert len(record_candidates) == 1
record_path = record_candidates[0]
record_location = Path(installed.locate_file(record_path))
assert record_location.is_file()
assert record_location.resolve().is_relative_to(prefix)

generated_dist_info_entries = {{
    "INSTALLER",
    "REQUESTED",
    "direct_url.json",
    "uv_cache.json",
    "RECORD",
}}
entries = []
metadata_entries = 0
payload_entries = 0
with record_location.open(encoding="utf-8", newline="") as record_file:
    for row in csv.reader(record_file):
        assert len(row) == 3
        raw_path, hash_spec, size = row
        assert raw_path and not raw_path.startswith(("/", "\\\\"))
        normalized_path = "/".join(
            part for part in raw_path.replace("\\\\", "/").split("/") if part
        )
        assert normalized_path
        assert not any(character in normalized_path for character in "\\r\\n\\t")
        parts = normalized_path.split("/")
        parent_count = 0
        while parent_count < len(parts) and parts[parent_count] == "..":
            parent_count += 1
        if parent_count:
            assert (
                len(parts) == parent_count + 2
                and parts[parent_count] in {{"bin", "Scripts"}}
                and parts[-1] not in {{"", ".", ".."}}
            )
            continue
        assert ".." not in parts
        is_dist_info = len(parts) >= 2 and parts[-2].endswith(".dist-info")
        if is_dist_info and parts[-1] in generated_dist_info_entries:
            continue
        location = Path(installed.locate_file(normalized_path)).resolve()
        assert location.is_relative_to(prefix)
        assert hash_spec and size.isdecimal()
        algorithm, separator, encoded_hash = hash_spec.partition("=")
        assert separator and algorithm and encoded_hash
        algorithm = algorithm.lower()
        assert algorithm in {{"sha256", "sha384", "sha512"}}
        try:
            expected_hash = base64.b64decode(
                encoded_hash + "=" * (-len(encoded_hash) % 4), altchars=b"-_", validate=True
            )
        except ValueError:
            raise AssertionError from None
        assert location.is_file() and location.stat().st_size == int(size)
        actual_hash = hashlib.new(algorithm, location.read_bytes()).digest()
        assert hmac.compare_digest(actual_hash, expected_hash)
        canonical_hash = base64.urlsafe_b64encode(expected_hash).decode("ascii").rstrip("=")
        entries.append((normalized_path, f"{{algorithm}}={{canonical_hash}}", str(int(size))))
        if is_dist_info and parts[-1] == "METADATA":
            metadata_entries += 1
        elif not is_dist_info:
            payload_entries += 1

assert metadata_entries == 1
assert payload_entries >= 1
digest = hashlib.sha256()
for entry in sorted(entries):
    digest.update("\\0".join(entry).encode("utf-8"))
    digest.update(b"\\n")
print(digest.hexdigest())
"""


class CommandRunner(Protocol):
    def __call__(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        environment: dict[str, str],
        timeout_seconds: int,
    ) -> subprocess.CompletedProcess[str]: ...


class WheelProbeRunner(Protocol):
    def __call__(
        self,
        python: Path,
        graph_root: Path,
        *,
        phase: str,
        timeout_seconds: int,
        page_parse_timeout_seconds: int,
    ) -> dict[str, Any]: ...


class VaultCopier(Protocol):
    def __call__(self, source: Path, destination: Path) -> None: ...


type CandidateVerifier = Callable[[Path], str]


def _markdown_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.md")):
        if ".matryca_semantic_cache" not in path.parts:
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def _is_imported_from_venv_site_packages(imported: Path, venv_prefix: Path) -> bool:
    """Require the candidate module to resolve under this virtual environment."""
    try:
        module_path = imported.resolve(strict=True)
        virtual_environment = venv_prefix.resolve(strict=True)
        relative_module = module_path.relative_to(virtual_environment)
    except (OSError, ValueError):
        return False
    return "site-packages" in relative_module.parts


def _safe_environment(
    graph_root: Path, *, enabled: bool, page_parse_timeout_seconds: int
) -> dict[str, str]:
    environment = {
        name: value for name, value in os.environ.items() if name in _PROCESS_ENV_ALLOWLIST
    }
    environment["LOGSEQ_GRAPH_PATH"] = str(graph_root)
    environment["MATRYCA_SHADOW_DB_ENABLED"] = "1" if enabled else "0"
    environment["MATRYCA_CACHE_PATH"] = str(
        (graph_root.parent / ".matryca-beta-evidence-cache").resolve(strict=False)
    )
    environment["MATRYCA_PAGE_PARSE_TIMEOUT_S"] = str(page_parse_timeout_seconds)
    return environment


def _run_command(
    command: Sequence[str], *, cwd: Path, environment: dict[str, str], timeout_seconds: int
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(command),
            cwd=cwd,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise EvidenceError("command_timeout") from exc
    except OSError as exc:
        raise EvidenceError("command_error") from exc


def _require_command_success(result: subprocess.CompletedProcess[str]) -> None:
    if result.returncode != 0:
        raise EvidenceError("command_failed")


def _resolve_source_vault(source_vault: Path, expected_source_file: Path) -> Path:
    try:
        source = source_vault.expanduser().resolve(strict=True)
        expected_lines = expected_source_file.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise EvidenceError("source_fingerprint_invalid") from exc
    if len(expected_lines) != 1 or not expected_lines[0]:
        raise EvidenceError("source_fingerprint_invalid")
    try:
        expected = Path(expected_lines[0]).expanduser().resolve(strict=True)
    except OSError as exc:
        raise EvidenceError("source_fingerprint_invalid") from exc
    if source != expected:
        raise EvidenceError("source_fingerprint_mismatch")
    if not source.is_dir() or not all(
        (source / name).is_dir() for name in ("pages", "journals", "logseq")
    ):
        raise EvidenceError("source_vault_invalid")
    if any(
        path.is_symlink()
        for directory in (source / "pages", source / "journals")
        for path in directory.rglob("*")
    ):
        raise EvidenceError("source_symlink_unsupported")
    return source


def _resolve_candidate_wheel(wheel_path: Path, source_vault: Path) -> Path:
    try:
        wheel = wheel_path.expanduser().resolve(strict=True)
    except OSError as exc:
        raise EvidenceError("wheel_invalid") from exc
    if not wheel.is_file() or wheel.suffix != ".whl" or _is_within(wheel, source_vault):
        raise EvidenceError("wheel_invalid")
    return wheel


def _copy_vault_without_cache(source: Path, destination: Path) -> None:
    def ignore_cache(directory: str, names: list[str]) -> set[str]:
        del directory
        return {name for name in names if name == ".matryca_semantic_cache"}

    shutil.copytree(source, destination, symlinks=True, ignore=ignore_cache)


def _add_synthetic_probe_pages(graph_root: Path) -> None:
    graph_root.joinpath("pages", _WHEEL_PROBE_PAGE).write_text(
        "- beta wheel probe shadow token #wheel-probe-id\n"
        "  id:: 9c1ca0c6-72df-4fbc-b7a8-1e3b894889d1\n"
        "  - beta wheel child token\n    id:: 4d0dc3d1-f0b2-4f47-a391-29b9b693cfd4\n",
        encoding="utf-8",
        newline="\n",
    )


def _validate_probe_payload(payload: object) -> dict[str, Any]:
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema_version", "baseline", "candidate"}
        or payload.get("schema_version") != _WHEEL_PROBE_SCHEMA_VERSION
    ):
        raise EvidenceError("probe_invalid")
    baseline, candidate = payload.get("baseline"), payload.get("candidate")
    expected_baseline = {"ready", "generation_hash", "duration_ms"}
    expected_candidate = {
        "metadata_version_ok",
        "import_from_site_packages",
        "warm_ready",
        "generation_preserved",
        "fts_ok",
        "cte_ok",
        "flag_off_noop",
        "schema_recovery_ok",
        "duplicate_failure_non_ready",
        "duplicate_fallback_ok",
        "duplicate_preserved_generation",
        "duplicate_recovery_ok",
        "working_markdown_unchanged",
        "duration_ms",
    }
    if (
        not isinstance(baseline, dict)
        or not isinstance(candidate, dict)
        or set(baseline) != expected_baseline
        or set(candidate) != expected_candidate
    ):
        raise EvidenceError("probe_invalid")
    if (
        not isinstance(baseline["ready"], bool)
        or not isinstance(baseline["generation_hash"], str)
        or re.fullmatch(r"[0-9a-f]{64}", baseline["generation_hash"]) is None
        or not isinstance(baseline["duration_ms"], int)
        or baseline["duration_ms"] < 0
    ):
        raise EvidenceError("probe_invalid")
    for key, value in candidate.items():
        if key == "duration_ms":
            if not isinstance(value, int) or value < 0:
                raise EvidenceError("probe_invalid")
        elif not isinstance(value, bool):
            raise EvidenceError("probe_invalid")
    return cast(dict[str, Any], payload)


def _run_wheel_probe(
    python: Path,
    graph_root: Path,
    *,
    phase: str,
    timeout_seconds: int,
    page_parse_timeout_seconds: int,
) -> dict[str, Any]:
    wrapper = Path(__file__).resolve().parents[1] / "beta_readiness_evidence.py"
    result = _run_command(
        [str(python), str(wrapper), "_wheel-probe", "--vault", str(graph_root), "--phase", phase],
        cwd=Path(tempfile.gettempdir()),
        environment=_safe_environment(
            graph_root,
            enabled=True,
            page_parse_timeout_seconds=page_parse_timeout_seconds,
        ),
        timeout_seconds=timeout_seconds,
    )
    _require_command_success(result)
    try:
        return _validate_probe_payload(json.loads(result.stdout))
    except json.JSONDecodeError as exc:
        raise EvidenceError("probe_invalid") from exc


def _verify_candidate_python(candidate_python: Path) -> str:
    """Verify the installed candidate and return its sanitized provenance digest."""

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
    if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise EvidenceError("candidate_provenance_invalid")
    return digest


def _wheel_details(
    *,
    wheel: Path,
    source: Path,
    source_before: str,
    source_after: str,
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    candidate_provenance_digest: str,
    candidate_wheel_binding_digest: str,
    page_parse_timeout_seconds: int,
) -> dict[str, Any]:
    return {
        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "candidate_provenance_digest": candidate_provenance_digest,
        "candidate_wheel_binding_digest": candidate_wheel_binding_digest,
        "source_unchanged": source_before == source_after,
        "source_markdown_count": sum(
            1 for path in source.rglob("*.md") if ".matryca_semantic_cache" not in path.parts
        ),
        "page_parse_timeout_seconds": page_parse_timeout_seconds,
        "baseline": baseline,
        "candidate": candidate,
    }


def collect_wheel(
    output: Path,
    *,
    wheel_path: Path,
    source_vault: Path,
    expected_source_file: Path,
    page_parse_timeout_seconds: int,
    timeout_seconds: int = _WHEEL_TIMEOUT_SECONDS,
    command_runner: CommandRunner = _run_command,
    probe_runner: WheelProbeRunner = _run_wheel_probe,
    copier: VaultCopier = _copy_vault_without_cache,
    candidate_verifier: CandidateVerifier | None = None,
) -> GateRecord:
    """Collect isolated baseline-to-wheel evidence without writing the source vault."""
    if not 1 <= timeout_seconds <= 600:
        raise EvidenceError("timeout_invalid")
    if not 2 <= page_parse_timeout_seconds <= 120:
        raise EvidenceError("page_parse_timeout_invalid")
    source = _resolve_source_vault(source_vault, expected_source_file)
    wheel = _resolve_candidate_wheel(wheel_path, source)
    verifier = _verify_candidate_python if candidate_verifier is None else candidate_verifier
    resolved_output = validate_output_directory(
        output, repo_root=_repo_root_from_script(), protected_roots=[source]
    )
    if _is_within(resolved_output, wheel.parent) and wheel.parent == resolved_output:
        raise EvidenceError("output_unsafe")
    source_before = _markdown_fingerprint(source)
    fingerprint_input = {
        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "source_fingerprint": hashlib.sha256(str(source).encode("utf-8")).hexdigest(),
        "expected_source_fingerprint": hashlib.sha256(
            expected_source_file.read_bytes()
        ).hexdigest(),
        "baseline": _WHEEL_BASELINE,
        "candidate": _WHEEL_CANDIDATE,
        "page_parse_timeout_seconds": page_parse_timeout_seconds,
    }
    _require_matching_gate_input(
        resolved_output,
        gate_id="wheel",
        input_hash=_canonical_hash(fingerprint_input),
    )
    temporary_root: Path | None = None
    try:
        resolved_output.mkdir(parents=True, exist_ok=True)
        temporary_root = Path(tempfile.mkdtemp(prefix="beta-wheel-", dir=resolved_output))
        working_vault, venv = temporary_root / "vault", temporary_root / "venv"
        copier(source, working_vault)
        if working_vault.resolve() == source:
            raise EvidenceError("working_copy_invalid")
        _add_synthetic_probe_pages(working_vault)
        working_before, python = _markdown_fingerprint(working_vault), venv / "bin" / "python"
        environment, cwd = (
            _safe_environment(
                working_vault,
                enabled=True,
                page_parse_timeout_seconds=page_parse_timeout_seconds,
            ),
            Path(tempfile.gettempdir()),
        )
        for command in (
            ["uv", "venv", str(venv)],
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                f"matryca-plumber=={_WHEEL_BASELINE}",
            ],
        ):
            _require_command_success(
                command_runner(
                    command, cwd=cwd, environment=environment, timeout_seconds=timeout_seconds
                )
            )
        baseline = _validate_probe_payload(
            probe_runner(
                python,
                working_vault,
                phase="baseline",
                timeout_seconds=timeout_seconds,
                page_parse_timeout_seconds=page_parse_timeout_seconds,
            )
        )["baseline"]
        _require_command_success(
            command_runner(
                ["uv", "pip", "install", "--python", str(python), "--reinstall", str(wheel)],
                cwd=cwd,
                environment=environment,
                timeout_seconds=timeout_seconds,
            )
        )
        candidate = _validate_probe_payload(
            probe_runner(
                python,
                working_vault,
                phase="candidate",
                timeout_seconds=timeout_seconds,
                page_parse_timeout_seconds=page_parse_timeout_seconds,
            )
        )["candidate"]
        candidate["working_markdown_unchanged"] = (
            candidate["working_markdown_unchanged"]
            and _markdown_fingerprint(working_vault) == working_before
        )
        candidate_provenance_digest = verifier(python)
        candidate_wheel_binding_digest = _candidate_wheel_binding_digest(
            hashlib.sha256(wheel.read_bytes()).hexdigest(), candidate_provenance_digest
        )
        details = _wheel_details(
            wheel=wheel,
            source=source,
            source_before=source_before,
            source_after=_markdown_fingerprint(source),
            baseline=baseline,
            candidate=candidate,
            candidate_provenance_digest=candidate_provenance_digest,
            candidate_wheel_binding_digest=candidate_wheel_binding_digest,
            page_parse_timeout_seconds=page_parse_timeout_seconds,
        )
        checks = [
            details["source_unchanged"],
            baseline["ready"],
            *[value for value in candidate.values() if isinstance(value, bool)],
        ]
        return _record_gate(
            resolved_output,
            GateRecord(
                "wheel",
                _canonical_hash(fingerprint_input),
                "PASS" if all(checks) else "FAIL",
                details,
            ),
            metadata={"baseline_package": _WHEEL_BASELINE, "candidate_package": _WHEEL_CANDIDATE},
        )
    except EvidenceError as exc:
        failure = {
            "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
            "source_unchanged": source_before == _markdown_fingerprint(source),
            "page_parse_timeout_seconds": page_parse_timeout_seconds,
            "failure_category": exc.category,
        }
        return _record_gate(
            resolved_output,
            GateRecord("wheel", _canonical_hash(fingerprint_input), "FAIL", failure),
            metadata={"baseline_package": _WHEEL_BASELINE, "candidate_package": _WHEEL_CANDIDATE},
        )
    finally:
        if temporary_root is not None:
            shutil.rmtree(temporary_root, ignore_errors=True)


def wheel_probe_main(vault: Path, phase: str) -> int:
    """Run a version-local, stdout-only probe in the disposable vault."""
    started, graph = time.monotonic(), vault.resolve(strict=True)
    from importlib.metadata import version

    from src.agent.markdown_graph_repository import MarkdownGraphRepository, get_graph_read_port
    from src.shadow.bootstrap import (
        ensure_shadow_runtime_at_startup,
        rebuild_shadow_from_graph,
        reset_shadow_bootstrap_checked_for_tests,
    )
    from src.shadow.connection import open_shadow_db
    from src.shadow.health import ShadowHealthState, resolve_shadow_health
    from src.shadow.meta import META_GENERATION, get_meta, set_meta
    from src.shadow.query import search_blocks_fts
    from src.shadow.subtree import query_subtree_by_block_uuid

    def generation() -> str:
        connection = open_shadow_db(graph)
        try:
            return str(get_meta(connection, META_GENERATION) or "")
        finally:
            connection.close()

    baseline = {"ready": False, "generation_hash": "0" * 64, "duration_ms": 0}
    candidate = {
        "metadata_version_ok": False,
        "import_from_site_packages": False,
        "warm_ready": False,
        "generation_preserved": False,
        "fts_ok": False,
        "cte_ok": False,
        "flag_off_noop": False,
        "schema_recovery_ok": False,
        "duplicate_failure_non_ready": False,
        "duplicate_fallback_ok": False,
        "duplicate_preserved_generation": False,
        "duplicate_recovery_ok": False,
        "working_markdown_unchanged": True,
        "duration_ms": 0,
    }
    if phase == "baseline":
        rebuild_shadow_from_graph(graph)
        current = generation()
        baseline = {
            "ready": resolve_shadow_health(graph) is ShadowHealthState.READY,
            "generation_hash": hashlib.sha256(current.encode("utf-8")).hexdigest(),
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
    elif phase == "candidate":
        original, before = _markdown_fingerprint(graph), generation()
        ensure_shadow_runtime_at_startup(graph)
        candidate["metadata_version_ok"] = version("matryca-plumber") == _WHEEL_CANDIDATE
        import src as installed_src

        candidate["import_from_site_packages"] = _is_imported_from_venv_site_packages(
            Path(installed_src.__file__ or ""),
            Path(sys.prefix),
        )
        candidate["warm_ready"], candidate["generation_preserved"] = (
            resolve_shadow_health(graph) is ShadowHealthState.READY,
            generation() == before,
        )
        connection = open_shadow_db(graph)
        try:
            candidate["fts_ok"] = bool(search_blocks_fts(connection, "wheel", limit=10))
            subtree = query_subtree_by_block_uuid(
                connection, "9c1ca0c6-72df-4fbc-b7a8-1e3b894889d1"
            )
            candidate["cte_ok"] = any(
                node.block_uuid == "4d0dc3d1-f0b2-4f47-a391-29b9b693cfd4" for node in subtree.nodes
            )
        finally:
            connection.close()
        no_op = generation()
        os.environ["MATRYCA_SHADOW_DB_ENABLED"] = "0"
        reset_shadow_bootstrap_checked_for_tests()
        ensure_shadow_runtime_at_startup(graph)
        candidate["flag_off_noop"] = generation() == no_op
        os.environ["MATRYCA_SHADOW_DB_ENABLED"] = "1"
        connection = open_shadow_db(graph)
        try:
            set_meta(connection, "schema_version", "0")
            connection.commit()
        finally:
            connection.close()
        reset_shadow_bootstrap_checked_for_tests()
        ensure_shadow_runtime_at_startup(graph)
        candidate["schema_recovery_ok"] = resolve_shadow_health(graph) is ShadowHealthState.READY
        good = generation()
        graph.joinpath("pages", _WHEEL_PROBE_DUPLICATE_PAGE).write_text(
            "- duplicate wheel probe\n  id:: 9c1ca0c6-72df-4fbc-b7a8-1e3b894889d1\n",
            encoding="utf-8",
            newline="\n",
        )
        with suppress(Exception):
            rebuild_shadow_from_graph(graph)
        candidate["duplicate_failure_non_ready"] = (
            resolve_shadow_health(graph) is not ShadowHealthState.READY
        )
        candidate["duplicate_fallback_ok"] = isinstance(
            get_graph_read_port(graph), MarkdownGraphRepository
        )
        candidate["duplicate_preserved_generation"] = generation() == good
        graph.joinpath("pages", _WHEEL_PROBE_DUPLICATE_PAGE).unlink(missing_ok=True)
        rebuild_shadow_from_graph(graph)
        candidate["duplicate_recovery_ok"] = resolve_shadow_health(graph) is ShadowHealthState.READY
        candidate["working_markdown_unchanged"] = _markdown_fingerprint(graph) == original
        candidate["duration_ms"] = int((time.monotonic() - started) * 1000)
    else:
        raise EvidenceError("probe_invalid")
    print(
        json.dumps(
            {
                "schema_version": _WHEEL_PROBE_SCHEMA_VERSION,
                "baseline": baseline,
                "candidate": candidate,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0
