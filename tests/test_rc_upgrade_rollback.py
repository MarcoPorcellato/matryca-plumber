from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPTS = Path(__file__).parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def _module() -> ModuleType:
    path = Path(__file__).parents[1] / "scripts" / "qualify_rc_upgrade_rollback.py"
    spec = importlib.util.spec_from_file_location("rc_upgrade_rollback", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _source(tmp_path: Path) -> tuple[Path, Path, Path]:
    source = tmp_path / "source"
    for directory in ("pages", "journals", "logseq"):
        (source / directory).mkdir(parents=True)
    (source / "pages" / "note.md").write_text("- immutable note\n", encoding="utf-8")
    wheel = tmp_path / "matryca_plumber-2.0.0rc1-py3-none-any.whl"
    wheel.write_bytes(b"wheel")
    expected_source = tmp_path / "expected-source.txt"
    expected_source.write_text(f"{source.resolve()}\n", encoding="utf-8")
    return source, wheel, expected_source


def _command(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], 0, "", "")


def _candidate(*_args: object, **_kwargs: object) -> dict[str, bool]:
    return {
        "candidate_version": True,
        "default_on_ready": True,
        "explicit_false": True,
        "external_cache_only": True,
        "schema_mismatch_fallback": True,
        "schema_mismatch_recovered": True,
        "failed_rebuild_fallback": True,
        "failed_rebuild_recovered": True,
        "read_only_ready": True,
        "read_only_external_cache": True,
        "markdown_unchanged": True,
        "graph_files_unchanged": True,
    }


def test_collector_records_sanitized_pass_for_each_baseline(tmp_path: Path) -> None:
    module = _module()
    source, wheel, expected_source = _source(tmp_path)

    result = module.collect_upgrade_rollback(
        tmp_path / "evidence",
        wheel=wheel,
        candidate_package="2.0.0rc1",
        baselines=("1.14.5", "2.0.0a5", "2.0.0b1"),
        source_vault=source,
        expected_source_file=expected_source,
        command_runner=_command,
        candidate_probe=_candidate,
        installed_probe=lambda _python, _package: True,
    )

    assert result["status"] == "PASS"
    assert [row["package"] for row in result["baselines"]] == ["1.14.5", "2.0.0a5", "2.0.0b1"]
    evidence = (tmp_path / "evidence" / module._RESULT_NAME).read_text(encoding="utf-8")
    assert str(source) not in evidence
    assert "immutable note" not in evidence
    assert json.loads(evidence)["status"] == "PASS"


def test_collector_fails_closed_and_preserves_source_on_candidate_failure(tmp_path: Path) -> None:
    module = _module()
    source, wheel, expected_source = _source(tmp_path)

    def fail_candidate(*_args: object, **_kwargs: object) -> dict[str, bool]:
        raise module.EvidenceError("candidate_probe_failed")

    result = module.collect_upgrade_rollback(
        tmp_path / "evidence",
        wheel=wheel,
        candidate_package="2.0.0rc1",
        baselines=("2.0.0b1",),
        source_vault=source,
        expected_source_file=expected_source,
        command_runner=_command,
        candidate_probe=fail_candidate,
        installed_probe=lambda _python, _package: True,
    )

    assert result["status"] == "FAIL"
    assert result["failure_category"] == "candidate_probe_failed"
    assert result["source_unchanged"] is True


def test_collector_rejects_duplicate_or_invalid_baselines(tmp_path: Path) -> None:
    module = _module()
    source, wheel, expected_source = _source(tmp_path)

    for baselines, category in (
        (("2.0.0b1", "2.0.0b1"), "baseline_packages_invalid"),
        (("not-a-version",), "baseline_package_invalid"),
    ):
        try:
            module.collect_upgrade_rollback(
                tmp_path / "evidence",
                wheel=wheel,
                candidate_package="2.0.0rc1",
                baselines=baselines,
                source_vault=source,
                expected_source_file=expected_source,
            )
        except module.EvidenceError as exc:
            assert exc.category == category
        else:
            raise AssertionError("expected a fail-closed validation error")


def test_collector_rejects_a_source_that_does_not_match_the_private_fingerprint(
    tmp_path: Path,
) -> None:
    module = _module()
    source, wheel, expected_source = _source(tmp_path)
    other = tmp_path / "other"
    for directory in ("pages", "journals", "logseq"):
        (other / directory).mkdir(parents=True)

    try:
        module.collect_upgrade_rollback(
            tmp_path / "evidence",
            wheel=wheel,
            candidate_package="2.0.0rc1",
            baselines=("2.0.0b1",),
            source_vault=other,
            expected_source_file=expected_source,
        )
    except module.EvidenceError as exc:
        assert exc.category == "source_fingerprint_mismatch"
    else:
        raise AssertionError("expected source_fingerprint_mismatch")


def test_candidate_probe_uses_the_external_cache_location_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _module()
    graph = tmp_path / "graph"
    graph.mkdir()
    payload = {
        "candidate_version": True,
        "default_on_ready": True,
        "explicit_false": True,
        "external_cache_only": True,
        "schema_mismatch_fallback": True,
        "schema_mismatch_recovered": True,
        "failed_rebuild_fallback": True,
        "failed_rebuild_recovered": True,
        "read_only_ready": True,
        "read_only_external_cache": True,
        "markdown_unchanged": True,
        "graph_files_unchanged": True,
    }
    commands: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert (
        module._candidate_probe(Path(sys.executable), graph, tmp_path / "cache", "2.0.0rc1", 30)
        == payload
    )
    script = commands[0][2]
    assert "from src.shadow.cache_location import resolve_shadow_cache_location" in script
    assert ".database_path.is_relative_to(cache_root)" in script
    assert "schema_mismatch_fallback" in script
    assert "failed_rebuild_fallback" in script
    assert "shadow_read_port_ready(graph)" in script


def test_candidate_probe_exercises_disposable_recovery_paths(tmp_path: Path) -> None:
    module = _module()
    graph = tmp_path / "graph"
    for directory in ("pages", "journals", "logseq"):
        (graph / directory).mkdir(parents=True)
    (graph / "pages" / "Probe.md").write_text(
        "- recovery probe\n  id:: 11111111-1111-4111-8111-111111111111\n",
        encoding="utf-8",
    )

    result = module._candidate_probe(
        Path(sys.executable),
        graph,
        tmp_path / "cache",
        version("matryca-plumber"),
        120,
    )

    assert all(result.values())
